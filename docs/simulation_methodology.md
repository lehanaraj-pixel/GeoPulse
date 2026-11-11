# GeoPulse – Simulation Methodology

This document explains how `generate_gps_data.py` turns the settings in `config.py` into a realistic synthetic GPS
mobility dataset. Values quoted as "default" are the shipped defaults in `config.py`; every one of them is editable.

> The model is **plausible, not calibrated** to any real city or any real retailer. It is designed to produce data
> with realistic structure (commutes, dwell, weekday/weekend differences, sparse and noisy pings) for developing and
> testing the pipeline, not to predict real footfall.

## 1. Design goals

| Goal | How it is met |
|------|---------------|
| No independent random points | Every ping is a point on a device's continuous itinerary (home → ... → home). |
| No teleporting | Positions are interpolated between stops using travel time = route length / speed; the validator checks implied speed. |
| Reproducible | Fixed seed + fixed configuration ⇒ byte-identical CSV. |
| Scalable | Devices are simulated in chunks; each chunk is vectorised with NumPy and appended to the CSV. |
| Useful for store analytics | A configurable share of the city is placed near Store A and Store B, and devices have store-specific behaviour, so catchments receive enough traffic and overlap. |
| Configurable geography | Bounding box, Store A, Store B and catchment radius live only in `config.py`. |

## 2. Pipeline

```
config.py ──► city layout (seeded) ──► for each chunk of devices:
                                          1. sample device attributes
                                          2. build daily itineraries (per device-day)
                                          3. schedule times (travel + dwell)
                                          4. sample ping times (24 h grid, hourly profile)
                                          5. interpolate positions + GPS noise
                                          6. format DeviceID / Timestamp → append rows to CSV
                       ──► manifest.json ──► validate_data.py
```

## 3. Coordinate system

Internally the city is a flat kilometre grid anchored at the south-west corner of the bounding box
(`x` east, `y` north, spherical Earth radius 6371.0088 km, longitude scaled by the cosine of the mid latitude). Output
coordinates are converted back to degrees and rounded to 6 decimals. Over a city-sized box the projection error is
far below the GPS noise. The validator measures distances with the haversine formula, so catchment membership is
computed independently of the generator's projection.

## 4. City layout

Drawn once per run from `SeedSequence([seed, 0])`, so it does not depend on chunking.

| Element | Default count | Placement |
|---------|---------------|-----------|
| Residential zones | 14 | 35 % within 0.5–3.0 km of Store A or B (alternating), the rest uniform in the box |
| Workplace zones | 8 | same rule as residential |
| Transport hubs | 6 | 1 hub 0.3–0.9 km from each store, the rest uniform |
| Other commercial centres | 6 | uniform, but at least 1.5 km from both stores (competing retail) |
| Store A / Store B | 2 | exactly the configured coordinates |

Zone centres stay at least `boundary_margin_km` (0.35 km) away from the box edge. Each zone gets a log-normal weight
(popularity). Individual homes, workplaces and shop visits are scattered around zone centres with a Gaussian spread
(residential 0.9 km, workplace 0.45 km, commercial 0.15 km, store 0.03 km, hub 0.04 km).

## 5. Devices

Per device, once, from the chunk's random stream:

- **Anonymous ID:** a bijective 64-bit mix (splitmix64) of the device counter and the seed, formatted `DEV_<16 hex>`.
- **Home:** residential zone drawn by weight, plus Gaussian scatter.
- **Persona:** commuter 60 %, hybrid 15 % (office on 3 random weekdays), local 25 % (no workplace).
- **Workplace** (commuter/hybrid): workplace zone drawn by weight × `exp(-distance/8 km)` (gravity model).
- **Transit use:** 45 % of workers whose commute is ≥ 2 km and whose home and work have different nearest hubs
  route via those hubs.
- **Habits:** typical weekday leave time (mean 08:30, device SD 0.6 h) and work duration (mean 8.5 h, device SD 0.5 h).
- **Retail rate:** weekly shop visits, log-normal (median 1.4, σ 0.55, clipped 0.2–7).
- **Ping emission:** device-specific keep probability, normal(0.65, 0.15) clipped to 0.25–0.95 – some phones report more than others.

### Store segments

Each device is a *store customer* with probability `0.12 + 0.50·exp(-d/3 km)`, where `d` is the distance from its
home (or workplace, if closer) to the nearest store. Customers are split into **A-only (40 %), B-only (35 %) or both
(25 %)**, re-weighted by proximity to each store. Everyone else is **neither** and shops only at other commercial
centres. A customer sends 85 % of its shop trips to its store(s) and the rest to other centres; a "both" device
chooses A or B per trip (preference ~ Beta(2, 2)), so it visits both stores mostly on different days and
occasionally on the same day.

## 6. Daily itineraries

Each device-day is a sequence of stops chosen from nine chronologically ordered slots:

```
home → hub → hub → WORK → retail 1 → retail 2 → hub → hub → home
        (only when commuting by transit)              (only when commuting by transit)
```

Inactive slots are removed, leaving e.g. `home → work → home` or `home → shop → shop → home`. Every day starts and
ends at home, so consecutive days join seamlessly.

| Day type | What happens |
|----------|--------------|
| Weekday, working | Leave ~08:30 (daily SD 15 min, clipped 05:30–10:30), optional hub legs (waits 1–9 min), work ~8.5 h (clipped 4–10 h), optional shop stop on the way home, home. 5 % of workers stay out of the office on any day. |
| Weekday, not working (locals, hybrids at home, absentees) | Optional errand starting uniformly between 10:00 and 20:00 (includes evening retail). |
| Weekend / holiday | Optional trip starting around 12:30 (SD 1.8 h, clipped 09:00–19:30), longer dwell. |

Shop trips per device-day: probability `weekly_rate × 0.45 / 5` on weekdays and `weekly_rate × 0.55 / 2` on weekends
(so weekends are busier per day); a second stop follows with probability 15 % (weekday) / 30 % (weekend). Shop dwell
is log-normal (median 38 min, σ 0.5, clipped 8–180 min, ×1.5 on weekends).

**Midnight guard:** a day must be back home by 23:30 (`itinerary_end_by_hour`). If late errands would breach that, the
shop stops of that day are dropped and the day is rescheduled.

## 7. Scheduling and movement

Times are computed stop by stop: *arrival = previous departure + travel time*, *departure = arrival + dwell* (home
departure and some others are anchored to the sampled leave time).

- **Route:** an L-shaped street-grid path (east–west then north–south, or the reverse, chosen at random per leg).
  Route length is the Manhattan distance.
- **Speed:** walking 3.8–5.2 km/h for legs under 0.8 km; otherwise road speed log-normal (median 20 km/h, clipped 12–35);
  hub-to-hub legs use transit speed 28–40 km/h.
- **Position at time t:** the device is either dwelling at a stop (fixed position) or on a leg, where its position is the
  point at the corresponding fraction of the L-shaped route.

## 8. GPS pings (24 hours)

1. A nominal grid every 15 minutes across the whole day (00:00–24:00) with a random per-device-day phase and ±30 %
   uniform jitter. The jitter bound guarantees ping times never reorder or collide.
2. Each grid time becomes a ping with probability
   **device keep probability × hourly activity[hour] × (1.5 if the device is travelling)**, capped at 0.98.
   The hourly activity profile is low overnight (0.10–0.20), rises through the morning commute (peak 08:00), stays near 0.9–1.0
   during working hours, peaks again 17:00–18:00 and fades through the evening (0.30 at 23:00).
3. Position = itinerary position at the ping time, plus Gaussian GPS error (σ = 10 m); 1.5 % of pings are outliers
   (σ = 60 m). Coordinates are clipped to the configured bounding box.
4. Timestamps are formatted as Asia/Kolkata local time with the `+05:30` suffix (fixed offset; ranges that would cross a DST
   change are rejected).

The result is a sparse, irregular, device-dependent series typical of commercial location data: about 45 pings per device
per day with the defaults, dense during movement and rare overnight.

## 9. Chunking, reproducibility and exact record counts

- `chunk_device_days` (default 15,000) bounds memory: a chunk simulates `chunk_device_days // num_days` devices at once,
  so memory does not grow with the dataset size; chunks are appended to the CSV (`.part` file renamed on success).
- Randomness: the layout uses `SeedSequence([seed, 0])`, chunk *k* uses `SeedSequence([seed, 1, k])`.
  The same seed and configuration (including `chunk_device_days`) therefore reproduce the file exactly.
- **Exact counts:** the generator keeps adding device chunks (the last one sized from the observed rows per device)
  until the target is reached, then trims the tail of the final chunk, so the file contains exactly `target_records` rows.
  The only side effect is that the last device may lose its final pings. With `--devices N` the device count is fixed
  and the record count is whatever the simulation produces.

## 10. Validation mapping

| Requirement | Check in `validate_data.py` |
|-------------|-----------------------------|
| Realistic, non-teleporting movement | Implied speed between consecutive pings; chronological order; commute-hour vs overnight/midday movement |
| 24-hour coverage | All 24 hours populated; overnight share of records and devices; sleeping-hours rate vs daytime |
| Weekday vs weekend behaviour | Weekday vs weekend morning movement |
| Evening retail activity | Catchment pings 17–21 h vs overnight |
| Analytical usefulness | Minimum unique devices in each catchment and in both |
| Data integrity | Missing values, duplicates, coordinate ranges, timestamp format/offset/range, DeviceID format, city bounds |

## 11. Known limitations

- Parameters are plausible defaults, not calibrated to observed data; no road network, no traffic, no public holidays unless
  listed in `holidays`.
- Everyone is at home overnight; there are no night shifts, trips between days or travel outside the bounding box.
- Catchment overlap is strongly driven by geography: with stores ~0.7 km apart and 35 % of residential/workplace zones
  placed near them, a large share of devices appears in both 500 m catchments. Increase the distance between the two
  stores in `config.py`, or lower `zone_share_near_stores` and `store_customer_proximity_boost`, to reduce it.
- Pass-through traffic is included: a ping in a catchment is not proof of a purchase or a deliberate visit.
- Output depends on the NumPy random generator implementation; the files shipped here were produced with NumPy 2.x.
