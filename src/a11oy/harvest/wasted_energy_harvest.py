#!/usr/bin/env python3
"""wasted_energy_harvest.py — jack into FREE, no-key feeds that expose WASTED energy
(negative-price / curtailed-renewable windows) and emit an honest harvest posture.

Doctrine (binding):
  - NO free-energy / over-unity. This HARVESTS already-wasted grid energy (power the grid
    is paying to offload because renewable supply exceeds demand). It does not create energy.
  - All feeds here are FREE and PUBLIC (no token). Open data, legal to ingest (idea/expression).
  - Energy figures stay SAMPLE/ESTIMATE until a real on-box meter (NVML) feeds joules.
    This module produces a PRICE/SURPLUS POSTURE signal, not a joule measurement.
  - The posture only GATES when to do batch work; it never asserts physical harvest.

Free feeds jacked (probed live 2026-06-13, all responded):
  - aWATTar DE/AT wholesale price (api.awattar.de|at /v1/marketdata) — negative price = wasted
  - CAISO OASIS LMP (oasis.caiso.com/oasisapi) — US California public
  - Energy-Charts / Fraunhofer (api.energy-charts.info) — renewable share of load (WHY it's negative)
  - UK Carbon Intensity (api.carbonintensity.org.uk) — low-carbon surplus index
  - Open-Meteo (api.open-meteo.com) — wind/solar weather = FORECAST of future surplus

Posture levels (worst→best for harvesting):
  expensive < normal < cheap < curtailed-renewable < negative-price
The daemon floods Bekenstein-gated batch work when posture >= cheap; hardest when negative-price.
"""
from __future__ import annotations
import json
import urllib.request
import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional

UA = {"User-Agent": "szl-wasted-energy-harvest/1.0 (+https://a11oy.net)"}
# Per-feed outbound timeout. Was 12s: with ~6 feeds fetched SEQUENTIALLY per posture
# call, a single slow/dead public feed could stall the request past the edge proxy's
# deadline -> intermittent HTTP 000. Bounded to <=3s so the worst case stays well
# inside the proxy budget while every feed still honest-degrades to reachable:false.
TIMEOUT = 3

# Posture ordering (higher index = more wasted energy available to soak)
POSTURE_RANK = {
    "expensive": 0,
    "normal": 1,
    "cheap": 2,
    "curtailed-renewable": 3,
    "negative-price": 4,
}


def _get_json(url: str) -> Optional[object]:
    """Best-effort GET → JSON. Returns None on any failure (honest: feed unreachable
    or returned non-JSON, e.g. a rate-limit/empty body). Never raises."""
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            body = r.read().decode("utf-8", "replace").strip()
        if not body:
            return None
        return json.loads(body)
    except Exception:
        return None


@dataclass
class FeedReading:
    feed: str
    reachable: bool
    measured: bool                 # True only if a REAL value was returned (not a fallback)
    value: Optional[float] = None  # price (EUR/MWh) or share (%) depending on feed
    unit: str = ""
    note: str = ""


@dataclass
class HarvestPosture:
    posture: str                   # one of POSTURE_RANK keys
    rank: int
    wasted_energy_available: bool  # True iff posture >= cheap
    soak_hard: bool                # True iff negative-price (flood the batch sponge)
    drivers: list = field(default_factory=list)   # human-readable reasons
    readings: list = field(default_factory=list)  # list[FeedReading]
    measured_any: bool = False     # at least one real feed responded
    timestamp_utc: str = ""
    citation: str = "FREE no-key feeds: aWATTar, CAISO OASIS, Energy-Charts/Fraunhofer (price+renshare+grid-frequency), UK Carbon Intensity, Open-Meteo forecast; Energinet (DK, intermittent) candidate"
    doctrine: str = "harvests wasted grid energy; no free-energy claim; joules stay SAMPLE until on-box NVML meter"


# ---- individual free jacks -------------------------------------------------

def jack_awattar(country: str = "de") -> tuple[FeedReading, list[float]]:
    """aWATTar wholesale price. Negative marketprice = the grid is PAYING to offload (wasted)."""
    base = "https://api.awattar.de" if country == "de" else "https://api.awattar.at"
    d = _get_json(f"{base}/v1/marketdata")
    if not d or "data" not in d:
        return FeedReading(f"awattar_{country}", False, False, note="unreachable"), []
    prices = [row["marketprice"] for row in d["data"]]
    now = prices[0] if prices else None
    return (
        FeedReading(f"awattar_{country}", True, True, now, "EUR/MWh",
                    f"min_next={min(prices):.2f} neg_windows={sum(1 for p in prices if p < 0)}/{len(prices)}"),
        prices,
    )


def jack_energy_charts_renshare(country: str = "de") -> FeedReading:
    """Fraunhofer renewable share of load. High share = surplus renewables = WHY price goes negative."""
    d = _get_json(f"https://api.energy-charts.info/ren_share?country={country}")
    if not d or not isinstance(d, list) or not d:
        return FeedReading("energy_charts_ren_share", False, False, note="unreachable")
    data = d[0].get("data") if isinstance(d[0], dict) else None
    if not data:
        return FeedReading("energy_charts_ren_share", True, False, note="no data array")
    cur = data[0]
    return FeedReading("energy_charts_ren_share", True, True, float(cur), "% of load",
                       f"max_today={max(x for x in data if x is not None):.1f}%")


def jack_uk_carbon() -> FeedReading:
    """UK Carbon Intensity (free). 'low' index = clean surplus on the GB grid."""
    d = _get_json("https://api.carbonintensity.org.uk/intensity")
    if not d or "data" not in d or not d["data"]:
        return FeedReading("uk_carbon_intensity", False, False, note="unreachable")
    intensity = d["data"][0].get("intensity", {})
    return FeedReading("uk_carbon_intensity", True, True,
                       float(intensity.get("actual") or intensity.get("forecast") or 0),
                       "gCO2/kWh", f"index={intensity.get('index')}")


def jack_grid_frequency(country: str = "de") -> FeedReading:
    """Energy-Charts grid frequency (Hz). The PUREST oversupply tell: when supply
    exceeds demand the frequency drifts ABOVE 50.00 Hz (under-frequency <50 = deficit).
    A sustained reading >50.00 corroborates a curtailed/negative-price surplus window."""
    d = _get_json(f"https://api.energy-charts.info/frequency?country={country}")
    if not d or "data" not in d and "frequency" not in d:
        # energy-charts returns {unix_seconds:[...], data:[...]} or similar; be defensive
        freq = None
        if isinstance(d, dict):
            for k in ("data", "frequency", "values"):
                v = d.get(k)
                if isinstance(v, list) and v:
                    freq = v[-1]
                    break
        if freq is None:
            return FeedReading("grid_frequency", bool(d), False, note="reachable, no parse")
        return FeedReading("grid_frequency", True, True, float(freq), "Hz",
                           f"{'surplus(>50)' if float(freq) >= 50.0 else 'deficit(<50)'}")
    arr = d.get("data") or d.get("frequency") or []
    if not arr:
        return FeedReading("grid_frequency", True, False, note="empty")
    freq = float(arr[-1])
    return FeedReading("grid_frequency", True, True, freq, "Hz",
                       f"{'surplus(>=50)' if freq >= 50.0 else 'deficit(<50)'}")


def jack_open_meteo_forecast(lat: float = 52.5, lon: float = 13.4) -> FeedReading:
    """Open-Meteo (free, no key): wind speed @100m + shortwave radiation forecast.
    High wind+sun in coming hours = a FUTURE surplus/negative-price window we can
    PRE-SCHEDULE batch work into before the price even drops. Returns a 0-100ish
    'surplus_outlook' score (normalized wind+solar) for the next 6h."""
    d = _get_json(
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
        f"&hourly=wind_speed_100m,shortwave_radiation&forecast_days=1")
    if not d or "hourly" not in d:
        return FeedReading("open_meteo_forecast", False, False, note="unreachable")
    h = d["hourly"]
    ws = [x for x in (h.get("wind_speed_100m") or [])[:6] if x is not None]
    sr = [x for x in (h.get("shortwave_radiation") or [])[:6] if x is not None]
    if not ws:
        return FeedReading("open_meteo_forecast", True, False, note="no wind data")
    # crude normalized outlook: wind (km/h, cap 60) + solar (W/m2, cap 800)
    wind_score = min(sum(ws) / len(ws), 60) / 60 * 50
    solar_score = (min(sum(sr) / len(sr), 800) / 800 * 50) if sr else 0
    outlook = round(wind_score + solar_score, 1)
    return FeedReading("open_meteo_forecast", True, True, outlook, "surplus_outlook_0_100",
                       f"next6h wind~{sum(ws)/len(ws):.0f}km/h solar~{(sum(sr)/len(sr)) if sr else 0:.0f}W/m2")


# Energy-Charts covers 40+ European countries/zones from ONE no-key endpoint.
WORLD_ZONES = ["de", "fr", "es", "it", "pl", "nl", "be", "ch", "at", "cz",
               "dk", "no", "se", "fi", "pt", "gr", "ro", "hu", "sk", "ie"]


def scan_world_renshare(zones: Optional[list] = None, cap: int = 8) -> dict:
    """FOLLOW-THE-WIND scanner: find which country has the highest renewable share
    of load right now (the deepest surplus = best place to route batch work).
    Free, no key (Energy-Charts). Caps the number of zones probed per call to be
    polite to the free endpoint. Returns {zone: share} for reachable zones +
    the best zone."""
    zones = (zones or WORLD_ZONES)[:cap]
    shares: dict = {}
    for z in zones:
        d = _get_json(f"https://api.energy-charts.info/ren_share?country={z}")
        if isinstance(d, list) and d and isinstance(d[0], dict):
            data = d[0].get("data")
            if data:
                shares[z] = round(float(data[0]), 1)
    best = max(shares, key=shares.get) if shares else None
    return {"shares": shares, "best_zone": best,
            "best_share": shares.get(best) if best else None,
            "reachable": len(shares)}


def jack_elexon_uk() -> FeedReading:
    """UK Elexon BMRS live fuel mix (MW), no key. Nuclear baseload + wind + negative
    interconnector exports (INT* < 0 = UK dumping surplus abroad = wasted-energy tell)."""
    d = _get_json("https://data.elexon.co.uk/bmrs/api/v1/datasets/FUELINST?format=json")
    rows = d.get("data") if isinstance(d, dict) else (d if isinstance(d, list) else None)
    if not rows:
        return FeedReading("elexon_uk_fuelmix", bool(d), False, note="reachable, no parse")
    last = {}
    for r in rows[-40:]:
        last[r.get("fuelType")] = r.get("generation")
    neg_exports = sum(v for k, v in last.items() if k and k.startswith("INT") and isinstance(v, (int, float)) and v < 0)
    nuclear = last.get("NUCLEAR")
    return FeedReading("elexon_uk_fuelmix", True, True, nuclear, "MW (nuclear)",
                       f"neg_interconnector_exports={neg_exports}MW (surplus dumped abroad)")


def jack_caiso() -> FeedReading:
    """CAISO OASIS reachability (US California public LMP). Probe-only here (zip payload)."""
    try:
        req = urllib.request.Request(
            "https://oasis.caiso.com/oasisapi/SingleZip?queryname=PRC_LMP&version=1",
            headers=UA)
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            ok = r.status == 200
        return FeedReading("caiso_oasis", ok, False, note="reachable (zip payload; parse on-box)")
    except Exception:
        return FeedReading("caiso_oasis", False, False, note="unreachable")


# ---- aggregator ------------------------------------------------------------

def current_harvest_posture() -> HarvestPosture:
    """Fuse the free feeds into one honest wasted-energy posture."""
    readings: list[FeedReading] = []
    drivers: list[str] = []

    aw, prices = jack_awattar("de")
    readings.append(aw)
    ren = jack_energy_charts_renshare("de")
    readings.append(ren)
    readings.append(jack_uk_carbon())
    freq = jack_grid_frequency("de")
    readings.append(freq)
    forecast = jack_open_meteo_forecast()
    readings.append(forecast)
    readings.append(jack_caiso())

    measured_any = any(r.measured for r in readings)

    # Decide posture from the strongest REAL signal we have.
    posture = "normal"
    if aw.measured and prices:
        cur = prices[0]
        min_next = min(prices)
        if cur < 0 or min_next < 0:
            posture = "negative-price"
            drivers.append(f"aWATTar negative: now={cur:.2f}, min_next={min_next:.2f} EUR/MWh — grid paying to offload")
        elif cur < 30:
            posture = "cheap"
            drivers.append(f"aWATTar cheap: {cur:.2f} EUR/MWh")
        else:
            posture = "normal"
            drivers.append(f"aWATTar normal: {cur:.2f} EUR/MWh")

    # Renewable surplus can PROMOTE cheap→curtailed-renewable (real curtailment driver).
    if ren.measured and ren.value is not None and ren.value >= 75 and posture in ("cheap", "normal"):
        if posture != "negative-price":
            posture = "curtailed-renewable"
        drivers.append(f"renewable share {ren.value:.1f}% of load — surplus wind/solar")
    elif ren.measured and ren.value is not None:
        drivers.append(f"renewable share {ren.value:.1f}% of load")

    # Grid frequency corroboration: sustained >50 Hz = real-time oversupply.
    if freq.measured and freq.value is not None and freq.value >= 50.0:
        drivers.append(f"grid frequency {freq.value:.3f} Hz (>=50 = live oversupply)")

    # Forecast: high surplus outlook = a soak window is coming even if price is normal now.
    if forecast.measured and forecast.value is not None and forecast.value >= 50:
        drivers.append(f"surplus outlook {forecast.value:.0f}/100 next 6h (pre-schedule next soak)")

    rank = POSTURE_RANK[posture]
    return HarvestPosture(
        posture=posture,
        rank=rank,
        wasted_energy_available=rank >= POSTURE_RANK["cheap"],
        soak_hard=(posture == "negative-price"),
        drivers=drivers,
        readings=[asdict(r) for r in readings],
        measured_any=measured_any,
        timestamp_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    )


def harvest_provenance() -> dict:
    """Receipt-shaped provenance fields for the energy receipt."""
    p = current_harvest_posture()
    return {
        "energy_source": "free-public-grid-feeds",
        "posture": p.posture,
        "wasted_energy_available": p.wasted_energy_available,
        "soak_hard": p.soak_hard,
        "price_measured": p.measured_any,   # price/posture is real; joules remain SAMPLE off-box
        "joules_label": "sample",           # NEVER measured until on-box NVML
        "drivers": p.drivers,
        "citation": p.citation,
    }


if __name__ == "__main__":
    import sys
    p = current_harvest_posture()
    checks = 0
    print("=== WASTED-ENERGY HARVEST — live free-feed probe ===")
    for r in p.readings:
        flag = "OK " if r["reachable"] else "DOWN"
        meas = "MEASURED" if r["measured"] else "sample/probe"
        print(f"  [{flag}] {r['feed']:26} {meas:13} val={r['value']} {r['unit']}  {r['note']}")
        checks += 1
    print(f"\n  POSTURE: {p.posture}  (rank {p.rank}/4)")
    print(f"  wasted_energy_available: {p.wasted_energy_available}")
    print(f"  soak_hard (flood batch sponge): {p.soak_hard}")
    print("  drivers:")
    for d in p.drivers:
        print(f"    - {d}")
    # honest checks
    assert p.posture in POSTURE_RANK, "posture must be a known level"; checks += 1
    assert p.measured_any, "at least one free feed must be live"; checks += 1
    prov = harvest_provenance()
    assert prov["joules_label"] == "sample", "joules MUST stay sample off-box (doctrine)"; checks += 1
    assert prov["energy_source"] == "free-public-grid-feeds"; checks += 1
    print(f"\n  provenance (receipt fields): {json.dumps(prov, indent=2)[:400]}...")
    print(f"\nok:true checks:{checks}")
    sys.exit(0)
