"""
config.py - single source of truth for the GeoPulse synthetic GPS generator
and validator.

Edit the defaults below, or override a subset from the command line
(see ``python generate_gps_data.py --help``).

!! ACTION REQUIRED BEFORE USING THE DATA FOR REAL ANALYSIS !!
The project brief did not specify the city bounding box or the coordinates of
Store A and Store B, so the values below are ILLUSTRATIVE PLACEHOLDERS. They do
not describe real stores. Replace them with your own values and then set
``geography_is_placeholder = False`` (the generator prints a warning and records
the flag in the manifest while it is True).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

BASE_DIR = Path(__file__).resolve().parent

#: Record volume the project is designed for (a warning is printed outside it).
SUPPORTED_RECORD_RANGE = (100_000, 10_000_000)

#: Shipped ILLUSTRATIVE placeholders (not real stores). Kept in one place so that
#: Config.validate() can refuse ``geography_is_placeholder=False`` while they are still in use.
PLACEHOLDER_BOUNDS = (12.9800, 13.1200, 80.1500, 80.3000)   # lat_min, lat_max, lon_min, lon_max
PLACEHOLDER_STORE_A = (13.0500, 80.2200)                     # (lat, lon)
PLACEHOLDER_STORE_B = (13.0530, 80.2260)                     # (lat, lon)


@dataclass(frozen=True)
class Config:
    # ------------------------------------------------------------------
    # Reproducibility
    # ------------------------------------------------------------------
    # Same seed + same configuration (including chunk_device_days) => identical file.
    seed: int = 42

    # ------------------------------------------------------------------
    # Volume and time span
    # ------------------------------------------------------------------
    target_records: int = 1_000_000          # default dataset size
    num_devices: int | None = None           # if set, overrides target_records
    num_days: int = 14                       # >= 14 recommended for weekly trends
    start_date: date = date(2026, 1, 5)      # synthetic calendar; 2026-01-05 is a Monday
    timezone: str = "Asia/Kolkata"           # timestamps are written with the +05:30 offset
    holidays: tuple[date, ...] = ()          # dates that behave like weekends

        # ------------------------------------------------------------------
    # Geography (Bengaluru - Indiranagar study area)
    # ------------------------------------------------------------------
    lat_min: float = 12.9400
    lat_max: float = 13.0200
    lon_min: float = 77.6000
    lon_max: float = 77.6900

    # Store A: Third Wave Coffee - CMH Indiranagar
    store_a: tuple[float, float] = (12.978973, 77.645270)

    # Store B: Beanlore - Indiranagar
    store_b: tuple[float, float] = (12.979005, 77.643732)

    catchment_radius_m: float = 500.0
    geography_is_placeholder: bool = False

    # ------------------------------------------------------------------
    # City layout (generated from the seed inside the bounding box)
    # ------------------------------------------------------------------
    n_residential_zones: int = 14
    n_workplace_zones: int = 8
    n_other_commercial_centers: int = 6      # competing retail areas besides Store A/B
    n_transport_hubs: int = 6
    hubs_near_each_store: int = 1            # hubs placed close to each store
    zone_share_near_stores: float = 0.35     # share of residential/work zones near the stores
    near_store_radius_km: tuple[float, float] = (0.5, 3.0)
    hub_near_store_radius_km: tuple[float, float] = (0.3, 0.9)
    other_center_min_store_distance_km: float = 1.5
    boundary_margin_km: float = 0.35         # keeps zone centres away from the bbox edge
    residential_spread_km: float = 0.9
    workplace_spread_km: float = 0.45
    commercial_spread_km: float = 0.15
    store_spread_km: float = 0.03            # where inside the store/mall a visit is located
    hub_spread_km: float = 0.04

    # ------------------------------------------------------------------
    # Population behaviour
    # ------------------------------------------------------------------
    persona_shares: tuple[float, float, float] = (0.60, 0.15, 0.25)  # commuter, hybrid, local
    hybrid_office_days: int = 3
    weekday_absence_prob: float = 0.05
    transit_share: float = 0.45              # commuters who route via transport hubs
    transit_min_commute_km: float = 2.0
    workplace_distance_decay_km: float = 8.0

    # Store propensity
    store_customer_base_prob: float = 0.12       # chance of being a store customer anywhere
    store_customer_proximity_boost: float = 0.50 # extra chance for devices living/working nearby
    store_distance_decay_km: float = 3.0
    store_segment_shares: tuple[float, float, float] = (0.40, 0.35, 0.25)  # A-only, B-only, both
    store_loyalty: float = 0.85                  # share of trips going to the device's store(s)
    other_retail_decay_km: float = 4.0
    retail_visits_per_week_median: float = 1.4
    retail_visits_per_week_sigma: float = 0.55
    weekday_retail_share: float = 0.45           # of weekly retail trips happening Mon-Fri
    weekend_retail_share: float = 0.55
    second_retail_prob_weekday: float = 0.15
    second_retail_prob_weekend: float = 0.30

    # ------------------------------------------------------------------
    # Daily timing (hours of the day unless stated otherwise)
    # ------------------------------------------------------------------
    weekday_leave_mean_h: float = 8.5
    weekday_leave_device_sd_h: float = 0.6
    weekday_leave_daily_sd_h: float = 0.25
    work_dwell_mean_h: float = 8.5
    work_dwell_device_sd_h: float = 0.5
    work_dwell_daily_sd_h: float = 0.3
    weekday_errand_window_h: tuple[float, float] = (10.0, 20.0)   # includes evening retail
    weekend_leave_mean_h: float = 12.5
    weekend_leave_sd_h: float = 1.8
    weekend_leave_bounds_h: tuple[float, float] = (9.0, 19.5)
    retail_dwell_median_min: float = 38.0
    retail_dwell_sigma: float = 0.5
    retail_dwell_bounds_min: tuple[float, float] = (8.0, 180.0)
    weekend_dwell_multiplier: float = 1.5

    # ------------------------------------------------------------------
    # Travel speeds (km/h). Routes follow an L-shaped street grid.
    # ------------------------------------------------------------------
    walk_threshold_km: float = 0.8
    walk_speed_kmh: tuple[float, float] = (3.8, 5.2)
    vehicle_speed_median_kmh: float = 20.0
    vehicle_speed_sigma: float = 0.25
    vehicle_speed_bounds_kmh: tuple[float, float] = (12.0, 35.0)
    transit_speed_kmh: tuple[float, float] = (28.0, 40.0)

    # ------------------------------------------------------------------
    # GPS ping behaviour
    # ------------------------------------------------------------------
    ping_interval_seconds: int = 900         # nominal grid spacing (>= 60)
    ping_jitter_fraction: float = 0.30       # +/- fraction of the interval, must be < 0.5
    active_start_hour: float = 0.0           # pings are emitted inside this daily window;
    active_end_hour: float = 24.0            # the default is the full 24 hours
    device_keep_prob_mean: float = 0.65      # per-device probability a grid ping is emitted
    device_keep_prob_sd: float = 0.15
    device_keep_prob_bounds: tuple[float, float] = (0.25, 0.95)
    # Relative ping-emission rate for each local hour 00..23 (multiplies the device's keep
    # probability): quiet while asleep, commuting peaks, steady daytime, evening retail bump.
    hourly_ping_activity: tuple[float, ...] = (
        0.15, 0.12, 0.10, 0.10, 0.12, 0.20,   # 00-05  sleeping hours
        0.60, 1.00, 1.20, 1.00, 0.90, 0.90,   # 06-11  morning commute peak, then workplace hours
        1.00, 0.90, 0.90, 0.90, 1.00, 1.20,   # 12-17  daytime, evening commute begins
        1.20, 1.10, 1.00, 0.80, 0.50, 0.30)   # 18-23  commute / evening retail, winding down
    moving_ping_boost: float = 1.5           # extra emission probability while travelling
    max_ping_keep_prob: float = 0.98
    itinerary_end_by_hour: float = 23.5      # every day's itinerary must finish at home by then
    gps_noise_sigma_m: float = 10.0
    gps_outlier_prob: float = 0.015
    gps_outlier_sigma_m: float = 60.0
    coordinate_decimals: int = 6

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------
    output_path: Path = BASE_DIR / "data" / "gps_data.csv"
    chunk_device_days: int = 15_000          # device-days simulated per chunk (memory control)

    # ------------------------------------------------------------------
    # Validation thresholds
    # ------------------------------------------------------------------
    validation_chunk_rows: int = 250_000
    min_devices_per_store: int = 20          # unique devices that must appear in each catchment
    min_devices_in_both: int = 5             # unique devices that must appear in both catchments
    max_plausible_speed_kmh: float = 150.0   # implied speed between consecutive pings
    # 24-hour coverage / daily-pattern checks
    overnight_hours: tuple[int, int] = (0, 6)       # [start, end) local hours counted as overnight
    min_overnight_share: float = 0.02               # overnight records as a share of all records
    min_devices_with_overnight_share: float = 0.90  # devices with >= 1 overnight record
    max_overnight_to_day_ratio: float = 0.50        # overnight rate/hour vs 07-21h rate/hour
    commute_to_night_movement_ratio: float = 2.0    # commute-hour vs overnight moving share
    moving_distance_m: float = 150.0                # consecutive pings farther apart = "moving"
    moving_max_gap_s: float = 1800.0                # ...if they are at most this far apart in time

    # ------------------------------------------------------------------
    def validate(self) -> None:
        errs: list[str] = []
        if not (-90 <= self.lat_min < self.lat_max <= 90):
            errs.append("lat_min/lat_max must satisfy -90 <= lat_min < lat_max <= 90")
        if not (-180 <= self.lon_min < self.lon_max <= 180):
            errs.append("lon_min/lon_max must satisfy -180 <= lon_min < lon_max <= 180")
        for name, (lat, lon) in (("store_a", self.store_a), ("store_b", self.store_b)):
            if not (self.lat_min <= lat <= self.lat_max and self.lon_min <= lon <= self.lon_max):
                errs.append(f"{name}={(lat, lon)} lies outside the configured city bounds")
        if tuple(self.store_a) == tuple(self.store_b):
            errs.append("store_a and store_b must be different locations")
        if self.catchment_radius_m <= 0:
            errs.append("catchment_radius_m must be > 0")
        if self.target_records < 1:
            errs.append("target_records must be >= 1")
        if self.num_devices is not None and self.num_devices < 1:
            errs.append("num_devices must be >= 1 when set")
        if self.num_days < 1:
            errs.append("num_days must be >= 1")
        if self.ping_interval_seconds < 60:
            errs.append("ping_interval_seconds must be >= 60")
        if not (0 <= self.ping_jitter_fraction < 0.5):
            errs.append("ping_jitter_fraction must be in [0, 0.5)")
        if not (0 <= self.active_start_hour < self.active_end_hour <= 24.0):
            errs.append("need 0 <= active_start_hour < active_end_hour <= 24")
        if len(self.hourly_ping_activity) != 24 or min(self.hourly_ping_activity) < 0 \
                or max(self.hourly_ping_activity) <= 0:
            errs.append("hourly_ping_activity needs 24 non-negative values, at least one > 0")
        if not (20.0 <= self.itinerary_end_by_hour <= 24.0):
            errs.append("itinerary_end_by_hour must be between 20 and 24")
        if abs(sum(self.persona_shares) - 1) > 1e-6:
            errs.append("persona_shares must sum to 1")
        if abs(sum(self.store_segment_shares) - 1) > 1e-6:
            errs.append("store_segment_shares must sum to 1")
        if min(self.n_residential_zones, self.n_workplace_zones,
               self.n_other_commercial_centers, self.n_transport_hubs) < 2:
            errs.append("each zone/hub count must be >= 2")
        if not (0 < self.hybrid_office_days <= 5):
            errs.append("hybrid_office_days must be in 1..5")
        if self.chunk_device_days < self.num_days:
            errs.append("chunk_device_days must be >= num_days")
        if not self.geography_is_placeholder:
            still = []
            if (self.lat_min, self.lat_max, self.lon_min, self.lon_max) == PLACEHOLDER_BOUNDS:
                still.append("city bounds")
            if tuple(self.store_a) == PLACEHOLDER_STORE_A:
                still.append("store_a")
            if tuple(self.store_b) == PLACEHOLDER_STORE_B:
                still.append("store_b")
            if still:
                errs.append("geography_is_placeholder=False but " + ", ".join(still)
                            + " still equal the shipped placeholder values - supply real coordinates")
        try:
            ZoneInfo(self.timezone)
        except Exception as exc:  # noqa: BLE001
            errs.append(f"unknown timezone {self.timezone!r}: {exc}")
        if errs:
            raise ValueError("Invalid configuration:\n  - " + "\n  - ".join(errs))


def utc_offset_string(cfg: Config, start: date | None = None, days: int | None = None) -> tuple[str, int]:
    """Return ("+05:30", 19800) for the configured zone; reject date ranges with DST changes."""
    tz = ZoneInfo(cfg.timezone)
    start = start or cfg.start_date
    days = days or cfg.num_days
    offsets = set()
    for i in range(days):
        d = start + timedelta(days=i)
        for hour in (0, 12, 23):
            offsets.add(datetime(d.year, d.month, d.day, hour, tzinfo=tz).utcoffset())
    if len(offsets) != 1:
        raise ValueError("A UTC-offset change (DST) inside the date range is not supported")
    secs = int(offsets.pop().total_seconds())
    sign = "+" if secs >= 0 else "-"
    a = abs(secs)
    return f"{sign}{a // 3600:02d}:{(a % 3600) // 60:02d}", secs
