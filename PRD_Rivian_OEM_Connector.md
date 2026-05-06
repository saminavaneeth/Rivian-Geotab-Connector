# Product Requirements Document
## Rivian OEM Connector for Geotab MyGeotab

| Field | Value |
|---|---|
| **Status** | Proposal — Draft v1.0 |
| **Author** | Sami Navaneeth |
| **Date** | May 5, 2026 |
| **Stakeholders** | OEM Partnerships, Fleet Product, Engineering, Sales |

---

## Executive Summary

Fleet managers operating mixed fleets today face a fragmentation problem: Rivian trucks and vans report data through Rivian's native FleetOS platform, while the rest of their fleet reports through Geotab MyGeotab. This forces dispatchers to context-switch between platforms, creating visibility gaps and degrading operational response time.

This PRD proposes a native OEM Connector that ingests Rivian vehicle telematics via Rivian's Vehicle API and normalizes it into Geotab's standard data models — making Rivian vehicles first-class citizens in MyGeotab alongside every other connected vehicle.

**Why Rivian, why now:**

Rivian has a documented OEM integration dataset in Geotab, but current coverage is limited and does not provide the same native, mixed-fleet MyGeotab experience as other OEM connectors. Amazon — an existing Geotab enterprise customer — operates 70,000+ Rivian EDV delivery vans on the same routes as their Geotab-managed vehicles. The Rivian connector closes that gap for Amazon and positions Geotab to capture a fast-growing segment of commercial EV fleets.

**Expected impact:** 5,000+ Rivian VINs managed in MyGeotab within 12 months of GA launch.

---

## 1. Problem Statement

### 1.1 The Fleet Fragmentation Problem

Modern commercial fleets are mixed. A logistics operator might run 200 Ford Transit GO-device vehicles alongside 50 new Rivian EDV delivery vans. Today, the Ford vehicles appear in MyGeotab with full telemetry — GPS, speed, faults, driver behavior. The Rivian vans are invisible to Geotab entirely. The dispatcher must open a second platform (Rivian FleetOS) to see any Rivian data.

This creates three specific failure modes:

1. **Dispatch errors**: A dispatcher assigns a Rivian EDV to a 180-mile route without knowing its current range is 140 miles. The vehicle strands a driver because range data was only visible in FleetOS — not the dispatch system.

2. **Maintenance blind spots**: A Rivian battery management fault fires at 2pm. The fleet manager doesn't see it until end of day because fault data isn't surfaced in MyGeotab. The vehicle completes 4 more hours of service before a technician is dispatched.

3. **Reporting fragmentation**: Monthly safety and utilization reports require manual data merging from two platforms. The CFO's fleet cost analysis excludes 20% of the fleet.

### 1.2 Why This Is a Product Problem, Not a Customer Problem

The temptation is to tell fleet operators to use Rivian FleetOS for Rivian vehicles and MyGeotab for everything else. The evidence says this doesn't work at scale:

- Fleet managers managing 100+ vehicles operate from a single dashboard. Switching platforms degrades response time by minutes — critical for live dispatch.
- Enterprise procurement teams buying fleet management software buy one platform. A product that doesn't cover their full fleet loses the deal to one that does.
- Geotab's own value proposition is unified fleet visibility. A gap in OEM coverage is a gap in that proposition.

### 1.3 The Amazon Signal

Amazon's 100,000-unit Rivian EDV order is the largest commercial EV fleet deployment in history. Amazon is already a Geotab enterprise customer. The fleet operations teams managing Amazon's Sprinter and Transit vans through Geotab are the same teams managing Rivian EDVs through FleetOS. The product gap is not hypothetical.

---

## 2. Market Opportunity

### 2.1 Rivian Commercial Fleet Size

| Metric | Value |
|---|---|
| Rivian EDVs delivered (Amazon, cumulative) | ~70,000 |
| Rivian R1T commercial fleet registrations (2024) | ~15,000 |
| Rivian EDV production capacity (2026) | 50,000/year |
| Projected Rivian commercial fleet (2027) | 150,000+ VINs |

### 2.2 Addressable Geotab Customer Overlap

Geotab manages 4.6M+ connected vehicles across 55,000 fleet customers. An estimated 8–12% of enterprise fleet customers operate or plan to operate Rivian vehicles alongside their existing Geotab-managed fleet. Conservative Year 1 addressable base: **5,000–8,000 Rivian VINs** within current Geotab enterprise accounts.

### 2.3 Competitive Context

| OEM | Geotab Connector? | Notes |
|---|---|---|
| Ford (including Pro E-Transit) | Yes | Direct Rivian commercial competitor |
| GM (BrightDrop EV600) | Yes | Commercial EV fleet |
| Stellantis (Ram ProMaster EV) | Yes | Delivery fleet competitor |
| Mercedes eSprinter | Yes | Direct competitor to Rivian EDV |
| **Rivian (R1T, R1S, EDV)** | **Yes (OEM dataset documented)** | Existing OEM integration dataset is available, but a full native connector would deliver deeper MyGeotab mixed-fleet support |
| Canoo | No | Smaller fleet, lower priority |

Rivian has a documented OEM dataset in Geotab, but it is still an important gap for full native MyGeotab mixed-fleet visibility and operations. Its absence in the broader native connector portfolio is increasingly visible in enterprise sales conversations.

### 2.4 Strategic Rationale

- **Expand EV connector portfolio**: Geotab has Polestar, Volvo, and Hyundai for passenger EVs. Rivian is the first native commercial EV connector — a differentiated capability.
- **Deepen Amazon relationship**: A Rivian connector turns a partial Geotab deployment into a full-fleet deployment for Amazon's largest operations.
- **Rivian Commercial co-sell motion**: Rivian's commercial sales team is actively looking for software partnerships to differentiate their fleet offering. This connector creates a co-sell opportunity.

---

## 3. User Personas

### Persona 1: Fleet Operations Manager (Primary)
**Name:** Marcus, Fleet Operations Manager, Regional Logistics Company  
**Fleet:** 180 vehicles — 130 Ford Transit (Geotab GO devices), 50 Rivian EDVs  
**Pain today:** Opens MyGeotab to start his day, immediately has to open FleetOS in a second tab to see his Rivians. Any cross-fleet report requires manual data export and merge. Has requested a unified view for 18 months.  
**What he needs:** All 180 vehicles in one map, one exception report, one utilization dashboard. Nothing more.

### Persona 2: Fleet Dispatcher (Secondary)
**Name:** Priya, Dispatcher, E-Commerce Distribution Center  
**Task:** Assigns 40 delivery vehicles to routes each morning. Needs to match vehicle range to route distance.  
**Pain today:** Range data for Rivian EDVs is not in the dispatch system (MyGeotab). She estimates Rivian range from memory or calls drivers to check. Two stranded vehicles in the past quarter.  
**What she needs:** Current range estimate for every vehicle — displayed inline with GPS and speed — before she assigns routes.

### Persona 3: EV Fleet Transition Lead (Emerging)
**Name:** David, VP Fleet Strategy, Parcel Delivery Company  
**Task:** Building a 3-year EV transition roadmap. Needs to present ICE vs. EV total cost of ownership to the CFO.  
**Pain today:** Rivian uptime, charge cost, and range utilization data lives in FleetOS. ICE vehicle data lives in MyGeotab. Building the comparison requires a data analyst and takes 2 weeks per reporting cycle.  
**What he needs:** A single Geotab report comparing ICE fuel cost vs. EV charge cost, with actual range utilization data, updated daily.

---

## 4. Jobs To Be Done

| When I… | I want to… | So I can… |
|---|---|---|
| Check my fleet at the start of the day | See all vehicles — Rivian and non-Rivian — in one map view | Identify issues without switching platforms |
| Assign a Rivian EDV to a route | See its current battery state of charge and range estimate | Avoid stranding drivers on long routes |
| Review end-of-day exception events | See Rivian fault codes alongside GO device exceptions | Ensure nothing falls through the cracks |
| Build a monthly fleet utilization report | Pull data for all vehicles from a single export | Deliver accurate reports without manual merging |
| A Rivian has a charging fault | Get an alert in MyGeotab like any other vehicle fault | Dispatch a technician before the next shift |

---

## 5. Proposed Solution

A native OEM Connector that:

1. **Authenticates** with Rivian's Vehicle API using OAuth2 credentials entered by the fleet operator in a MyGeotab Add-in setup wizard
2. **Polls** Rivian's API on a configurable interval (default: 10 seconds when vehicle is moving; 60 seconds when parked)
3. **Normalizes** Rivian's proprietary telemetry into Geotab's standard data models via a transformation layer
4. **Writes** normalized data to MyGeotab's standard pipeline (Data Intake Gateway) — making Rivian vehicles indistinguishable from GO-device vehicles in dashboards, reports, and exception rules

The connector lives outside MyGeotab as a standalone service (consistent with how other OEM connectors are architected), communicating with Geotab via the DIG API.

---

## 6. Functional Requirements

### P0 — MVP (Required for Beta)

| # | Requirement |
|---|---|
| F-01 | Fleet operator can enter Rivian API credentials (Client ID, Client Secret) via a MyGeotab Add-in setup wizard |
| F-02 | On first connection, connector creates a Geotab `Device` record for each VIN in the Rivian account |
| F-03 | Connector syncs GPS `LogRecord` data (lat, lon, speed in km/h, heading) at configurable interval (default 10s moving, 60s parked) |
| F-04 | Connector syncs `StatusData` for: State of Charge (%), Estimated Range (km), Odometer (km), Charging State, Motor Torque (Nm), Cabin Temperature (°C), Regenerative Braking active |
| F-05 | Connector syncs `FaultData`: Rivian DTCs are normalized to Geotab fault code + failure mode identifier using a maintained lookup table |
| F-06 | Rivian vehicles are visible in MyGeotab alongside GO-device vehicles in the same database (mixed fleet support) |
| F-07 | Connector supports Rivian R1T, R1S, and EDV body types |
| F-08 | Data is available in MyGeotab within 60 seconds of the vehicle event |

### P1 — V1.1 (Post-Beta)

| # | Requirement |
|---|---|
| F-09 | Charging session history: start time, end time, kWh added, charger type (L1/L2/DC Fast), estimated cost |
| F-10 | Cabin preconditioning status and scheduled preconditioning events |
| F-11 | Regenerative braking events logged as `ExceptionEvent` records |
| F-12 | Driver assignment: Rivian driver identity mapped to Geotab `DriverKey` via VIN + session lookup |
| F-13 | MyGeotab Add-in: Rivian-specific vehicle detail panel (battery cell health, thermal management state, charge schedule) |

### P2 — Future

| # | Requirement |
|---|---|
| F-14 | Predictive battery degradation alerts using Rivian battery health trend data |
| F-15 | V2G (vehicle-to-grid) status integration for fleets with managed charging infrastructure |
| F-16 | Rivian Spaces (charging network) session data integration |

---

## 7. Non-Functional Requirements

| Category | Requirement |
|---|---|
| **Latency** | 95th percentile: vehicle event visible in MyGeotab within 60 seconds |
| **Reliability** | LogRecord data completeness ≥ 99.5% (vs. vehicle active time) |
| **Scale** | Support up to 10,000 Rivian VINs per MyGeotab database instance |
| **Availability** | Connector service uptime ≥ 99.5% (consistent with other OEM connectors) |
| **Security** | OAuth2 credential refresh; credentials stored in Geotab secrets manager; no VIN or SOC data stored outside Geotab's standard data pipeline |
| **Compatibility** | Rivian vehicles and GO-device vehicles must coexist in the same MyGeotab database with no UI differentiation |
| **API versioning** | Connector must detect and handle Rivian API version changes without silent data loss |

---

## 8. Technical Architecture

```
Rivian Vehicle
      │
      ▼  (cellular / embedded telematics)
Rivian Cloud API  ──────────────────────────────────┐
      │                                              │
      ▼  (OAuth2, REST/webhook, 30s push interval)   │
┌─────────────────────────────────────┐              │
│  Rivian-Geotab Connector Service    │              │
│  ┌─────────────────────────────┐    │              │
│  │  Auth Manager (OAuth2)      │    │   Rivian API │
│  │  Token refresh & rotation   │    │   webhook    │
│  ├─────────────────────────────┤    │   fallback   │
│  │  Data Normalizer            │◄───┘              │
│  │  RivianStatus → LogRecord   │                   │
│  │  RivianStatus → StatusData[]│                   │
│  │  RivianFault  → FaultData   │                   │
│  │  VIN → Device provisioning  │                   │
│  ├─────────────────────────────┤                   │
│  │  Rate Limiter / Retry Logic │                   │
│  │  Dead-letter queue (DLQ)    │                   │
│  └─────────────────────────────┘                   │
└───────────────────┬─────────────────────────────────┘
                    │  (HTTPS, Geotab DIG API)
                    ▼
         Geotab Data Intake Gateway
                    │
                    ▼
            MyGeotab Database
                    │
                    ▼
     Fleet Manager in MyGeotab UI
     (same view as all other vehicles)
```

### Key Design Decisions

**1. One Rivian status update → multiple StatusData records**

Geotab's `StatusData` model is one-metric-per-record (a single `data: float` field). A single Rivian vehicle status payload contains 7+ metrics (SOC, range, odometer, cabin temp, charge state, torque, regen braking). The normalizer must fan these out into 7 separate `StatusData` records. This is consistent with how all other OEM connectors handle Geotab's data model.

**2. Push + poll hybrid**

Rivian's API supports webhooks (push) for state changes and polling for periodic snapshots. The connector uses webhooks as the primary path (lower latency) and falls back to polling (30s interval) when webhook delivery fails. This meets the 60-second latency SLA.

**3. DTC normalization table**

Rivian fault codes follow the format `RIV-{system}-{code}` (e.g., `RIV-BMS-0042`). These must be mapped to Geotab's `(code: int, failureModeIdentifier: int, diagnosticName: string)` tuple. The mapping table is maintained by the connector team and versioned alongside the connector code. Unknown fault codes are passed through with a `RivianUnknownFault` diagnostic name to avoid silent data loss.

**4. VIN-based Device provisioning**

On first connection, the connector creates a Geotab `Device` record for each VIN using the pattern `device.id = "b" + hash(VIN)`. This ensures idempotency — re-running provisioning never creates duplicates. The device `groups` property is set to `["Rivian Fleet", "EV Vehicles"]` for immediate filterability in MyGeotab.

---

## 9. Data Mapping Reference

### 9.1 Rivian API → Geotab Standard Models

| Rivian Field | Example Value | Geotab Model | Geotab Diagnostic ID |
|---|---|---|---|
| `battery_percent` | `78.2` | StatusData | `DiagnosticStateOfChargeId` |
| `estimated_range_miles` | `231.0` | StatusData | `DiagnosticElectricVehicleRangeId` (converted to km) |
| `odometer_km` | `12400.5` | StatusData | `DiagnosticOdometerAdjustmentId` |
| `cabin_temp_f` | `68.0` | StatusData | `DiagnosticCabinTemperatureId` (converted to °C) |
| `charge_status` | `"CHARGING"` | StatusData | `DiagnosticChargeStateId` (1.0 = charging, 0.0 = not) |
| `motor_torque_nm` | `412.0` | StatusData | `DiagnosticMotorTorqueId` |
| `regenerative_braking_active` | `true` | StatusData | `DiagnosticRegenerativeBrakingId` (1.0 = active) |
| `latitude` / `longitude` | `43.6532, -79.3832` | LogRecord | (built-in GPS fields) |
| `speed_mph` | `45.0` | LogRecord | (built-in speed field, converted to km/h) |
| `fault_codes[]` | `["RIV-BMS-0042"]` | FaultData | Normalized via DTC lookup table |

### 9.2 Rivian DTC → Geotab FaultData

| Rivian DTC | Geotab Code | FMI | Geotab Diagnostic Name |
|---|---|---|---|
| `RIV-BMS-0042` | 42 | 14 | Battery Management System Fault |
| `RIV-MCU-0018` | 18 | 31 | Motor Control Unit Warning |
| `RIV-CHG-0071` | 71 | 9  | Charging System Fault |
| `RIV-TMS-0033` | 33 | 7  | Thermal Management System Alert |
| Unknown | pass-through | 0  | RivianUnknownFault (code preserved) |

---

## 10. User Stories & Acceptance Criteria

### US-01: Vehicle provisioning

**Story:** As a fleet manager, when I connect my Rivian account to MyGeotab, I want all my Rivian vehicles to appear automatically so I don't have to add them manually.

**Acceptance criteria:**
- Given a fleet manager has entered valid Rivian API credentials in the Add-in wizard
- When the connector completes initial sync
- Then all VINs associated with that Rivian account appear as Devices in MyGeotab within 5 minutes
- And each device is assigned to the "Rivian Fleet" and "EV Vehicles" groups
- And re-running provisioning does not create duplicate Devices

---

### US-02: Live GPS tracking

**Story:** As a dispatcher, I want to see Rivian vehicles on the MyGeotab map so I can monitor live locations alongside my other vehicles.

**Acceptance criteria:**
- Given a Rivian vehicle is powered on and moving
- When the dispatcher opens the MyGeotab live map
- Then the Rivian vehicle appears as a map marker that updates at least every 15 seconds
- And the vehicle is indistinguishable from GO-device vehicles in the map UI

---

### US-03: Battery and range visibility

**Story:** As a dispatcher, I want to see each Rivian vehicle's battery percentage and estimated range so I can assign them to appropriately-sized routes.

**Acceptance criteria:**
- Given a Rivian vehicle is connected and the connector is running
- When the dispatcher views any vehicle in the fleet
- Then the battery state of charge (%) and estimated range (km) are visible in the vehicle detail panel
- And both values update within 60 seconds of a change on the vehicle

---

### US-04: Fault detection

**Story:** As a fleet manager, I want Rivian fault codes to appear in MyGeotab exception events so I don't have to check FleetOS for alerts.

**Acceptance criteria:**
- Given a Rivian vehicle has an active fault code (e.g., RIV-BMS-0042)
- When the connector syncs that vehicle's telemetry
- Then a FaultData record appears in MyGeotab with the human-readable diagnostic name
- And the fault triggers any applicable MyGeotab exception rules (e.g., "Vehicle has fault — notify maintenance")
- And the fault is visible within 60 seconds of the DTC being set on the vehicle

---

### US-05: Mixed fleet reporting

**Story:** As a fleet operations manager, I want to run utilization and exception reports that include Rivian vehicles alongside my GO-device vehicles.

**Acceptance criteria:**
- Given a database contains both Rivian-connected vehicles and GO-device vehicles
- When the manager runs a standard MyGeotab exception summary or utilization report
- Then Rivian vehicles are included in report results with no special configuration
- And filter-by-group works correctly (Rivian Fleet group returns only Rivian vehicles)

---

## 11. Success Metrics

### Primary KPIs

| Metric | Target (Year 1) | Measurement Method |
|---|---|---|
| Rivian VINs managed in MyGeotab | 5,000 | Count of Rivian Devices in production databases |
| Fleet customers with ≥1 Rivian vehicle connected | 50 | Customer account analysis |

### Data Quality KPIs

| Metric | Target | Measurement Method |
|---|---|---|
| LogRecord completeness | ≥ 99.5% (vs. vehicle active time) | DIG ingestion audit |
| StatusData sync latency (p95) | < 60 seconds | Timestamp delta: Rivian API event → MyGeotab record |
| Fault detection latency (p95) | < 60 seconds | Timestamp delta: DTC set → FaultData created |
| DTC normalization coverage | ≥ 95% of observed fault codes | Unknown fault code rate in FaultData |

### Customer Experience KPIs

| Metric | Target | Measurement Method |
|---|---|---|
| Time-to-connect (credential entry → first vehicle visible) | Median < 5 minutes | Connector provisioning telemetry |
| Fleet manager NPS (mixed EV/ICE fleet visibility) | ≥ 50 | Post-activation survey (n=30 beta customers) |
| Support tickets: Rivian data accuracy issues | < 2% of connected fleet | Support ticket tagging |

---

## 12. Go-to-Market Plan

### Phase 1: Private Beta (M0–M6)

- **Participants**: 3–5 fleet operators with both existing Geotab accounts and active Rivian commercial fleets; Amazon logistics as primary target
- **Success gate**: All P0 requirements met; LogRecord completeness ≥ 99.5%; at least 2 customers express intent to expand
- **Key deliverable**: Rivian API partnership agreement signed; connector deployed to beta environment

### Phase 2: General Availability (M7)

- **Geotab Marketplace listing**: "Rivian OEM Connector" — free for Geotab customers, consistent with other OEM connectors
- **Rivian Commercial partner announcement**: Joint press release with Rivian's fleet partnerships team
- **Sales enablement**: Updated competitive battlecard (Geotab now covers Rivian; competitors do not); fleet migration guide for customers moving Rivian vehicles from FleetOS to MyGeotab

### Phase 3: Expansion (M8–M12)

- **Amazon rollout**: Full EDV fleet deployment through existing Geotab enterprise account
- **V1.1 features**: Charging session history, cabin preconditioning, driver assignment
- **New OEM signal**: Lessons learned from Rivian connector inform prioritization of next commercial EV connector (Canoo, BrightDrop, Arrival)

---

## 13. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Rivian API v1 introduces breaking changes | Medium | High | Version-negotiated connector; monitor Rivian developer changelog; automated regression tests against API contract |
| Data latency exceeds 60s SLA due to Rivian API reliability | Medium | Medium | Implement dead-letter queue for failed syncs; expose connector health status in MyGeotab; set clear latency SLA in customer onboarding |
| Amazon exclusivity clause in Rivian commercial partnership prevents co-sell | Low | High | Legal review before GA announcement; treat Amazon as expansion, not dependency |
| SOC and location data raises privacy concerns in EU GDPR context | Medium | Medium | Follow Geotab's existing GDPR data processing framework; no additional data storage beyond standard MyGeotab pipeline; include privacy impact assessment in legal review |
| Rivian changes authentication model (API key → OAuth2 upgrade) | Low | Medium | OAuth2 token rotation already implemented; monitor Rivian developer communications |
| Connector launch delays due to Rivian API access approval process | Medium | Low | Begin API access negotiation in M0; build connector against Rivian sandbox during partnership discussions |

---

## 14. Open Questions

1. **Rivian API access model**: Does Rivian offer a fleet API with multi-VIN access, or must each vehicle owner authorize separately? This affects the credential setup UX significantly.

2. **Data ownership**: Does the fleet operator or Rivian own the telematics data? This has implications for data retention policies and customer agreements.

3. **Existing Rivian customers**: Are there current Geotab customers who have already attempted to connect Rivian vehicles via workarounds (e.g., manual data exports)? If yes, what is the migration path?

4. **Pricing model**: OEM connectors are currently free to Geotab customers. Is Rivian expecting a revenue-share arrangement for data access? This affects the business case.

5. **Geofencing and Rivian FleetOS**: Some Rivian customers use FleetOS for geofencing capabilities. Do we need to replicate geofence rule support in MyGeotab for full parity?

---

## 15. Timeline

```
M0  ──── M2  ──── M4  ──── M6  ──── M8  ──── M10 ──── M12
│         │         │         │         │         │         │
Partner   Rivian    Connector Beta      GA        V1.1     Amazon
agreement API       built &   launch   launch    features  full
signed    access    tested    (3 fleets)(Market- ship      rollout
          granted             pass)     place)
```

---

## Appendix A: Competitive OEM Connector Reference

Geotab's existing OEM connector portfolio for reference:

| OEM | Vehicle Types | Key EV Data |
|---|---|---|
| Ford Pro | Transit, F-150 Lightning, E-Transit | SOC, range, charging status |
| General Motors | Silverado EV, BrightDrop EV600 | SOC, range |
| Polestar | Polestar 2, 3, 4 | SOC, range, thermal state |
| Hyundai/Kia | Ioniq 5, EV6 (EU) | SOC, range, ADAS metrics |
| Volvo | EX90, EC40 (ICE + BEV) | SOC, range, battery temp |

Rivian EDV fills the commercial delivery van gap not covered by any existing connector.

---

*This document accompanies a working prototype connector available at `github.com/[handle]/rivian-geotab-connector`. The prototype demonstrates the data normalization layer and fleet dashboard described in Section 8.*
