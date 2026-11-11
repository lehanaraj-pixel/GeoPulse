#!/usr/bin/env python3
"""
validate_data.py - streaming quality checks for the GeoPulse GPS dataset.

The CSV is read in chunks, so memory stays bounded (only per-device state and
row hashes for the duplicate check are kept). Nothing is removed or repaired:
every problem is counted and reported.

Checks: missing values, duplicate records, invalid lat/lon, invalid timestamps,
DeviceID format/contiguity, chronological order per device, implied-speed
plausibility (no teleporting), boundary violations, store catchment coverage,
unique devices and total records, plus 24-hour coverage (every hour populated,
overnight records, sleeping-hours vs daytime rate) and daily-pattern sanity checks
(commute-hour movement peaks, weekday vs weekend mornings, evening retail activity).

Usage
-----
    python validate_data.py                         # validates cfg.output_path
    python validate_data.py --input data/sample_gps_data.csv
Exit code is 0 when no check FAILS, 1 otherwise.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import Counter
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from config import Config, utc_offset_string

REQUIRED = ["DeviceID", "Latitude", "Longitude", "Timestamp"]
DEVICE_RE = r"^DEV_[0-9A-F]{16}$"
NA_TOKENS = {"", "nan", "NaN", "NAN", "null", "NULL", "None", "none", "NA", "N/A"}
R_EARTH_M = 6371008.8
EPOCH = date(1970, 1, 1)


def haversine_m(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = (np.sin((p2 - p1) / 2) ** 2
         + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2)
    return 2 * R_EARTH_M * np.arcsin(np.sqrt(a))


class Validator:
    def __init__(self, cfg: Config, start: date, days: int, holidays=()):
        self.cfg = cfg
        # holidays behave like weekends in the generator, so they must do so here as well
        self.hol_days = np.array(sorted((h - EPOCH).days for h in holidays), dtype=np.int64)
        self.offset_str, self.offset_s = utc_offset_string(cfg, start, days)
        self.day_lo = (start - EPOCH).days
        self.day_hi = self.day_lo + days - 1
        self.total = 0
        self.missing = Counter()
        self.non_numeric = Counter()
        self.out_of_range = Counter()
        self.ts_unparseable = self.ts_bad_offset = self.ts_out_of_range = 0
        self.bad_device_format = 0
        self.outside_bbox = 0
        self.chrono_viol = self.noncontig = self.speed_viol = 0
        self.max_speed = 0.0
        self.last: dict = {}             # device -> (ts, lat, lon)
        self.dev_counts: Counter = Counter()
        self.day_counts: Counter = Counter()
        self.tail_dev = None
        self.h_full, self.h_key, self.catch = [], [], []
        self.ts_min, self.ts_max = None, None
        self.pings_a = self.pings_b = self.pings_both = 0
        self.examples: list[str] = []
        # hourly profile state: row 0 = weekday, row 1 = weekend; columns = local hour 0..23
        self.hour_cnt = np.zeros((2, 24), dtype=np.int64)
        self.pair_cnt = np.zeros((2, 24), dtype=np.int64)   # consecutive-ping pairs (<= gap)
        self.move_cnt = np.zeros((2, 24), dtype=np.int64)   # ...of which the device moved
        self.catch_hour = np.zeros(24, dtype=np.int64)      # pings inside A or B per hour
        self.night_devs: set = set()

    def is_weekend(self, days):
        """True for Saturdays, Sundays and configured holidays (days = days since 1970-01-01)."""
        days = np.asarray(days)
        return (((days + 3) % 7) >= 5) | np.isin(days, self.hol_days)   # 1970-01-01 was a Thursday

    # ------------------------------------------------------------------
    def _note(self, msg: str):
        if len(self.examples) < 8:
            self.examples.append(msg)

    def process(self, df: pd.DataFrame):
        cfg = self.cfg
        n = len(df)
        self.total += n
        miss = {c: df[c].str.strip().isin(NA_TOKENS).to_numpy() for c in REQUIRED}
        for c in REQUIRED:
            self.missing[c] += int(miss[c].sum())

        lat = pd.to_numeric(df["Latitude"], errors="coerce").to_numpy(dtype=float)
        lon = pd.to_numeric(df["Longitude"], errors="coerce").to_numpy(dtype=float)
        ok_geo = np.ones(n, dtype=bool)
        for name, arr, lim in (("Latitude", lat, 90.0), ("Longitude", lon, 180.0)):
            nonnum = ~miss[name] & ~np.isfinite(arr)
            rng_bad = np.isfinite(arr) & (np.abs(arr) > lim)
            self.non_numeric[name] += int(nonnum.sum())
            self.out_of_range[name] += int(rng_bad.sum())
            ok_geo &= np.isfinite(arr) & ~rng_bad
            if rng_bad.any():
                self._note(f"{name} out of range, e.g. {arr[rng_bad][0]}")

        ts_raw = df["Timestamp"]
        parsed = pd.to_datetime(ts_raw, format="%Y-%m-%d %H:%M:%S%z", errors="coerce", utc=True)
        valid_ts = parsed.notna().to_numpy()
        self.ts_unparseable += int((~miss["Timestamp"] & ~valid_ts).sum())
        self.ts_bad_offset += int((valid_ts & ~ts_raw.str.endswith(self.offset_str).to_numpy()).sum())
        ts = np.zeros(n, dtype=np.int64)
        if valid_ts.any():
            ts[valid_ts] = (parsed[valid_ts].dt.tz_convert(None).to_numpy()
                            .astype("datetime64[s]").astype(np.int64))
        local = ts + self.offset_s
        day = local // 86400
        out_rng = valid_ts & ((day < self.day_lo) | (day > self.day_hi))
        self.ts_out_of_range += int(out_rng.sum())

        dev_ok_fmt = df["DeviceID"].str.match(DEVICE_RE).to_numpy()
        self.bad_device_format += int((~miss["DeviceID"] & ~dev_ok_fmt).sum())

        # Duplicate detection (hash-based; collision probability is negligible).
        self.h_full.append(pd.util.hash_pandas_object(df[REQUIRED], index=False).to_numpy())
        self.h_key.append(pd.util.hash_pandas_object(df[["DeviceID", "Timestamp"]], index=False).to_numpy())

        # Rows usable for geometric / temporal analysis (failures above are already counted).
        ok = ok_geo & valid_ts & ~miss["DeviceID"]
        if not ok.any():
            return
        dev = df["DeviceID"].to_numpy(dtype=object)[ok]
        la, lo, t = lat[ok], lon[ok], ts[ok]
        dy = day[ok]
        hr = (local[ok] % 86400) // 3600
        we = self.is_weekend(dy).astype(np.int64)
        self.hour_cnt += np.bincount(we * 24 + hr, minlength=48).reshape(2, 24)
        night = (hr >= cfg.overnight_hours[0]) & (hr < cfg.overnight_hours[1])
        if night.any():
            self.night_devs.update(pd.unique(dev[night]).tolist())

        self.ts_min = int(t.min()) if self.ts_min is None else min(self.ts_min, int(t.min()))
        self.ts_max = int(t.max()) if self.ts_max is None else max(self.ts_max, int(t.max()))
        for d, c in zip(*np.unique(dy, return_counts=True)):
            self.day_counts[int(d)] += int(c)

        out = ((la < cfg.lat_min) | (la > cfg.lat_max) | (lo < cfg.lon_min) | (lo > cfg.lon_max))
        self.outside_bbox += int(out.sum())

        # Chronology + implied speed within the chunk.
        if len(dev) > 1:
            same = dev[1:] == dev[:-1]
            dt = np.diff(t)
            self.chrono_viol += int((same & (dt < 0)).sum())
            mv = same & (dt > 0)
            if mv.any():
                dist = haversine_m(la[:-1][mv], lo[:-1][mv], la[1:][mv], lo[1:][mv])
                spd = dist / 1000.0 / (dt[mv] / 3600.0)
                self.speed_viol += int((spd > cfg.max_plausible_speed_kmh).sum())
                self.max_speed = max(self.max_speed, float(spd.max()))
                use = dt[mv] <= cfg.moving_max_gap_s            # "moving" = far apart, close in time
                key = (we[1:][mv] * 24 + hr[1:][mv])[use]
                self.pair_cnt += np.bincount(key, minlength=48).reshape(2, 24)
                self.move_cnt += np.bincount(key[dist[use] > cfg.moving_distance_m],
                                             minlength=48).reshape(2, 24)
        # Run boundaries: cross-chunk continuity, contiguity of each device's block.
        starts = np.flatnonzero(np.concatenate(([True], dev[1:] != dev[:-1])))
        ends = np.concatenate((starts[1:] - 1, [len(dev) - 1]))
        for s, e in zip(starts.tolist(), ends.tolist()):
            d = dev[s]
            prev = self.last.get(d)
            if prev is not None:
                if not (s == 0 and d == self.tail_dev):
                    self.noncontig += 1
                dt0 = int(t[s]) - prev[0]
                if dt0 < 0:
                    self.chrono_viol += 1
                    self._note(f"time goes backwards for {d}")
                elif dt0 > 0:
                    sp = haversine_m(prev[1], prev[2], la[s], lo[s]) / 1000.0 / (dt0 / 3600.0)
                    if sp > cfg.max_plausible_speed_kmh:
                        self.speed_viol += 1
                    self.max_speed = max(self.max_speed, float(sp))
            self.last[d] = (int(t[e]), float(la[e]), float(lo[e]))
            self.dev_counts[d] += e - s + 1
        self.tail_dev = dev[-1]

        # Catchments.
        in_a = haversine_m(la, lo, cfg.store_a[0], cfg.store_a[1]) <= cfg.catchment_radius_m
        in_b = haversine_m(la, lo, cfg.store_b[0], cfg.store_b[1]) <= cfg.catchment_radius_m
        self.pings_a += int(in_a.sum())
        self.pings_b += int(in_b.sum())
        self.pings_both += int((in_a & in_b).sum())
        sel = in_a | in_b
        if sel.any():
            self.catch_hour += np.bincount(hr[sel], minlength=24)
            self.catch.append(pd.DataFrame({"dev": dev[sel], "local": local[ok][sel],
                                            "a": in_a[sel], "b": in_b[sel]}))

    # ------------------------------------------------------------------
    def finalize(self) -> dict:
        full = np.concatenate(self.h_full) if self.h_full else np.array([], dtype=np.uint64)
        key = np.concatenate(self.h_key) if self.h_key else np.array([], dtype=np.uint64)
        self.dup_full = int(len(full) - len(np.unique(full)))
        self.dup_key = int(len(key) - len(np.unique(key)))
        self.h_full = self.h_key = []
        return self._catchment_stats()

    def _catchment_stats(self) -> dict:
        cfg = self.cfg
        empty = {"devices_a": 0, "devices_b": 0, "devices_both": 0, "devices_union": 0}
        if not self.catch:
            return empty
        c = pd.concat(self.catch, ignore_index=True)
        c["day"] = c["local"] // 86400
        c["hour"] = (c["local"] % 86400) // 3600
        c["weekend"] = self.is_weekend(c["day"].to_numpy())
        ca, cb = c[c["a"]], c[c["b"]]
        set_a, set_b = set(ca["dev"]), set(cb["dev"])
        both = set_a & set_b
        stats = {"devices_a": len(set_a), "devices_b": len(set_b), "devices_both": len(both),
                 "devices_union": len(set_a | set_b),
                 "devices_a_only": len(set_a - set_b), "devices_b_only": len(set_b - set_a)}
        stats["overlap_pct_of_a"] = 100 * len(both) / len(set_a) if set_a else 0.0
        stats["overlap_pct_of_b"] = 100 * len(both) / len(set_b) if set_b else 0.0
        stats["jaccard_pct"] = 100 * len(both) / len(set_a | set_b) if (set_a | set_b) else 0.0

        va = ca[["dev", "day"]].drop_duplicates()
        vb = cb[["dev", "day"]].drop_duplicates()
        n_a, n_b = va.groupby("dev").size(), vb.groupby("dev").size()
        stats["repeat_visitors_a"] = int((n_a >= 2).sum())
        stats["repeat_visitors_b"] = int((n_b >= 2).sum())
        if both:
            union_days = pd.concat([va, vb]).drop_duplicates().groupby("dev").size()
            idx = sorted(both)
            same_single_day = (n_a[idx] == 1) & (n_b[idx] == 1) & (union_days[idx] == 1)
            stats["both_on_different_days"] = int((~same_single_day).sum())
        else:
            stats["both_on_different_days"] = 0

        for name, sub in (("a", ca), ("b", cb)):
            daily = sub[["dev", "day"]].drop_duplicates().groupby("day").size()
            wk = self.is_weekend(daily.index.to_numpy())
            stats[f"daily_unique_{name}_weekday"] = float(daily[~wk].mean()) if (~wk).any() else float("nan")
            stats[f"daily_unique_{name}_weekend"] = float(daily[wk].mean()) if wk.any() else float("nan")
            hourly = sub[["dev", "day", "hour"]].drop_duplicates().groupby(["day", "hour"]).size()
            stats[f"hourly_unique_{name}_mean"] = float(hourly.mean())
            stats[f"hourly_unique_{name}_max"] = int(hourly.max())
            by_hour = hourly.groupby(level="hour").mean()
            stats[f"peak_hour_{name}"] = int(by_hour.idxmax())
        return stats


# ----------------------------------------------------------------------------
def load_manifest(path: Path):
    mp = path.with_name(path.stem + ".manifest.json")
    if mp.exists():
        try:
            return json.loads(mp.read_text())
        except Exception:  # noqa: BLE001
            return None
    return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Validate a GeoPulse GPS CSV.")
    ap.add_argument("--input", type=Path, help="CSV to validate (default: config output_path)")
    ap.add_argument("--expected-records", type=int, help="expected row count (default: manifest value)")
    ap.add_argument("--chunk-rows", type=int, help="rows per chunk")
    ap.add_argument("--json-report", type=Path, help="also write the results as JSON")
    ap.add_argument("--hourly-warn-only", action="store_true",
                    help="report 24-hour coverage / daily-pattern failures as warnings "
                         "(e.g. for files generated before 24-hour pinging existed)")
    a = ap.parse_args(argv)

    cfg = Config()
    try:
        cfg.validate()
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    path = a.input or Path(cfg.output_path)
    if not path.exists():
        print(f"ERROR: {path} not found", file=sys.stderr)
        return 2
    manifest = load_manifest(path)
    notes = []
    start, days = cfg.start_date, cfg.num_days
    holidays = tuple(cfg.holidays)
    expected = a.expected_records
    if manifest:
        mc = manifest["config"]
        start, days = date.fromisoformat(mc["start_date"]), int(mc["num_days"])
        holidays = tuple(date.fromisoformat(h) for h in mc.get("holidays", []))
        if expected is None:
            expected = manifest["records_written"]
        for k in ("store_a", "store_b", "lat_min", "lat_max", "lon_min", "lon_max", "catchment_radius_m"):
            if json.dumps(mc[k]) != json.dumps(getattr(cfg, k)):
                notes.append(f"manifest value for '{k}' differs from config.py - validating against config.py")
    if cfg.geography_is_placeholder:
        notes.append("geography_is_placeholder=True: bounds/stores are illustrative placeholders")

    header = pd.read_csv(path, nrows=0).columns.tolist()
    missing_cols = [c for c in REQUIRED if c not in header]
    if missing_cols:
        print(f"FAIL: missing required columns {missing_cols}; found {header}")
        return 1

    t0 = time.time()
    v = Validator(cfg, start, days, holidays)
    structural_error = None
    try:
        reader = pd.read_csv(path, usecols=REQUIRED, dtype=str, keep_default_na=False, na_filter=False,
                             chunksize=a.chunk_rows or cfg.validation_chunk_rows)
        for chunk in reader:
            v.process(chunk[REQUIRED])
    except pd.errors.ParserError as exc:
        structural_error = str(exc)
    cs = v.finalize()
    elapsed = time.time() - t0

    # ---------------- assemble checks ----------------
    checks = []

    def add(name, ok, detail, warn_only=False):
        checks.append((name, "PASS" if ok else ("WARN" if warn_only else "FAIL"), detail))

    add("CSV structure", structural_error is None, structural_error or "all rows parsed with 4 columns")
    if expected is not None:
        add("Total records vs expected", v.total == expected, f"{v.total:,} found, {expected:,} expected")
    add("Missing values", sum(v.missing.values()) == 0,
        ", ".join(f"{c}={v.missing[c]:,}" for c in REQUIRED))
    add("Duplicate records (identical rows)", v.dup_full == 0, f"{v.dup_full:,}")
    add("Duplicate (DeviceID, Timestamp) keys", v.dup_key == 0, f"{v.dup_key:,}")
    bad_ll = sum(v.non_numeric.values()) + sum(v.out_of_range.values())
    add("Valid latitude/longitude", bad_ll == 0,
        f"non-numeric={sum(v.non_numeric.values()):,}, outside [-90,90]/[-180,180]={sum(v.out_of_range.values()):,}")
    bad_ts = v.ts_unparseable + v.ts_bad_offset + v.ts_out_of_range
    add("Valid timestamps", bad_ts == 0,
        f"unparseable={v.ts_unparseable:,}, offset != {v.offset_str}={v.ts_bad_offset:,}, "
        f"outside {start}..+{days}d={v.ts_out_of_range:,}")
    add("DeviceID format", v.bad_device_format == 0, f"{v.bad_device_format:,} IDs not matching {DEVICE_RE}")
    add("Chronological order per device", v.chrono_viol == 0, f"{v.chrono_viol:,} violations")
    add("Device records contiguous", v.noncontig == 0,
        f"{v.noncontig:,} devices split across several blocks", warn_only=True)
    add(f"Implied speed <= {cfg.max_plausible_speed_kmh:g} km/h (no teleporting)", v.speed_viol == 0,
        f"{v.speed_viol:,} violations, max implied {v.max_speed:,.1f} km/h")
    add("Inside configured city bounds", v.outside_bbox == 0, f"{v.outside_bbox:,} records outside")
    add(f"Store A catchment devices >= {cfg.min_devices_per_store}",
        cs["devices_a"] >= cfg.min_devices_per_store, f"{cs['devices_a']:,}")
    add(f"Store B catchment devices >= {cfg.min_devices_per_store}",
        cs["devices_b"] >= cfg.min_devices_per_store, f"{cs['devices_b']:,}")
    add(f"Devices seen in both catchments >= {cfg.min_devices_in_both}",
        cs["devices_both"] >= cfg.min_devices_in_both, f"{cs['devices_both']:,}")

    # ---------------- 24-hour coverage and daily-pattern checks ----------------
    hw = a.hourly_warn_only
    nan = float("nan")
    lo_h, hi_h = cfg.overnight_hours
    rec_h = v.hour_cnt.sum(axis=0)
    tot_h = int(rec_h.sum())
    empty = [h for h in range(24) if rec_h[h] == 0]
    add("Hourly coverage: all 24 hours have records", not empty,
        f"{24 - len(empty)}/24 hours populated" + (f"; empty hours {empty}" if empty else ""), warn_only=hw)
    night_n = int(rec_h[lo_h:hi_h].sum())
    night_share = night_n / tot_h if tot_h else 0.0
    add(f"Overnight records ({lo_h:02d}-{hi_h:02d}h) >= {cfg.min_overnight_share:.0%} of all",
        night_share >= cfg.min_overnight_share, f"{night_n:,} records = {night_share:.1%}", warn_only=hw)
    dev_total = len(v.dev_counts)
    dev_night = len(v.night_devs)
    dev_share = dev_night / dev_total if dev_total else 0.0
    add(f"Devices with overnight records >= {cfg.min_devices_with_overnight_share:.0%}",
        dev_share >= cfg.min_devices_with_overnight_share,
        f"{dev_night:,} of {dev_total:,} devices ({dev_share:.1%})", warn_only=hw)
    night_rate, day_rate = float(rec_h[lo_h:hi_h].mean()), float(rec_h[7:22].mean())
    ratio = night_rate / day_rate if day_rate else nan
    add(f"Sleeping hours quieter than 07-21h (ratio <= {cfg.max_overnight_to_day_ratio:.0%})",
        bool(np.isfinite(ratio) and ratio <= cfg.max_overnight_to_day_ratio),
        f"{night_rate:,.0f} vs {day_rate:,.0f} records/hour, ratio {ratio:.1%}", warn_only=hw)

    def mshare(weeks, hours):
        p = sum(int(v.pair_cnt[w, h]) for w in weeks for h in hours)
        m = sum(int(v.move_cnt[w, h]) for w in weeks for h in hours)
        return m / p if p else nan

    def pattern(name, vals, cond, detail):
        if all(np.isfinite(x) for x in vals):
            add(name, bool(cond()), detail, warn_only=hw)
        else:
            add(name, False, "insufficient data", warn_only=True)

    commute_sh = mshare((0,), (7, 8, 9, 17, 18, 19))
    night_sh = mshare((0, 1), range(lo_h, hi_h))
    midday_sh = mshare((0,), range(10, 16))
    wd_am, we_am = mshare((0,), (7, 8, 9)), mshare((1,), (7, 8, 9))
    pattern(f"Commute-hour movement >= {cfg.commute_to_night_movement_ratio:g}x overnight movement",
            (commute_sh, night_sh),
            lambda: commute_sh >= cfg.commute_to_night_movement_ratio * max(night_sh, 0.005),
            f"moving share {commute_sh:.1%} (weekday 07-09h, 17-19h) vs {night_sh:.1%} overnight")
    pattern("Commute-hour movement > weekday midday (workplace hours) movement",
            (commute_sh, midday_sh), lambda: commute_sh > midday_sh,
            f"{commute_sh:.1%} vs {midday_sh:.1%} (weekday 10-15h)")
    pattern("Weekday morning movement > weekend morning movement",
            (wd_am, we_am), lambda: wd_am > we_am,
            f"{wd_am:.1%} weekday vs {we_am:.1%} weekend (07-09h)")
    ch = v.catch_hour
    ev_rate, ch_night = float(ch[17:22].mean()), float(ch[lo_h:hi_h].mean())
    pattern("Store catchments busier in the evening (17-21h) than overnight",
            (ev_rate, ch_night) if ch.sum() else (nan,), lambda: ev_rate > ch_night,
            f"{ev_rate:,.0f} vs {ch_night:,.0f} catchment pings/hour")

    n_fail = sum(1 for c in checks if c[1] == "FAIL")
    n_warn = sum(1 for c in checks if c[1] == "WARN")
    n_dev = len(v.dev_counts)

    line = "=" * 78
    print(line + "\n GEOPULSE DATA VALIDATION REPORT\n" + line)
    print(f" File            : {path}")
    print(f" Validation time : {elapsed:.1f}s")
    for note in notes:
        print(f" NOTE            : {note}")
    print("\n--- Dataset summary " + "-" * 58)
    print(f" Total records   : {v.total:,}")
    print(f" Unique devices  : {n_dev:,}")
    if n_dev:
        counts = np.array(list(v.dev_counts.values()))
        print(f" Records/device  : min {counts.min():,} | median {int(np.median(counts)):,} | max {counts.max():,}")
    if v.ts_min is not None:
        fmt = lambda s: pd.Timestamp(s + v.offset_s, unit="s").strftime("%Y-%m-%d %H:%M:%S")
        print(f" Time span (IST) : {fmt(v.ts_min)} -> {fmt(v.ts_max)}  ({len(v.day_counts)} days with data)")
        dc = np.array([v.day_counts[d] for d in sorted(v.day_counts)])
        print(f" Records/day     : min {dc.min():,} | mean {int(dc.mean()):,} | max {dc.max():,}")
    print(f" Bounds checked  : lat {cfg.lat_min}..{cfg.lat_max}, lon {cfg.lon_min}..{cfg.lon_max}")

    print("\n--- Catchment coverage (radius %g m) %s" % (cfg.catchment_radius_m, "-" * 36))
    print(f" Pings inside    : Store A {v.pings_a:,} | Store B {v.pings_b:,} | overlap zone {v.pings_both:,}"
          f"  ({100 * (v.pings_a + v.pings_b - v.pings_both) / max(v.total, 1):.2f}% of all pings in A or B)")
    if cs["devices_union"]:
        print(f" Unique devices  : A {cs['devices_a']:,} | B {cs['devices_b']:,} | both {cs['devices_both']:,} "
              f"| A only {cs['devices_a_only']:,} | B only {cs['devices_b_only']:,}")
        print(f" Overlap         : {cs['overlap_pct_of_a']:.1f}% of A visitors also in B | "
              f"{cs['overlap_pct_of_b']:.1f}% of B visitors also in A | Jaccard {cs['jaccard_pct']:.1f}%")
        print(f" Repeat visitors : A {cs['repeat_visitors_a']:,} | B {cs['repeat_visitors_b']:,} "
              f"(>=2 distinct days) | both stores on different days: {cs['both_on_different_days']:,}")
        for s in ("a", "b"):
            print(f" Store {s.upper()} traffic   : daily unique visitors weekday {cs[f'daily_unique_{s}_weekday']:.1f} / "
                  f"weekend {cs[f'daily_unique_{s}_weekend']:.1f} | hourly unique mean "
                  f"{cs[f'hourly_unique_{s}_mean']:.1f}, max {cs[f'hourly_unique_{s}_max']} | peak hour {cs[f'peak_hour_{s}']:02d}:00")

    if tot_h:
        print("\n--- Hourly profile (IST) " + "-" * 53)
        print(" Hour   Records  Share  Moving%wkday  Moving%wkend  Catchment  ")
        for h in range(24):
            share = rec_h[h] / tot_h
            mv = [f"{100 * v.move_cnt[w, h] / v.pair_cnt[w, h]:5.1f}" if v.pair_cnt[w, h] else "  n/a"
                  for w in (0, 1)]
            print(f" {h:02d}:00 {rec_h[h]:>9,} {share:6.1%}  {mv[0]:>11}  {mv[1]:>12}  {v.catch_hour[h]:>9,}  "
                  + "#" * int(round(share * 250)))

    print("\n--- Checks " + "-" * 67)
    for name, status, detail in checks:
        print(f" [{status}] {name:<52} {detail}")
    if v.examples:
        print("\n Examples of problems found:")
        for e in v.examples:
            print(f"   - {e}")
    print("\n" + line)
    print(f" RESULT: {'FAILED' if n_fail else 'PASSED'}  ({len(checks) - n_fail - n_warn} passed, "
          f"{n_warn} warnings, {n_fail} failed)")
    print(line)

    if a.json_report:
        a.json_report.write_text(json.dumps({
            "file": str(path), "total_records": v.total, "unique_devices": n_dev,
            "checks": [{"name": n, "status": s, "detail": d} for n, s, d in checks],
            "catchment": cs}, indent=2, default=str))
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
