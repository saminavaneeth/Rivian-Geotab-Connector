# Rivian × Geotab OEM Connector — Application Guide

**Live demo:** https://rivian-geotab-connector.onrender.com
**API explorer:** https://rivian-geotab-connector.onrender.com/docs

---

## What this application is

A working simulation of a Geotab OEM Connector for Rivian vehicles. It demonstrates the full data pipeline — from raw Rivian vehicle telemetry, through a [normalization engine](#how-the-data-transformation-works), into Geotab's standard data models — and surfaces the result as a dispatcher-facing fleet dashboard.

The application has two parts:
- **Backend (Python / FastAPI):** Simulates Rivian's Vehicle API, runs the normalization engine, and exposes REST endpoints
- **Frontend (dashboard):** Shows the normalized data as a dispatcher would use it in MyGeotab

The dashboard auto-refreshes every 3 seconds, simulating a live connected fleet.

---

## The Dashboard

### Header bar
The connector name and a pulsing green dot indicating the live data feed is active.

### KPI Cards (top row)

| Card | What it shows | How it's calculated |
|---|---|---|
| **Total Vehicles** | Number of vehicles connected | Count of VINs in the simulated fleet (5 vehicles) |
| **Lowest Battery** | Battery % of the vehicle with least charge, plus its VIN suffix | `min(battery_percent)` across all vehicles. Green ≥ 30%, amber 20–30%, red < 20% |
| **Charging** | Vehicles currently on charge | Count of vehicles where `charge_status = CHARGING` |
| **Active Faults** | Total fault codes across the fleet | Sum of all active fault codes — matches the fault row count in the panel below |

---

### Fault Severity Scores panel (left)

Every active fault across the fleet, sorted by severity score (highest first).

**Each row shows:**
- **Fault name** — human-readable Rivian DTC name (e.g. "Cell Imbalance Detected")
- **Vehicle** — model and last 6 digits of VIN (e.g. "Rivian R1T ...000002")
- **Severity badge** — CRITICAL / HIGH / MEDIUM / LOW, color coded
- **Score** — 0–100 priority score for dispatcher triage
- **Recommendation** — one-line action for the dispatcher

**Severity colors:**
- 🔴 CRITICAL — dark red border
- 🟠 HIGH — red border
- 🟡 MEDIUM — amber border
- 🔵 LOW — blue border

**Interacting:**
- **Click a fault row** → the Maintenance Suggestions panel updates to show the specific action for that fault. The clicked row gets a blue highlight.
- **✕ Dismiss** → removes that specific fault from the vehicle's active list. The dispatcher must explicitly dismiss — faults never auto-clear.

---

### Maintenance Suggestions panel (right)

Recommended maintenance actions based on active faults.

**Default view (Show All):** The highest-priority maintenance suggestion per faulted vehicle.

**Focused view (after clicking a fault):** The maintenance suggestion specifically for the fault clicked — not the most severe fault on the vehicle. A context bar shows which vehicle is focused. Click **Show All** to return.

**Card colors match urgency:**
- 🔴 Critical — dark red (e.g. contactor weld, thermal runaway risk)
- 🟠 High — red
- 🟡 Medium — amber
- 🟢 Low — green

**Each card shows:** action type, vehicle VIN, urgency, estimated downtime, reason (which fault triggered it), and parts likely needed.

---

## How the fault system works

### Where faults come from

1. **Random faults** — every 3-second cycle, each vehicle has a 4% chance of a new fault appearing, drawn from the Rivian DTC lookup table. A vehicle accumulates up to 3 random faults at a time.
2. **Injected faults** — manually triggered via the API (`POST /api/simulate/fault`). Use the `/docs` explorer to inject specific fault codes by VIN.

### Fault persistence

Active faults are stored in memory and written to `fault_state.json` on disk on every change. On server startup, this file is loaded back — so faults survive server restarts and Render.com sleep cycles.

### How faults are cleared

Only by a dispatcher clicking **✕ Dismiss** on a specific fault. No timer, no auto-clear. Each fault must be explicitly acknowledged.

---

## How fault scoring works

Each fault code maps to a severity score (0–100) and level via `FAULT_SEVERITY_MAP`:

| Level | Score range | Example faults |
|---|---|---|
| CRITICAL | 85–100 | Cell Imbalance, Contactor Weld, Thermal Trip, Coolant Pump Failure |
| HIGH | 70–84 | Charge Limit Restricted, Proximity Pilot, Octovalve Error |
| MEDIUM | 55–69 | Resolver Calibration Error, Compressor Overheat, Fluid Pressure Low |
| LOW | below 55 | Minor diagnostics |

**Multi-fault boost:** If a vehicle has more than 2 active faults simultaneously, all scores increase by 15 points (max 100), reflecting compounding risk. Faults always display in descending score order.

---

## How maintenance suggestions work

The suggestion engine runs two paths in order:

### Path 1 — Active fault trigger (immediate)
If an active fault maps to a known maintenance action, that action is returned immediately. Urgency mirrors the fault's severity level:

| Fault severity | Maintenance urgency |
|---|---|
| CRITICAL | critical |
| HIGH | high |
| MEDIUM | medium |
| LOW | low |

Seven faults have direct triggers: Cell Imbalance, Contactor Weld, Thermal Trip (charging), Inverter Overcurrent, Resolver Calibration Error, Coolant Pump Failure, Refrigerant Pressure Low.

### Path 2 — History pattern matching (fallback)
If no active fault has a direct trigger, the engine checks the vehicle's 14-day fault history:

| Pattern | Threshold | Action | Urgency |
|---|---|---|---|
| BMS faults (codes 154, 17, 166) | 3+ in 14 days | battery_inspection | high |
| Charging faults (112, 235) | 2+ in 14 days | charging_maintenance | medium |
| Thermal faults (302, 319, 341) | 2+ in 14 days | thermal_inspection | high or critical |

If no threshold is met → "All vehicles healthy."

### Fault-specific vs vehicle-wide
Clicking a fault row queries the maintenance endpoint with that specific fault code — the suggestion shown is for the fault clicked, not the worst fault on the vehicle. "Show All" returns the highest-priority suggestion per vehicle across all faults.

---

## How the data transformation works

This is the core of what an OEM connector does. Raw Rivian telemetry is transformed into four Geotab standard data models on every poll:

### 1. Device (vehicle registration)
```
Rivian VIN → GeotabDevice
  VIN prefix determines model: 7PDSG = R1S, 7FMCU = EDV, other = R1T
  Device ID = MD5 hash of VIN (stable, reproducible)
  Groups = ["Rivian Fleet", "EV Vehicles"]
```

### 2. LogRecord (position + speed)
```
Rivian → Geotab
  latitude, longitude  →  unchanged
  speed_mph            →  speed km/h  (× 1.60934)
```
One Rivian status update → one LogRecord.

### 3. StatusData — 1 Rivian update → 7 Geotab records
Geotab's StatusData model stores exactly one float value per record, each tagged with a DiagnosticId. A single Rivian status update fans out into 7 separate records:

| Rivian field | Conversion | Geotab DiagnosticId |
|---|---|---|
| `battery_percent` | none | DiagnosticStateOfChargeId |
| `estimated_range_miles` | × 1.60934 → km | DiagnosticElectricVehicleRangeId |
| `odometer_km` | none | DiagnosticOdometerAdjustmentId |
| `cabin_temp_f` | (°F − 32) × 5/9 → °C | DiagnosticCabinTemperatureId |
| `charge_status` | CHARGING → 1.0, else 0.0 | DiagnosticChargeStateId |
| `motor_torque_nm` | none | DiagnosticMotorTorqueId |
| `regenerative_braking_active` | true → 1.0, false → 0.0 | DiagnosticRegenerativeBrakingId |

Using standard Geotab DiagnosticIds means Rivian data participates in existing MyGeotab exception rules, fuel/energy reports, and maintenance workflows without special configuration.

### 4. FaultData (diagnostic trouble codes)
```
Rivian DTC string "BMS_a154"
  → lookup in RIVIAN_FAULT_MAP
  → FaultData.code = 154  (integer)
  → FaultData.failure_mode_identifier = 2  (SAE J1939 FMI)
  → FaultData.diagnostic_name = "Cell Imbalance Detected"

Unknown codes not in the map:
  → code = 9999, fmi = 31 ("unknown/proprietary")
  → still appears in MyGeotab rather than being silently dropped
```

---

## API Endpoints

Full interactive explorer at `/docs`.

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/fleet` | All vehicles normalized to Geotab format |
| GET | `/api/vehicle/{vin}/raw` | Raw Rivian telemetry for one vehicle |
| GET | `/api/vehicle/{vin}/normalized` | Geotab-normalized data for one vehicle |
| GET | `/api/fleet/faults/scores` | Severity scores for all active faults |
| GET | `/api/vehicle/{vin}/maintenance` | Maintenance suggestion (add `?fault_code=` for fault-specific) |
| GET | `/api/vehicle/{vin}/fault-history` | Fault history log for one vehicle |
| POST | `/api/simulate/fault` | Inject a fault code onto a vehicle |
| DELETE | `/api/vehicle/{vin}/faults/{fault_code}` | Dismiss a specific active fault |
| DELETE | `/api/simulate/fault/{vin}` | Clear all injected faults from a vehicle |

**Valid fault codes for injection:**

| Code | Name | Severity |
|---|---|---|
| `BMS_a154` | Cell Imbalance Detected | CRITICAL |
| `BMS_a017` | Contactor Weld Detection | CRITICAL |
| `CHG_a112` | Thermal Trip (Charging) | CRITICAL |
| `DRV_a023` | Inverter Overcurrent | CRITICAL |
| `THM_a002` | Coolant Pump A Stuck | CRITICAL |
| `THM_a019` | Refrigerant Pressure Low | CRITICAL |
| `BMS_a066` | Charge Limit Restricted | HIGH |
| `CHG_a035` | Proximity Pilot Fault | HIGH |
| `VDM_a045` | Ride Height Sensor Out of Range | HIGH |
| `THM_a041` | Octovalve Position Error | HIGH |
| `DRV_a088` | Resolver Calibration Error | MEDIUM |
| `VDM_a004` | Compressor Overheat | MEDIUM |
| `VDM_a012` | Kinetic Fluid Pressure Low | MEDIUM |

---

## Simulated fleet

| VIN suffix | Model | Starting battery | Starting location |
|---|---|---|---|
| ...000001 | Rivian R1S | 82% | Toronto, ON |
| ...000002 | Rivian R1T | 45% | Toronto North |
| ...000003 | Rivian EDV | 91% | Toronto West |
| ...000004 | Rivian R1S | 19% | Toronto NE |
| ...000005 | Rivian R1T | 63% | Toronto SE |

Battery drains while driving, charges automatically below 20%. Position drifts to simulate movement. Speed varies randomly when unplugged.
