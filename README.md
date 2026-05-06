# Rivian × Geotab OEM Connector — Demo

A working prototype demonstrating how a Rivian OEM telematics connector would integrate into Geotab's MyGeotab platform.

## What it shows

- **Data normalization**: Rivian's proprietary telemetry format → Geotab standard models (LogRecord, StatusData, FaultData)
- **Live fleet dashboard**: 5 simulated Rivian vehicles updating every 3 seconds
- **Mixed EV data**: State of charge, range, charging status, motor torque, cabin temp, fault codes
- **The connector's job**: Side-by-side view of raw Rivian API format vs normalized Geotab format

## Setup (3 steps)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start the connector service
python main.py

# 3. Open the dashboard
# http://localhost:8000
```

## Key URLs

| URL | What you see |
|-----|-------------|
| `http://localhost:8000` | Live fleet dashboard |
| `http://localhost:8000/docs` | FastAPI Swagger UI — execute live API calls |
| `http://localhost:8000/api/fleet` | All vehicles, normalized to Geotab format |
| `http://localhost:8000/api/vehicle/{vin}/raw` | Raw Rivian API format |
| `http://localhost:8000/api/vehicle/{vin}/normalized` | Geotab normalized format |

## Demo flow (for the interview)

1. Open the dashboard — show 5 live Rivian vehicles updating in real time
2. Click a vehicle card — the data pipeline panel shows raw vs normalized JSON side by side
3. Open `/docs` in another tab — execute `POST /api/simulate/fault` to inject a fault
4. Watch the fault badge appear on the vehicle card within 3 seconds
5. Explain the normalization: 1 Rivian status update → 7 Geotab StatusData records (one per diagnostic)

## Architecture

```
Rivian Vehicle
     ↓
Rivian Cloud API  (simulated by MockRivianFleet in main.py)
     ↓
RivianGeotabConnector  (normalize_position / normalize_status / normalize_faults)
     ↓
Geotab Data Intake Gateway  (represented by /api/* endpoints)
     ↓
MyGeotab Dashboard  (index.html)
```

## Why Rivian?

Rivian is not yet a Geotab OEM partner. Amazon — an existing Geotab customer — operates 70,000+ Rivian EDV delivery vans on the same routes as their Geotab-managed vehicles. This connector closes that visibility gap. See `PRD_Rivian_OEM_Connector.md` for the full product case.
