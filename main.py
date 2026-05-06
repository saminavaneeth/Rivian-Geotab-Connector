from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta
from typing import Optional
from pathlib import Path
import random
import hashlib
import asyncio
import json
from collections import defaultdict

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
    fault_state_active: bool = True
    dismiss_user_name: Optional[str] = None


class NormalizedVehicle(BaseModel):
    device: GeotabDevice
    log_record: GeotabLogRecord
    status_data: list[GeotabStatusData]
    fault_data: list[GeotabFaultData]


class FaultSeverityScore(BaseModel):
    """Severity scoring for fault prioritization in dispatcher workflows."""
    fault_code: int
    fault_name: str
    severity_score: int  # 0-100
    severity_level: str  # CRITICAL, HIGH, MEDIUM, LOW, INFO
    recommendation: str
    rivian_fault_code: str = ""


class MaintenanceSuggestion(BaseModel):
    """Maintenance action recommended based on fault patterns."""
    device_id: str
    vin: str
    suggestion_type: str  # battery_inspection, charging_maintenance, motor_diagnostics, thermal_inspection
    urgency: str  # high, medium, low
    estimated_downtime_hours: int
    parts_likely_needed: list[str]
    reason: str


# ─────────────────────────────────────────────────────────────────────────────
# Rivian DTC → Geotab FaultData lookup table (with real Rivian codes)
# Format: "RIV-{system}-{code}" → (geotab_code, fmi, description)
# ─────────────────────────────────────────────────────────────────────────────

RIVIAN_FAULT_MAP: dict[str, tuple[int, int, str]] = {
    # BMS (Battery Management System) faults
    "BMS_a066": (166, 1, "Charge Limit Restricted"),  # Pack is too cold or too hot
    "BMS_a154": (154, 2, "Cell Imbalance Detected"),  # Delta voltage exceeds threshold
    "BMS_a017": (17, 3, "Contactor Weld Detection"),  # HV contactors stuck
    
    # CHG (Charging System) faults
    "CHG_a035": (235, 4, "Proximity Pilot Fault"),  # Physical connection issue
    "CHG_a112": (112, 5, "Thermal Trip (Charging)"),  # Charger overheat
    
    # DRV (Drive/Inverter) faults
    "DRV_a023": (23, 6, "Inverter Overcurrent"),  # Power surge detected
    "DRV_a088": (88, 7, "Resolver Calibration Error"),  # Motor position unknown
    
    # VDM (Vehicle Dynamics/Suspension) faults
    "VDM_a004": (204, 8, "Compressor Overheat"),  # Air suspension pump overheat
    "VDM_a045": (45, 9, "Ride Height Sensor Out of Range"),  # Suspension alignment
    "VDM_a012": (212, 10, "Kinetic Fluid Pressure Low"),  # Hydraulic anti-roll issue
    
    # THM (Thermal Management) faults
    "THM_a002": (302, 11, "Coolant Pump A Stuck"),  # Primary cooling failure
    "THM_a019": (319, 12, "Refrigerant Pressure Low"),  # AC leak (critical for battery)
    "THM_a041": (341, 13, "Octovalve Position Error"),  # Complex valve stuck
}

# Fault severity mapping (code → (severity_score 0-100, severity_level))
FAULT_SEVERITY_MAP: dict[int, tuple[int, str]] = {
    166: (75, "HIGH"),      # Charge limit (operational impact)
    154: (90, "CRITICAL"),  # Cell imbalance (safety)
    17: (95, "CRITICAL"),   # Contactor weld (safety-critical)
    235: (70, "HIGH"),      # Proximity pilot (charging issue)
    112: (85, "CRITICAL"),  # Thermal trip (fire risk)
    23: (80, "CRITICAL"),   # Inverter overcurrent (power loss)
    88: (60, "MEDIUM"),     # Resolver error (clunking, non-critical)
    204: (65, "MEDIUM"),    # Compressor overheat (suspension issue)
    45: (75, "HIGH"),       # Height sensor (ride/handling)
    212: (55, "MEDIUM"),    # Fluid pressure (degraded performance)
    302: (85, "CRITICAL"),  # Coolant pump (thermal runaway risk)
    319: (90, "CRITICAL"),  # Refrigerant (battery cooling failure)
    341: (70, "HIGH"),      # Octovalve (thermal management degraded)
}

# Maintenance triggers based on fault patterns
MAINTENANCE_TRIGGERS: dict[int, dict] = {
    154: {"action": "battery_inspection", "parts": ["battery_module", "bms_firmware"], "hours": 8},
    17: {"action": "battery_inspection", "parts": ["hv_contactors", "power_distribution"], "hours": 6},
    112: {"action": "charging_maintenance", "parts": ["onboard_charger", "thermal_sensor"], "hours": 4},
    23: {"action": "motor_diagnostics", "parts": ["inverter_module", "power_electronics"], "hours": 6},
    88: {"action": "motor_diagnostics", "parts": ["motor_resolver", "position_sensor"], "hours": 5},
    302: {"action": "thermal_inspection", "parts": ["coolant_pump", "radiator"], "hours": 3},
    319: {"action": "thermal_inspection", "parts": ["refrigerant_circuit", "compressor"], "hours": 4},
}


# ─────────────────────────────────────────────────────────────────────────────
# Fault Scoring Engine  (prioritization for dispatcher workflows)
# ─────────────────────────────────────────────────────────────────────────────

class FaultScoringEngine:
    """Scores faults for dispatcher prioritization and maintenance workflows."""
    
    @staticmethod
    def score_fault(fault_code: int, active_fault_count: int = 1) -> FaultSeverityScore:
        """Score a single fault (0-100)."""
        base_score, level = FAULT_SEVERITY_MAP.get(fault_code, (40, "LOW"))
        
        # Boost severity if multiple faults active on same vehicle
        if active_fault_count > 2:
            base_score = min(100, base_score + 15)
        if active_fault_count > 4:
            base_score = min(100, base_score + 10)
        
        fault_name = next(
            (name for code, (c, _, name) in RIVIAN_FAULT_MAP.items() if c == fault_code),
            "Unknown Fault"
        )
        
        recommendation = FaultScoringEngine._get_recommendation(fault_code)
        
        return FaultSeverityScore(
            fault_code=fault_code,
            fault_name=fault_name,
            severity_score=base_score,
            severity_level=level,
            recommendation=recommendation,
        )
    
    @staticmethod
    def _get_recommendation(fault_code: int) -> str:
        recommendations = {
            154: "CRITICAL: Stop vehicle and inspect battery module immediately.",
            17: "CRITICAL: Do not operate vehicle. High-voltage safety risk.",
            112: "WARNING: Charging disabled. Schedule charger inspection.",
            23: "CRITICAL: Reduced power. Motor controller failure imminent.",
            319: "CRITICAL: Battery thermal runaway risk. Stop and cool vehicle.",
        }
        return recommendations.get(fault_code, "Monitor and schedule maintenance.")


class MaintenanceEngine:
    """Suggests maintenance actions based on fault history patterns."""
    
    @staticmethod
    def suggest_maintenance(vin: str, fault_history: list[dict]) -> Optional[MaintenanceSuggestion]:
        """Generate maintenance suggestion if fault pattern detected."""
        if not fault_history:
            return None
        
        now = datetime.now(timezone.utc)
        recent_faults = [
            f for f in fault_history
            if datetime.fromisoformat(f["date_time"].replace('Z', '+00:00')) > now - timedelta(days=14)
        ]
        
        # Battery inspection trigger: 3+ BMS faults in 2 weeks
        bms_faults = [f for f in recent_faults if f["code"] in [154, 17, 166]]
        if len(bms_faults) >= 3:
            return MaintenanceSuggestion(
                device_id=vin,
                vin=vin,
                suggestion_type="battery_inspection",
                urgency="high",
                estimated_downtime_hours=8,
                parts_likely_needed=["battery_module", "bms_firmware", "connector_assembly"],
                reason=f"{len(bms_faults)} battery-related faults in past 14 days",
            )
        
        # Charging maintenance: 2+ charging faults
        chg_faults = [f for f in recent_faults if f["code"] in [112, 235]]
        if len(chg_faults) >= 2:
            return MaintenanceSuggestion(
                device_id=vin,
                vin=vin,
                suggestion_type="charging_maintenance",
                urgency="medium",
                estimated_downtime_hours=4,
                parts_likely_needed=["onboard_charger", "charging_port_assembly", "thermal_sensor"],
                reason=f"{len(chg_faults)} charging faults detected",
            )
        
        # Thermal inspection: 2+ thermal management faults
        thm_faults = [f for f in recent_faults if f["code"] in [302, 319, 341]]
        if len(thm_faults) >= 2:
            return MaintenanceSuggestion(
                device_id=vin,
                vin=vin,
                suggestion_type="thermal_inspection",
                urgency="high" if 319 in [f["code"] for f in thm_faults] else "medium",
                estimated_downtime_hours=4,
                parts_likely_needed=["coolant_pump", "refrigerant_circuit", "radiator"],
                reason=f"{len(thm_faults)} thermal management faults",
            )
        
        return None


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
        """Normalize Rivian faults to Geotab FaultData with dynamic mapping for unknowns."""
        dev_id = RivianGeotabConnector._device_id(raw.vin)
        result = []
        for code in raw.fault_codes:
            if code in RIVIAN_FAULT_MAP:
                fault_code, fmi, name = RIVIAN_FAULT_MAP[code]
            else:
                # Passthrough dynamic mapping: map unknown codes to generic Rivian diagnostic
                fault_code = 9999  # Generic Rivian proprietary code
                fmi = 31  # Unknown/proprietary FMI
                name = f"Rivian Proprietary: {code}"
            
            result.append(GeotabFaultData(
                id=hashlib.md5(f"{raw.vin}{code}".encode()).hexdigest()[:12],
                device_id=dev_id,
                date_time=raw.timestamp,
                code=fault_code,
                failure_mode_identifier=fmi,
                diagnostic_name=name,
                fault_state_active=True,
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
fault_history: dict[str, list[dict]] = defaultdict(list)  # Track fault history for each VIN
webhook_events: list[dict] = []  # Simulated webhook events log

def _init_fleet() -> None:
    for vin, lat, lon, battery, odo in _FLEET_SEED:
        fleet_state[vin] = {
            "lat": lat, "lon": lon,
            "battery": battery, "odometer": odo,
            "speed": 0.0, "injected_faults": [],
            "fault_state_active": {},
            "random_faults": [], "fault_set_at": None,
        }
        fault_history[vin] = []

_init_fleet()

_FAULT_STATE_FILE = Path(__file__).parent / "fault_state.json"

def _save_fault_state() -> None:
    try:
        data = {
            vin: {
                "injected_faults": s["injected_faults"],
                "random_faults":   s["random_faults"],
            }
            for vin, s in fleet_state.items()
        }
        _FAULT_STATE_FILE.write_text(json.dumps(data), encoding="utf-8")
    except Exception:
        pass

def _load_fault_state() -> None:
    if not _FAULT_STATE_FILE.exists():
        return
    try:
        data = json.loads(_FAULT_STATE_FILE.read_text(encoding="utf-8"))
        for vin, faults in data.items():
            if vin in fleet_state:
                fleet_state[vin]["injected_faults"] = faults.get("injected_faults", [])
                fleet_state[vin]["random_faults"]   = faults.get("random_faults", [])
    except Exception:
        pass

_load_fault_state()


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
    ts = datetime.now(timezone.utc).isoformat()

    active_faults = list(s["injected_faults"]) + list(s["random_faults"])

    # 4% chance per cycle to add a new random fault (max 3 random faults per vehicle)
    if random.random() < 0.04 and len(s["random_faults"]) < 3:
        new_fault = random.choice([f for f in RIVIAN_FAULT_MAP.keys() if f not in active_faults])
        s["random_faults"].append(new_fault)
        active_faults.append(new_fault)
        fault_code, fmi, name = RIVIAN_FAULT_MAP[new_fault]
        fault_history[vin].append({
            "code": fault_code,
            "name": name,
            "date_time": ts,
            "state": "active",
        })
        _save_fault_state()

    return RivianVehicleStatus(
        vin=vin,
        timestamp=ts,
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
    geotab_code, fmi, name = RIVIAN_FAULT_MAP[fault_code]
    fleet_state[vin]["injected_faults"] = [fault_code]
    fault_history[vin].append({
        "code": geotab_code,
        "name": name,
        "date_time": datetime.now(timezone.utc).isoformat(),
        "state": "active",
    })
    _save_fault_state()
    return {"status": "ok", "vin": vin, "fault_code": fault_code, "fault_name": name}


@app.delete(
    "/api/simulate/fault/{vin}",
    summary="Clear all injected faults from a vehicle",
    tags=["Simulation"],
)
async def clear_fault(vin: str):
    if vin not in fleet_state:
        return {"error": f"VIN {vin} not found"}
    fleet_state[vin]["injected_faults"] = []
    _save_fault_state()
    return {"status": "ok", "vin": vin, "message": "Faults cleared"}


@app.delete(
    "/api/vehicle/{vin}/faults/{fault_code}",
    summary="Dispatcher dismisses a specific active fault",
    tags=["Simulation"],
)
async def dismiss_fault(vin: str, fault_code: str):
    if vin not in fleet_state:
        raise HTTPException(status_code=404, detail={"error": f"VIN {vin} not found"})
    s = fleet_state[vin]
    dismissed = False
    if fault_code in s["injected_faults"]:
        s["injected_faults"].remove(fault_code)
        dismissed = True
    if fault_code in s["random_faults"]:
        s["random_faults"].remove(fault_code)
        dismissed = True
    if not dismissed:
        raise HTTPException(status_code=404, detail={"error": f"Fault {fault_code} not active on {vin}"})
    _save_fault_state()
    return {"status": "ok", "vin": vin, "dismissed": fault_code}


@app.post(
    "/api/simulate/webhook",
    summary="Simulate a Rivian webhook push event (event-driven architecture)",
    tags=["Simulation"],
)
async def simulate_webhook(vin: str, event_type: str = "status_update"):
    """
    Simulates Rivian's Cloud API pushing an event to the connector.
    In production, Rivian would POST to this endpoint when a vehicle
    event occurs — no polling needed.
    """
    if vin not in fleet_state:
        raise HTTPException(status_code=404, detail=f"VIN {vin} not found")

    raw = _build_status(vin)
    norm_device = RivianGeotabConnector.normalize_device(raw)

    event_payloads = {
        "status_update": {
            "battery_percent": raw.battery_percent,
            "estimated_range_miles": raw.estimated_range_miles,
            "charge_status": raw.charge_status,
            "latitude": raw.latitude,
            "longitude": raw.longitude,
            "speed_mph": raw.speed_mph,
            "cabin_temp_f": raw.cabin_temp_f,
        },
        "fault_detected": {
            "fault_codes": raw.fault_codes if raw.fault_codes else ["BMS_a066"],
            "fault_names": [
                RIVIAN_FAULT_MAP[c][2]
                for c in (raw.fault_codes if raw.fault_codes else ["BMS_a066"])
                if c in RIVIAN_FAULT_MAP
            ],
            "severity": "HIGH",
        },
        "charge_started": {
            "charge_status": "CHARGING",
            "battery_percent": raw.battery_percent,
            "charger_type": random.choice(["L2_AC", "DC_FAST", "L1_AC"]),
            "est_charge_complete_min": int((100 - raw.battery_percent) * 2.5),
        },
        "charge_completed": {
            "charge_status": "PLUGGED_NOT_CHARGING",
            "battery_percent": 100.0,
            "kwh_added": round((100 - raw.battery_percent) * 1.35, 1),
            "session_duration_min": int((100 - raw.battery_percent) * 2.5),
        },
    }

    if event_type not in event_payloads:
        event_type = "status_update"

    payload = {
        "event_id": hashlib.md5(f"{vin}{datetime.now(timezone.utc).isoformat()}".encode()).hexdigest()[:16],
        "event_type": event_type,
        "vin": vin,
        "device_name": norm_device.name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "rivian_cloud_api",
        "connector_action": "normalize_and_forward_to_geotab_dig",
        "data": event_payloads[event_type],
    }

    webhook_events.append(payload)
    return {"status": "ok", "event": payload}


@app.get(
    "/api/fleet/faults/scores",
    response_model=dict,
    summary="Get severity scores for all active faults across fleet",
    tags=["Maintenance"],
)
async def get_fault_scores():
    """Scoring for dispatcher prioritization. Reads from fleet_state directly — no side effects."""
    _severity_order = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "INFO": 0}
    result = {}
    for vin, s in fleet_state.items():
        active_faults = list(s["injected_faults"]) + list(s["random_faults"])
        if not active_faults:
            continue

        model = "Rivian R1S" if vin.startswith("7PDSG") else "Rivian EDV" if vin.startswith("7FMCU") else "Rivian R1T"
        device_name = f"{model} ...{vin[-6:]}"

        scores = []
        for fault_code_str in active_faults:
            if fault_code_str in RIVIAN_FAULT_MAP:
                fault_code, _, _ = RIVIAN_FAULT_MAP[fault_code_str]
                score_dict = FaultScoringEngine.score_fault(fault_code, len(active_faults)).dict()
                score_dict["rivian_fault_code"] = fault_code_str
                scores.append(score_dict)

        if scores:
            scores.sort(key=lambda x: -x["severity_score"])
            result[vin] = {
                "device_name": device_name,
                "active_fault_count": len(active_faults),
                "scores": scores,
                "max_severity_score": scores[0]["severity_score"],
                "max_severity_level": max((s["severity_level"] for s in scores), key=lambda x: _severity_order.get(x, 0)),
            }
    return result


@app.get(
    "/api/vehicle/{vin}/maintenance",
    response_model=Optional[MaintenanceSuggestion],
    summary="Get maintenance suggestion based on fault history",
    tags=["Maintenance"],
)
async def get_maintenance_suggestion(vin: str, fault_code: Optional[str] = None):
    """
    Returns a maintenance suggestion.
    - fault_code provided: suggestion specific to that one fault only.
    - fault_code omitted: highest-priority suggestion across all active faults,
      falling back to history-based pattern matching.
    """
    if vin not in fleet_state:
        raise HTTPException(status_code=404, detail={"error": f"VIN {vin} not found"})

    s = fleet_state[vin]
    all_active = list(s["injected_faults"]) + list(s["random_faults"])

    # When a specific fault is requested, only evaluate that one
    faults_to_check = [fault_code] if fault_code else all_active

    _sev_to_urgency = {"CRITICAL": "critical", "HIGH": "high", "MEDIUM": "medium", "LOW": "low"}
    for fault_code_str in faults_to_check:
        if fault_code_str not in all_active:
            continue  # requested fault is no longer active
        if fault_code_str in RIVIAN_FAULT_MAP:
            geotab_code, _, _ = RIVIAN_FAULT_MAP[fault_code_str]
            if geotab_code in MAINTENANCE_TRIGGERS:
                t = MAINTENANCE_TRIGGERS[geotab_code]
                _, _, fault_name = RIVIAN_FAULT_MAP[fault_code_str]
                _, sev_level = FAULT_SEVERITY_MAP.get(geotab_code, (40, "HIGH"))
                urgency = _sev_to_urgency.get(sev_level, "high")
                return MaintenanceSuggestion(
                    device_id=vin,
                    vin=vin,
                    suggestion_type=t["action"],
                    urgency=urgency,
                    estimated_downtime_hours=t["hours"],
                    parts_likely_needed=t["parts"],
                    reason=f"Active fault: {fault_name}",
                )

    # Fault-specific request with no trigger → no action defined
    if fault_code:
        return None

    # Vehicle-wide fallback: history-based pattern matching
    return MaintenanceEngine.suggest_maintenance(vin, fault_history[vin])


@app.get(
    "/api/vehicle/{vin}/fault-history",
    summary="Get fault history for vehicle",
    tags=["Maintenance"],
)
async def get_fault_history(vin: str):
    """Retrieve fault history for trend analysis."""
    if vin not in fleet_state:
        return {"error": f"VIN {vin} not found"}
    return {
        "vin": vin,
        "total_faults": len(fault_history[vin]),
        "recent_30d": [f for f in fault_history[vin] 
                       if datetime.fromisoformat(f["date_time"].replace('Z', '+00:00')) 
                          > datetime.now(timezone.utc) - timedelta(days=30)],
        "full_history": fault_history[vin],
    }


@app.post(
    "/api/simulate/webhook",
    summary="Simulate Rivian webhook push (event-driven data update)",
    tags=["Simulation"],
)
async def simulate_webhook(vin: str, event_type: str = "status_update"):
    """
    Simulates real-time webhook from Rivian API.
    Event types: status_update, fault_detected, fault_cleared, charge_complete
    """
    if vin not in fleet_state:
        return {"error": f"VIN {vin} not found"}
    
    raw = _build_status(vin)
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "vin": vin,
        "event_type": event_type,
        "payload": raw.dict(),
    }
    webhook_events.append(event)
    
    return {
        "status": "webhook_received",
        "event_id": len(webhook_events) - 1,
        "event": event,
    }


@app.get(
    "/api/simulate/webhooks",
    summary="Get webhook events log",
    tags=["Simulation"],
)
async def get_webhooks(limit: int = 20):
    """Retrieve simulated webhook events for debugging."""
    return {
        "total_events": len(webhook_events),
        "recent_events": webhook_events[-limit:],
    }


@app.get(
    "/api/dig/batch-status",
    summary="DIG API batch ingestion simulator status",
    tags=["DIG API Simulator"],
)
async def dig_batch_status():
    """Mock DIG API batch status tracking."""
    now = datetime.now(timezone.utc)
    return {
        "connector_version": "1.0.0",
        "dig_api_endpoint": "https://api.geotab.com/data-intake-gateway/records",
        "last_batch_time": now.isoformat(),
        "batch_size_limit": 5000,
        "record_types_supported": ["VinRecord", "GpsRecord", "StatusRecord", "GenericFaultRecord"],
        "vehicles_monitored": len(fleet_state),
        "total_webhook_events": len(webhook_events),
        "auth_status": "authenticated (mock OAuth2 token valid for 3600s)",
    }

if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print("\n  Rivian × Geotab OEM Connector")
    print(f"  Dashboard : http://localhost:{port}")
    print(f"  API Docs  : http://localhost:{port}/docs\n")
    uvicorn.run(app, host="0.0.0.0", port=port)
