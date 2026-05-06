from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, timezone
from typing import Optional
from pathlib import Path
import random
import hashlib

app = FastAPI(
    title="Rivian × Geotab OEM Connector",
    description=(
        "Demo connector that normalizes Rivian vehicle telematics into Geotab's "
        "standard data models (LogRecord, StatusData, FaultData). "
        "In production, RivianGeotabConnector would call Rivian's Vehicle API "
        "instead of the built-in fleet simulator."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


# ─────────────────────────────────────────────────────────────────────────────
# Rivian Raw Data Models  (proprietary OEM format — what Rivian's API returns)
# ─────────────────────────────────────────────────────────────────────────────

class RivianVehicleStatus(BaseModel):
    """Raw telemetry payload from Rivian's Vehicle API."""
    vin: str
    timestamp: str
    battery_percent: float
    estimated_range_miles: float
    charge_status: str            # CHARGING | PLUGGED_NOT_CHARGING | UNPLUGGED
    odometer_km: float
    latitude: float
    longitude: float
    speed_mph: float
    cabin_temp_f: float
    motor_torque_nm: float
    regenerative_braking_active: bool
    fault_codes: list[str]        # Rivian DTC format e.g. "RIV-BMS-0042"
    driver_id: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Geotab Standard Data Models  (what MyGeotab expects)
# ─────────────────────────────────────────────────────────────────────────────

class GeotabDevice(BaseModel):
    id: str
    name: str
    serial_number: str
    device_type: str
    vehicle_identification_number: str
    groups: list[str]


class GeotabLogRecord(BaseModel):
    """GPS position and speed. One record per polling interval."""
    id: str
    device_id: str
    date_time: str
    latitude: float
    longitude: float
    speed: float                  # Always km/h in Geotab
    is_device_communicating: bool


class GeotabStatusData(BaseModel):
    """Single diagnostic metric. One Rivian status → many StatusData records."""
    id: str
    device_id: str
    date_time: str
    diagnostic_id: str
    diagnostic_name: str
    data: float


class GeotabFaultData(BaseModel):
    id: str
    device_id: str
    date_time: str
    code: int
    failure_mode_identifier: int
    diagnostic_name: str
    dismiss_user_name: Optional[str] = None


class NormalizedVehicle(BaseModel):
    device: GeotabDevice
    log_record: GeotabLogRecord
    status_data: list[GeotabStatusData]
    fault_data: list[GeotabFaultData]


# ─────────────────────────────────────────────────────────────────────────────
# Rivian DTC → Geotab FaultData lookup table
# ─────────────────────────────────────────────────────────────────────────────

RIVIAN_FAULT_MAP: dict[str, tuple[int, int, str]] = {
    "RIV-BMS-0042": (42, 14, "Battery Management System Fault"),
    "RIV-MCU-0018": (18, 31, "Motor Control Unit Warning"),
    "RIV-CHG-0071": (71,  9, "Charging System Fault"),
    "RIV-TMS-0033": (33,  7, "Thermal Management System Alert"),
}


# ─────────────────────────────────────────────────────────────────────────────
# Rivian → Geotab Normalization Engine  (this IS the OEM connector concept)
# ─────────────────────────────────────────────────────────────────────────────

class RivianGeotabConnector:
    """
    Transforms Rivian proprietary telemetry into Geotab standard data models.

    Key design note: Geotab's StatusData is a single-value model (one float per
    diagnostic). A single Rivian status update therefore expands into 7 separate
    StatusData records — one per metric. This is intentional and matches how
    all other Geotab OEM connectors work.
    """

    @staticmethod
    def _device_id(vin: str) -> str:
        return "b" + hashlib.md5(vin.encode()).hexdigest()[:8]

    @staticmethod
    def normalize_device(raw: RivianVehicleStatus) -> GeotabDevice:
        model = "Rivian R1T"
        if raw.vin.startswith("7PDSG"):
            model = "Rivian R1S"
        elif raw.vin.startswith("7FMCU"):
            model = "Rivian EDV"
        return GeotabDevice(
            id=RivianGeotabConnector._device_id(raw.vin),
            name=f"{model} ...{raw.vin[-6:]}",
            serial_number=raw.vin,
            device_type=model.replace(" ", ""),
            vehicle_identification_number=raw.vin,
            groups=["Rivian Fleet", "EV Vehicles"],
        )

    @staticmethod
    def normalize_position(raw: RivianVehicleStatus) -> GeotabLogRecord:
        dev_id = RivianGeotabConnector._device_id(raw.vin)
        return GeotabLogRecord(
            id=hashlib.md5(f"{raw.vin}{raw.timestamp}pos".encode()).hexdigest()[:12],
            device_id=dev_id,
            date_time=raw.timestamp,
            latitude=raw.latitude,
            longitude=raw.longitude,
            speed=round(raw.speed_mph * 1.60934, 1),   # mph → km/h
            is_device_communicating=True,
        )

    @staticmethod
    def normalize_status(raw: RivianVehicleStatus) -> list[GeotabStatusData]:
        dev_id = RivianGeotabConnector._device_id(raw.vin)
        ts = raw.timestamp
        base = hashlib.md5(f"{raw.vin}{ts}st".encode()).hexdigest()[:8]

        metrics = [
            ("DiagnosticStateOfChargeId",        "State of Charge (%)",        raw.battery_percent),
            ("DiagnosticElectricVehicleRangeId", "EV Estimated Range (km)",    round(raw.estimated_range_miles * 1.60934, 1)),
            ("DiagnosticOdometerAdjustmentId",   "Odometer (km)",              raw.odometer_km),
            ("DiagnosticCabinTemperatureId",     "Cabin Temperature (°C)",     round((raw.cabin_temp_f - 32) * 5 / 9, 1)),
            ("DiagnosticChargeStateId",          "Charge State",               1.0 if raw.charge_status == "CHARGING" else 0.0),
            ("DiagnosticMotorTorqueId",          "Motor Torque (Nm)",          raw.motor_torque_nm),
            ("DiagnosticRegenerativeBrakingId",  "Regenerative Braking Active", 1.0 if raw.regenerative_braking_active else 0.0),
        ]
        return [
            GeotabStatusData(
                id=f"{base}{i:02d}",
                device_id=dev_id,
                date_time=ts,
                diagnostic_id=diag_id,
                diagnostic_name=diag_name,
                data=round(value, 2),
            )
            for i, (diag_id, diag_name, value) in enumerate(metrics)
        ]

    @staticmethod
    def normalize_faults(raw: RivianVehicleStatus) -> list[GeotabFaultData]:
        dev_id = RivianGeotabConnector._device_id(raw.vin)
        result = []
        for code in raw.fault_codes:
            if code in RIVIAN_FAULT_MAP:
                fault_code, fmi, name = RIVIAN_FAULT_MAP[code]
                result.append(GeotabFaultData(
                    id=hashlib.md5(f"{raw.vin}{code}".encode()).hexdigest()[:12],
                    device_id=dev_id,
                    date_time=raw.timestamp,
                    code=fault_code,
                    failure_mode_identifier=fmi,
                    diagnostic_name=name,
                ))
        return result

    @classmethod
    def full_sync(cls, raw: RivianVehicleStatus) -> NormalizedVehicle:
        return NormalizedVehicle(
            device=cls.normalize_device(raw),
            log_record=cls.normalize_position(raw),
            status_data=cls.normalize_status(raw),
            fault_data=cls.normalize_faults(raw),
        )


# ─────────────────────────────────────────────────────────────────────────────
# Mock Rivian Fleet Simulator
# (in production this would be replaced with calls to Rivian's Vehicle API)
# ─────────────────────────────────────────────────────────────────────────────

_FLEET_SEED = [
    ("7PDSG1EV2NB000001", 43.6532, -79.3832, 82.0, 12400.0),
    ("1FMCU0EV3NB000002", 43.7200, -79.4100, 45.0,  8750.0),
    ("7FMCU0EV4NB000003", 43.6000, -79.5000, 91.0, 22100.0),
    ("7PDSG1EV5NB000004", 43.8100, -79.2800, 19.0,  5310.0),
    ("1FMCU0EV6NB000005", 43.6800, -79.3200, 63.0, 15640.0),
]

fleet_state: dict[str, dict] = {}


def _init_fleet() -> None:
    for vin, lat, lon, battery, odo in _FLEET_SEED:
        fleet_state[vin] = {
            "lat": lat, "lon": lon,
            "battery": battery, "odometer": odo,
            "speed": 0.0, "injected_faults": [],
        }


_init_fleet()


def _build_status(vin: str) -> RivianVehicleStatus:
    s = fleet_state[vin]
    battery = s["battery"]

    if battery < 20:
        charge_status = "CHARGING"
        s["battery"] = min(100.0, battery + random.uniform(0.8, 2.0))
        s["speed"] = 0.0
    elif random.random() < 0.12:
        charge_status = "PLUGGED_NOT_CHARGING"
        s["speed"] = 0.0
    else:
        charge_status = "UNPLUGGED"
        s["battery"] = max(14.0, battery - random.uniform(0.0, 0.35))
        s["speed"] = random.uniform(0, 95)
        s["lat"] += random.uniform(-0.0015, 0.0015)
        s["lon"] += random.uniform(-0.0015, 0.0015)

    s["odometer"] += s["speed"] * (3 / 3600)

    active_faults = list(s["injected_faults"])
    if random.random() < 0.04 and not active_faults:
        active_faults = [random.choice(list(RIVIAN_FAULT_MAP.keys()))]

    return RivianVehicleStatus(
        vin=vin,
        timestamp=datetime.now(timezone.utc).isoformat(),
        battery_percent=round(s["battery"], 1),
        estimated_range_miles=round((s["battery"] / 100) * 314, 1),
        charge_status=charge_status,
        odometer_km=round(s["odometer"], 1),
        latitude=round(s["lat"], 6),
        longitude=round(s["lon"], 6),
        speed_mph=round(s["speed"], 1),
        cabin_temp_f=round(random.uniform(64, 76), 1),
        motor_torque_nm=round(s["speed"] * 8.5, 1) if charge_status == "UNPLUGGED" else 0.0,
        regenerative_braking_active=s["speed"] > 8 and random.random() < 0.3,
        fault_codes=active_faults,
        driver_id=f"DRV-{vin[-5:]}",
    )


# ─────────────────────────────────────────────────────────────────────────────
# API Endpoints
# ─────────────────────────────────────────────────────────────────────────────

HTML_PATH = Path(__file__).parent / "index.html"


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def serve_dashboard():
    return HTML_PATH.read_text(encoding="utf-8")


@app.get(
    "/api/fleet",
    summary="Get all Rivian vehicles — normalized to Geotab format",
    tags=["Fleet"],
)
async def get_fleet():
    result = []
    for vin in fleet_state:
        raw = _build_status(vin)
        norm = RivianGeotabConnector.full_sync(raw)
        result.append({
            "vin": vin,
            "name": norm.device.name,
            "device_type": norm.device.device_type,
            "device_id": norm.device.id,
            "battery_percent": raw.battery_percent,
            "estimated_range_miles": raw.estimated_range_miles,
            "charge_status": raw.charge_status,
            "speed_mph": raw.speed_mph,
            "latitude": raw.latitude,
            "longitude": raw.longitude,
            "fault_codes": raw.fault_codes,
            "fault_names": [
                RIVIAN_FAULT_MAP[c][2] for c in raw.fault_codes if c in RIVIAN_FAULT_MAP
            ],
        })
    return result


@app.get(
    "/api/vehicle/{vin}/raw",
    response_model=RivianVehicleStatus,
    summary="Raw Rivian telemetry — proprietary OEM format",
    tags=["Data Pipeline"],
)
async def get_raw(vin: str):
    if vin not in fleet_state:
        return {"error": f"VIN {vin} not found"}
    return _build_status(vin)


@app.get(
    "/api/vehicle/{vin}/normalized",
    response_model=NormalizedVehicle,
    summary="Geotab normalized telemetry — standard Geotab data models",
    tags=["Data Pipeline"],
)
async def get_normalized(vin: str):
    if vin not in fleet_state:
        return {"error": f"VIN {vin} not found"}
    return RivianGeotabConnector.full_sync(_build_status(vin))


@app.post(
    "/api/simulate/fault",
    summary="Inject a fault on a vehicle (demo: makes fault badge appear on dashboard)",
    tags=["Simulation"],
)
async def inject_fault(vin: str, fault_code: str = "RIV-BMS-0042"):
    if vin not in fleet_state:
        return {"error": f"VIN {vin} not found"}
    if fault_code not in RIVIAN_FAULT_MAP:
        return {"error": f"Unknown fault code. Valid options: {list(RIVIAN_FAULT_MAP.keys())}"}
    fleet_state[vin]["injected_faults"] = [fault_code]
    _, _, name = RIVIAN_FAULT_MAP[fault_code]
    return {"status": "ok", "vin": vin, "fault_code": fault_code, "fault_name": name}


@app.delete(
    "/api/simulate/fault/{vin}",
    summary="Clear injected fault from a vehicle",
    tags=["Simulation"],
)
async def clear_fault(vin: str):
    if vin not in fleet_state:
        return {"error": f"VIN {vin} not found"}
    fleet_state[vin]["injected_faults"] = []
    return {"status": "ok", "vin": vin, "message": "Faults cleared"}


if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print("\n  Rivian × Geotab OEM Connector")
    print(f"  Dashboard : http://localhost:{port}")
    print(f"  API Docs  : http://localhost:{port}/docs\n")
    uvicorn.run(app, host="0.0.0.0", port=port)
