#!/usr/bin/env python3
"""
generate_gps_data.py - synthetic, anonymised GPS mobility data for GeoPulse.

Simulation model (all parameters live in config.py)
---------------------------------------------------
1. A synthetic city is drawn from the seed inside the configured bounding box:
   residential zones, workplace zones, transport hubs and commercial centres.
   A configurable share of zones is placed near Store A / Store B.
2. Every device gets a persistent anonymous ID, a home, a persona
   (commuter / hybrid / local), optional workplace + nearest transport hubs,
   habitual departure/dwell times, a store segment (A-only, B-only, both,
   neither) and a weekly retail-visit rate.
3. Each device-day is a short itinerary built from fixed "slots":
   home -> [hub -> hub] -> work -> retail 1 -> retail 2 -> [hub -> hub] -> home.
   Inactive slots are compacted away, then arrival/departure times are computed
   from distance, travel mode and dwell time.
4. GPS pings are sampled on a jittered 24-hour time grid. The emission probability
   follows an hourly activity profile (quiet at night, commuting peaks, daytime,
   evening retail), is boosted while a device is travelling, and varies per device.
   Positions are interpolated along the itinerary (L-shaped street-grid routes),
   then GPS noise (plus rare outliers) is added. Devices never teleport.

Everything is vectorised with NumPy per chunk of devices; chunks are appended to
the CSV so the full dataset never sits in RAM.

Usage
-----
    python generate_gps_data.py                      # defaults from config.py (1M records)
    python generate_gps_data.py --records 100000 --days 7
    python generate_gps_data.py --records 10000000 --days 28 --output data/gps_10m.csv
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from config import SUPPORTED_RECORD_RANGE, Config, utc_offset_string

GENERATOR_VERSION = "1.0.0"
R_EARTH_KM = 6371.0088
KM_PER_DEG = R_EARTH_KM * math.pi / 180.0
BIG = 1.0e7  # "never" in seconds; far beyond any time of day

# Itinerary slots, listed in the order they can occur during a day.
(S_HOME0, S_HUB_H_OUT, S_HUB_W_OUT, S_WORK, S_RETAIL1, S_RETAIL2,
 S_HUB_W_BACK, S_HUB_H_BACK, S_HOME_END) = range(9)
N_SLOTS = 9
SEG_A_ONLY, SEG_B_ONLY, SEG_BOTH, SEG_NONE = range(4)
PERSONA_COMMUTER, PERSONA_HYBRID, PERSONA_LOCAL = range(3)


# ----------------------------------------------------------------------------
# Geometry helpers (planar km grid anchored at the south-west corner)
# ----------------------------------------------------------------------------
class Projection:
    def __init__(self, cfg: Config):
        self.lat0, self.lon0 = cfg.lat_min, cfg.lon_min
        lat_mid = math.radians((cfg.lat_min + cfg.lat_max) / 2.0)
        self.ky = KM_PER_DEG
        self.kx = KM_PER_DEG * math.cos(lat_mid)
        self.width = (cfg.lon_max - cfg.lon_min) * self.kx
        self.height = (cfg.lat_max - cfg.lat_min) * self.ky

    def to_km(self, lat, lon):
        return (lon - self.lon0) * self.kx, (lat - self.lat0) * self.ky

    def to_deg(self, x, y):
        return self.lat0 + y / self.ky, self.lon0 + x / self.kx


def _clip_xy(pts, proj: Projection, margin: float):
    pts = np.array(pts, dtype=float)
    pts[..., 0] = np.clip(pts[..., 0], margin, proj.width - margin)
    pts[..., 1] = np.clip(pts[..., 1], margin, proj.height - margin)
    return pts


def _uniform_points(rng, n, proj, margin):
    return np.column_stack([rng.uniform(margin, proj.width - margin, n),
                            rng.uniform(margin, proj.height - margin, n)])


def _ring_points(rng, centres, n, r_lo, r_hi, proj, margin):
    """n points at distance [r_lo, r_hi] km from the given centres (round-robin)."""
    which = np.arange(n) % len(centres)
    ang = rng.uniform(0, 2 * np.pi, n)
    rad = rng.uniform(r_lo, r_hi, n)
    pts = centres[which] + np.column_stack([rad * np.cos(ang), rad * np.sin(ang)])
    return _clip_xy(pts, proj, margin)


def _pick_weighted(rng, weights):
    """Row-wise categorical sampling from an (n, k) non-negative weight matrix."""
    cdf = np.cumsum(weights, axis=1)
    cdf /= cdf[:, -1:]
    u = rng.random((weights.shape[0], 1))
    return np.minimum((u > cdf).sum(axis=1), weights.shape[1] - 1)


def make_device_ids(seed: int, start_index: int, n: int) -> np.ndarray:
    """Anonymous, persistent, collision-free IDs (bijective splitmix64 of the device index)."""
    mask64 = (1 << 64) - 1
    salt = np.uint64((seed * 0x9E3779B97F4A7C15 + 0x632BE59BD9B4E019) & mask64)
    idx = np.arange(start_index, start_index + n, dtype=np.uint64)
    with np.errstate(over="ignore"):
        z = idx + salt
        z = (z ^ (z >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
        z = (z ^ (z >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
        z = z ^ (z >> np.uint64(31))
    return np.array([f"DEV_{v:016X}" for v in z.tolist()], dtype=object)


# ----------------------------------------------------------------------------
# City layout
# ----------------------------------------------------------------------------
@dataclass
class CityLayout:
    store_xy: np.ndarray   # (2, 2)  Store A, Store B
    res_xy: np.ndarray
    res_w: np.ndarray
    work_xy: np.ndarray
    work_w: np.ndarray
    hub_xy: np.ndarray
    other_xy: np.ndarray
    other_w: np.ndarray


def build_layout(cfg: Config, proj: Projection, rng) -> CityLayout:
    m = cfg.boundary_margin_km
    if proj.width <= 2 * m or proj.height <= 2 * m:
        raise ValueError("City bounding box is too small for the configured boundary_margin_km")
    store_xy = np.vstack([proj.to_km(*cfg.store_a), proj.to_km(*cfg.store_b)]).astype(float)

    def zone_centres(n):
        n_near = min(n, int(round(n * cfg.zone_share_near_stores)))
        near = _ring_points(rng, store_xy, n_near, *cfg.near_store_radius_km, proj, m)
        far = _uniform_points(rng, n - n_near, proj, m)
        return np.vstack([near, far])

    def weights(n):
        w = rng.lognormal(0.0, 0.5, n)
        return w / w.sum()

    res_xy = zone_centres(cfg.n_residential_zones)
    work_xy = zone_centres(cfg.n_workplace_zones)

    n_h = cfg.n_transport_hubs
    n_h_near = min(n_h, 2 * cfg.hubs_near_each_store)
    hub_xy = np.vstack([
        _ring_points(rng, store_xy, n_h_near, *cfg.hub_near_store_radius_km, proj, m),
        _uniform_points(rng, n_h - n_h_near, proj, m)])

    other = _uniform_points(rng, cfg.n_other_commercial_centers, proj, m)
    for _ in range(200):  # keep competing retail centres away from the two stores
        d = np.minimum(np.linalg.norm(other - store_xy[0], axis=1),
                       np.linalg.norm(other - store_xy[1], axis=1))
        bad = d < cfg.other_center_min_store_distance_km
        if not bad.any():
            break
        other[bad] = _uniform_points(rng, int(bad.sum()), proj, m)

    return CityLayout(store_xy, res_xy, weights(len(res_xy)), work_xy, weights(len(work_xy)),
                      hub_xy, other, weights(len(other)))


# ----------------------------------------------------------------------------
# Devices
# ----------------------------------------------------------------------------
@dataclass
class Devices:
    ids: np.ndarray
    home: np.ndarray
    work: np.ndarray
    persona: np.ndarray
    hub_home: np.ndarray
    hub_work: np.ndarray
    transit: np.ndarray
    leave_mu: np.ndarray
    work_dwell_mu: np.ndarray
    work_dow_mask: np.ndarray
    segment: np.ndarray
    pref_a: np.ndarray
    visits_per_week: np.ndarray
    keep_prob: np.ndarray


class MobilitySimulator:
    def __init__(self, cfg: Config, proj: Projection, layout: CityLayout):
        self.cfg, self.proj, self.layout = cfg, proj, layout
        offset_str, _ = utc_offset_string(cfg)
        dates = [cfg.start_date + timedelta(days=i) for i in range(cfg.num_days)]
        hol = set(cfg.holidays)
        self.day_dow = np.array([d.weekday() for d in dates])
        self.day_weekend = np.array([d.weekday() >= 5 or d in hol for d in dates])
        self.day_str = np.array([d.isoformat() for d in dates], dtype=object)
        self.tod_str = np.array(
            [f" {s // 3600:02d}:{(s // 60) % 60:02d}:{s % 60:02d}{offset_str}" for s in range(86400)],
            dtype=object)
        self.profile = np.asarray(cfg.hourly_ping_activity, dtype=float)

    # ------------------------------------------------------------------
    def generate_chunk(self, chunk_idx: int, first_device: int, n_dev: int) -> pd.DataFrame:
        rng = np.random.default_rng(np.random.SeedSequence([self.cfg.seed, 1, chunk_idx]))
        devs = self._sample_devices(rng, first_device, n_dev)
        return self._simulate(rng, devs)

    # ------------------------------------------------------------------
    def _sample_devices(self, rng, first_index: int, n: int) -> Devices:
        cfg, lay, proj = self.cfg, self.layout, self.proj
        ids = make_device_ids(cfg.seed, first_index, n)

        zone = rng.choice(len(lay.res_w), size=n, p=lay.res_w)
        home = _clip_xy(lay.res_xy[zone] + rng.normal(0, cfg.residential_spread_km, (n, 2)), proj, 0.05)
        persona = rng.choice(3, size=n, p=np.asarray(cfg.persona_shares))
        has_work = persona != PERSONA_LOCAL

        d_hw = np.linalg.norm(home[:, None, :] - lay.work_xy[None, :, :], axis=2)
        wz = _pick_weighted(rng, lay.work_w[None, :] * np.exp(-d_hw / cfg.workplace_distance_decay_km))
        work = _clip_xy(lay.work_xy[wz] + rng.normal(0, cfg.workplace_spread_km, (n, 2)), proj, 0.05)
        work = np.where(has_work[:, None], work, home)

        def nearest_hub(xy):
            return np.linalg.norm(xy[:, None, :] - lay.hub_xy[None, :, :], axis=2).argmin(axis=1)

        hub_home, hub_work = nearest_hub(home), nearest_hub(work)
        commute_km = np.abs(home - work).sum(axis=1)
        transit = (has_work & (rng.random(n) < cfg.transit_share) & (hub_home != hub_work)
                   & (commute_km >= cfg.transit_min_commute_km))

        leave_mu = np.clip(rng.normal(cfg.weekday_leave_mean_h, cfg.weekday_leave_device_sd_h, n), 6.5, 10.5)
        work_dwell_mu = np.clip(rng.normal(cfg.work_dwell_mean_h, cfg.work_dwell_device_sd_h, n), 6.0, 10.0)

        ranks = rng.random((n, 5)).argsort(axis=1).argsort(axis=1)
        work_mask = np.zeros((n, 5), dtype=bool)
        work_mask[persona == PERSONA_COMMUTER] = True
        hyb = persona == PERSONA_HYBRID
        work_mask[hyb] = ranks[hyb] < cfg.hybrid_office_days

        # Store propensity: devices living/working near a store are likelier customers.
        sa, sb = lay.store_xy
        d_a = np.linalg.norm(home - sa, axis=1)
        d_b = np.linalg.norm(home - sb, axis=1)
        d_a = np.where(has_work, np.minimum(d_a, np.linalg.norm(work - sa, axis=1)), d_a)
        d_b = np.where(has_work, np.minimum(d_b, np.linalg.norm(work - sb, axis=1)), d_b)
        decay = cfg.store_distance_decay_km
        p_cust = np.clip(cfg.store_customer_base_prob
                         + cfg.store_customer_proximity_boost * np.exp(-np.minimum(d_a, d_b) / decay), 0, 0.95)
        is_cust = rng.random(n) < p_cust
        sh = cfg.store_segment_shares
        seg_w = np.column_stack([sh[0] * np.exp(-d_a / decay), sh[1] * np.exp(-d_b / decay),
                                 sh[2] * np.exp(-(d_a + d_b) / (2 * decay))]) + 1e-12
        segment = np.where(is_cust, _pick_weighted(rng, seg_w), SEG_NONE)

        pref_a = rng.beta(2.0, 2.0, n)
        visits = np.clip(rng.lognormal(math.log(cfg.retail_visits_per_week_median),
                                       cfg.retail_visits_per_week_sigma, n), 0.2, 7.0)
        keep = np.clip(rng.normal(cfg.device_keep_prob_mean, cfg.device_keep_prob_sd, n),
                       *cfg.device_keep_prob_bounds)
        return Devices(ids, home, work, persona, hub_home, hub_work, transit, leave_mu,
                       work_dwell_mu, work_mask, segment, pref_a, visits, keep)

    # ------------------------------------------------------------------
    def _choose_retail(self, rng, devs: Devices, dv, anchor_xy):
        cfg, lay = self.cfg, self.layout
        n = len(dv)
        seg = devs.segment[dv]
        loyal = rng.random(n) < cfg.store_loyalty
        pick_a = rng.random(n) < devs.pref_a[dv]
        store_idx = np.where(seg == SEG_A_ONLY, 0, np.where(seg == SEG_B_ONLY, 1, np.where(pick_a, 0, 1)))
        use_store = (seg != SEG_NONE) & loyal

        d = np.linalg.norm(anchor_xy[:, None, :] - lay.other_xy[None, :, :], axis=2)
        oi = _pick_weighted(rng, lay.other_w[None, :] * np.exp(-d / cfg.other_retail_decay_km) + 1e-12)
        xy_store = lay.store_xy[store_idx] + rng.normal(0, cfg.store_spread_km, (n, 2))
        xy_other = lay.other_xy[oi] + rng.normal(0, cfg.commercial_spread_km, (n, 2))
        return _clip_xy(np.where(use_store[:, None], xy_store, xy_other), self.proj, 0.0)

    def _retail_dwell(self, rng, n, weekend):
        cfg = self.cfg
        d = rng.lognormal(math.log(cfg.retail_dwell_median_min), cfg.retail_dwell_sigma, n)
        d = np.where(weekend, d * cfg.weekend_dwell_multiplier, d)
        return np.clip(d, *cfg.retail_dwell_bounds_min) * 60.0

    # ------------------------------------------------------------------
    def _simulate(self, rng, devs: Devices) -> pd.DataFrame:
        cfg, lay, proj = self.cfg, self.layout, self.proj
        S, H = N_SLOTS, 3600.0
        n_dev, nd = len(devs.ids), cfg.num_days
        n = n_dev * nd                                  # device-days
        dv = np.repeat(np.arange(n_dev), nd)            # device index of each device-day
        di = np.tile(np.arange(nd), n_dev)              # day index of each device-day
        weekend = self.day_weekend[di]
        dow = np.minimum(self.day_dow[di], 4)

        # ---- what does each device do today? ---------------------------------
        works_today = (~weekend) & devs.work_dow_mask[dv, dow]
        commute = works_today & (rng.random(n) >= cfg.weekday_absence_prob)
        transit = commute & devs.transit[dv]

        lam = devs.visits_per_week[dv]
        p1 = np.where(weekend, lam * cfg.weekend_retail_share / 2.0, lam * cfg.weekday_retail_share / 5.0)
        r1 = rng.random(n) < np.clip(p1, 0.0, 0.95)
        p2 = np.where(weekend, cfg.second_retail_prob_weekend, cfg.second_retail_prob_weekday)
        r2 = r1 & (rng.random(n) < p2)

        t_commute = np.clip(rng.normal(devs.leave_mu[dv], cfg.weekday_leave_daily_sd_h), 5.5, 10.5) * H
        t_errand = rng.uniform(cfg.weekday_errand_window_h[0], cfg.weekday_errand_window_h[1], n) * H
        t_weekend = np.clip(rng.normal(cfg.weekend_leave_mean_h, cfg.weekend_leave_sd_h, n),
                            cfg.weekend_leave_bounds_h[0], cfg.weekend_leave_bounds_h[1]) * H
        t_leave = np.where(commute, t_commute, np.where(weekend, t_weekend, t_errand))

        # ---- itinerary slots ---------------------------------------------------
        X = np.zeros((n, S)); Y = np.zeros((n, S))
        dwell = np.zeros((n, S)); mind = np.zeros((n, S))
        active = np.zeros((n, S), dtype=bool)
        home, work = devs.home[dv], devs.work[dv]
        hub_h, hub_w = lay.hub_xy[devs.hub_home[dv]], lay.hub_xy[devs.hub_work[dv]]
        anchor = np.where(commute[:, None], work, home)

        def put(slot, xy, act, dw):
            X[:, slot], Y[:, slot] = xy[:, 0], xy[:, 1]
            active[:, slot] = act
            dwell[:, slot] = np.where(act, dw, 0.0)

        def jit(sd):
            return rng.normal(0, sd, (n, 2))

        put(S_HOME0, home, True, 0.0)
        mind[:, S_HOME0] = t_leave
        put(S_HUB_H_OUT, hub_h + jit(cfg.hub_spread_km), transit, rng.uniform(3, 9, n) * 60)
        put(S_HUB_W_OUT, hub_w + jit(cfg.hub_spread_km), transit, rng.uniform(1, 4, n) * 60)
        put(S_WORK, work + jit(0.02), commute,
            np.clip(rng.normal(devs.work_dwell_mu[dv], cfg.work_dwell_daily_sd_h), 4.0, 10.0) * H)
        put(S_RETAIL1, self._choose_retail(rng, devs, dv, anchor), r1, self._retail_dwell(rng, n, weekend))
        put(S_RETAIL2, self._choose_retail(rng, devs, dv, anchor), r2, self._retail_dwell(rng, n, weekend))
        put(S_HUB_W_BACK, hub_w + jit(cfg.hub_spread_km), transit, rng.uniform(2, 6, n) * 60)
        put(S_HUB_H_BACK, hub_h + jit(cfg.hub_spread_km), transit, rng.uniform(2, 6, n) * 60)
        put(S_HOME_END, home, True, np.full(n, BIG))

        # ---- schedule: compact active slots, then travel, arrival and departure times ---
        def schedule(act):
            order = np.argsort(~act, axis=1, kind="stable")
            Xc, Yc = np.take_along_axis(X, order, 1), np.take_along_axis(Y, order, 1)
            dwc, mnc = np.take_along_axis(dwell, order, 1), np.take_along_axis(mind, order, 1)
            n_act = act.sum(axis=1)
            pad = np.arange(S)[None, :] >= n_act[:, None]
            Xc, Yc = np.where(pad, home[:, 0:1], Xc), np.where(pad, home[:, 1:2], Yc)
            dwc, mnc = np.where(pad, 0.0, dwc), np.where(pad, 0.0, mnc)

            # travel time = Manhattan route length / mode speed
            dist = np.abs(np.diff(Xc, axis=1)) + np.abs(np.diff(Yc, axis=1))
            prev, cur = order[:, :-1], order[:, 1:]
            is_tr = (((prev == S_HUB_H_OUT) & (cur == S_HUB_W_OUT))
                     | ((prev == S_HUB_W_BACK) & (cur == S_HUB_H_BACK)))
            sp_walk = rng.uniform(cfg.walk_speed_kmh[0], cfg.walk_speed_kmh[1], dist.shape)
            sp_veh = np.clip(rng.lognormal(math.log(cfg.vehicle_speed_median_kmh), cfg.vehicle_speed_sigma,
                                           dist.shape), *cfg.vehicle_speed_bounds_kmh)
            sp_tr = rng.uniform(cfg.transit_speed_kmh[0], cfg.transit_speed_kmh[1], dist.shape)
            speed = np.where(is_tr, sp_tr, np.where(dist < cfg.walk_threshold_km, sp_walk, sp_veh))
            travel = np.zeros((n, S))
            travel[:, 1:] = dist / speed * H

            arr = np.empty((n, S)); dep = np.empty((n, S))
            arr[:, 0] = -1.0
            dep[:, 0] = np.maximum(arr[:, 0] + dwc[:, 0], mnc[:, 0])
            for i in range(1, S):
                arr[:, i] = dep[:, i - 1] + travel[:, i]
                dep[:, i] = np.maximum(arr[:, i] + dwc[:, i], mnc[:, i])
            return Xc, Yc, arr, dep, n_act

        Xc, Yc, arr, dep, n_act = schedule(active)
        # With 24-hour pinging every day must end at home before midnight, otherwise the next
        # day (which starts at home) would look like a jump. Late retail stops are dropped.
        late = arr[np.arange(n), n_act - 1] > cfg.itinerary_end_by_hour * H
        if late.any():
            active[late, S_RETAIL1] = False
            active[late, S_RETAIL2] = False
            Xc, Yc, arr, dep, n_act = schedule(active)
        knots = np.stack([arr, dep], axis=2).reshape(n, 2 * S)   # arr0, dep0, arr1, dep1, ...
        hflag = rng.random((n, S)) < 0.5                         # which leg of the L-route goes first

        # ---- ping times: 24-hour grid, emission probability follows the daily profile --
        T = float(cfg.ping_interval_seconds)
        w0, w1 = cfg.active_start_hour * H, cfg.active_end_hour * H
        K = int((w1 - w0) // T) + 1
        t = (w0 + rng.uniform(0, T, (n, 1)) + np.arange(K)[None, :] * T
             + rng.uniform(-cfg.ping_jitter_fraction * T, cfg.ping_jitter_fraction * T, (n, K)))
        in_window = (t >= w0) & (t < w1)
        idx = (knots[:, None, :] <= t[:, :, None]).sum(axis=2)   # knots passed at each ping time
        moving = ((idx - 1) & 1) == 1                            # between two stops = travelling
        hour = np.clip((t // H).astype(np.int64), 0, 23)
        p_emit = (devs.keep_prob[dv][:, None] * self.profile[hour]
                  * np.where(moving, cfg.moving_ping_boost, 1.0))
        keep = in_window & (rng.random((n, K)) < np.minimum(p_emit, cfg.max_ping_keep_prob))

        rows, cols = np.nonzero(keep)                    # row-major => device, day, time order
        tk = t[rows, cols]
        k = idx[rows, cols] - 1
        j = k >> 1
        travelling = (k & 1) == 1
        jn = np.minimum(j + 1, S - 1)
        x0, y0, x1, y1 = Xc[rows, j], Yc[rows, j], Xc[rows, jn], Yc[rows, jn]
        dep_j, arr_n = dep[rows, j], arr[rows, jn]
        s = np.where(travelling, np.clip((tk - dep_j) / np.maximum(arr_n - dep_j, 1e-6), 0.0, 1.0), 0.0)
        ddx, ddy = x1 - x0, y1 - y0
        ax, ay = np.abs(ddx), np.abs(ddy)
        along = s * (ax + ay)
        hf = hflag[rows, j]
        mx = np.where(hf, np.minimum(along, ax), np.maximum(along - ay, 0.0))
        my = np.where(hf, np.maximum(along - ax, 0.0), np.minimum(along, ay))
        x = x0 + np.sign(ddx) * mx
        y = y0 + np.sign(ddy) * my

        # ---- GPS noise, boundary clipping, formatting ------------------------------
        m = len(tk)
        sigma = np.where(rng.random(m) < cfg.gps_outlier_prob,
                         cfg.gps_outlier_sigma_m, cfg.gps_noise_sigma_m) / 1000.0
        x = np.clip(x + rng.standard_normal(m) * sigma, 0.0, proj.width)
        y = np.clip(y + rng.standard_normal(m) * sigma, 0.0, proj.height)
        lat, lon = proj.to_deg(x, y)
        dec = cfg.coordinate_decimals
        lat = np.clip(np.round(lat, dec), cfg.lat_min, cfg.lat_max)
        lon = np.clip(np.round(lon, dec), cfg.lon_min, cfg.lon_max)
        ts = self.day_str[di[rows]] + self.tod_str[np.floor(tk).astype(np.int64)]

        return pd.DataFrame({"DeviceID": devs.ids[dv[rows]], "Latitude": lat,
                             "Longitude": lon, "Timestamp": ts})


# ----------------------------------------------------------------------------
# Driver
# ----------------------------------------------------------------------------
def _portable(conf: dict) -> dict:
    """Store the output path relative to the project folder when possible."""
    p = Path(conf["output_path"])
    try:
        conf["output_path"] = str(p.resolve().relative_to(Path(__file__).resolve().parent))
    except ValueError:
        conf["output_path"] = str(p)
    return conf


def generate(cfg: Config, quiet: bool = False) -> dict:
    cfg.validate()
    log = (lambda *a, **k: None) if quiet else (lambda *a, **k: print(*a, **k, flush=True))
    t_start = time.time()

    if cfg.geography_is_placeholder:
        log("!" * 78)
        log("WARNING: city bounds and Store A/B coordinates are ILLUSTRATIVE PLACEHOLDERS.")
        log("         Edit config.py and set geography_is_placeholder = False for real use.")
        log("!" * 78)
    if cfg.num_devices is None and not (SUPPORTED_RECORD_RANGE[0] <= cfg.target_records <= SUPPORTED_RECORD_RANGE[1]):
        log(f"NOTE: target_records={cfg.target_records:,} is outside the supported range "
            f"{SUPPORTED_RECORD_RANGE[0]:,}-{SUPPORTED_RECORD_RANGE[1]:,}; generating anyway.")

    proj = Projection(cfg)
    layout = build_layout(cfg, proj, np.random.default_rng(np.random.SeedSequence([cfg.seed, 0])))
    sim = MobilitySimulator(cfg, proj, layout)

    out = Path(cfg.output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".part")
    per_chunk = max(1, cfg.chunk_device_days // cfg.num_days)
    target = None if cfg.num_devices is not None else cfg.target_records

    total = devices_written = devices_generated = rows_generated = chunk_idx = 0
    log(f"Generating {'%d devices' % cfg.num_devices if target is None else '%s records' % format(target, ',')} "
        f"over {cfg.num_days} days (seed={cfg.seed}) -> {out}")
    with open(tmp, "w", newline="") as fh:
        fh.write("DeviceID,Latitude,Longitude,Timestamp\n")
        while True:
            if target is None:
                if devices_generated >= cfg.num_devices:
                    break
                n_dev = min(per_chunk, cfg.num_devices - devices_generated)
            else:
                remaining = target - total
                if remaining <= 0:
                    break
                n_dev = per_chunk
                if rows_generated:  # right-size the final chunk from observed rows/device
                    avg = rows_generated / devices_generated
                    n_dev = int(min(per_chunk, max(1, math.ceil(remaining / avg * 1.03) + 1)))
            df = sim.generate_chunk(chunk_idx, devices_generated, n_dev)
            devices_generated += n_dev
            rows_generated += len(df)
            if target is not None and total + len(df) > target:
                df = df.iloc[: target - total]          # trim only the tail of the last chunk
            if len(df):
                devices_written += df["DeviceID"].nunique()
            df.to_csv(fh, header=False, index=False, lineterminator="\n",
                      float_format=f"%.{cfg.coordinate_decimals}f")
            total += len(df)
            chunk_idx += 1
            goal = target if target is not None else None
            log(f"  chunk {chunk_idx:>4}: devices={devices_written:>8,}  records={total:>12,}"
                + (f"  ({100 * total / goal:5.1f}%)" if goal else ""))
    os.replace(tmp, out)

    elapsed = time.time() - t_start
    manifest = {
        "generator_version": GENERATOR_VERSION,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "records_written": total,
        "devices_written": devices_written,
        "chunks": chunk_idx,
        "elapsed_seconds": round(elapsed, 2),
        "config": _portable(asdict(cfg)),
    }
    man_path = out.with_name(out.stem + ".manifest.json")
    man_path.write_text(json.dumps(manifest, indent=2, default=str))
    log(f"Done: {total:,} records, {devices_written:,} devices in {elapsed:.1f}s")
    log(f"  data     : {out}\n  manifest : {man_path}")
    return manifest


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Generate synthetic GPS mobility data for GeoPulse.")
    p.add_argument("--records", type=int, help="target number of records (default: config.py)")
    p.add_argument("--devices", type=int, help="fix the device count instead of the record count")
    p.add_argument("--days", type=int, help="number of simulated days")
    p.add_argument("--start-date", type=date.fromisoformat, help="first day, YYYY-MM-DD")
    p.add_argument("--seed", type=int, help="random seed")
    p.add_argument("--ping-interval-min", type=float, help="nominal ping interval in minutes")
    p.add_argument("--output", type=Path, help="output CSV path")
    p.add_argument("--quiet", action="store_true", help="suppress progress output")
    return p.parse_args(argv)


def main(argv=None) -> int:
    a = parse_args(argv)
    over = {}
    if a.records is not None: over["target_records"] = a.records
    if a.devices is not None: over["num_devices"] = a.devices
    if a.days is not None: over["num_days"] = a.days
    if a.start_date is not None: over["start_date"] = a.start_date
    if a.seed is not None: over["seed"] = a.seed
    if a.ping_interval_min is not None: over["ping_interval_seconds"] = int(round(a.ping_interval_min * 60))
    if a.output is not None: over["output_path"] = a.output
    cfg = replace(Config(), **over)
    try:
        generate(cfg, quiet=a.quiet)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
