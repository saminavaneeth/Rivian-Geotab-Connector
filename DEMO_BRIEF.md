# Rivian × Geotab OEM Connector — Product Demo Brief

**Prepared by:** Sami Navaneeth
**For:** Geotab OEM Connectors — Senior PM Interview
**Live demo:** https://rivian-geotab-connector.onrender.com
**PRD:** Available in the repository alongside the demo

---

## Why I built this

Before our conversations about the role, I spent time understanding how Geotab's OEM Connector ecosystem actually works — the Data Intake Gateway, the normalization model, the diagnostic ID space, and the connector pattern used by existing integrations like Ford Pro.

I then built a working prototype of a connector that doesn't exist yet: **Rivian**.

Rivian is not currently a full native MyGeotab connector. Amazon — already a Geotab enterprise customer — operates 70,000+ Rivian EDV delivery vans on the same routes as their Geotab-managed vehicles. The fleet ops teams running Amazon's Sprinter and Transit vans through MyGeotab are the same teams managing Rivian EDVs through FleetOS. That is a product gap with a named customer attached to it.

This demo is my way of showing how I think about a problem before I'm hired to solve it.

---

## What the demo is

A live FastAPI service that:

1. **Simulates Rivian's Vehicle API** — generates realistic telemetry for 5 vehicles (R1T, R1S, EDV) with live battery drain, position drift, charging cycles, and fault events
2. **Runs a normalization engine** — transforms Rivian's proprietary data format into Geotab's standard data models (LogRecord, StatusData × 7, FaultData, Device)
3. **Serves a dispatcher dashboard** — showing the normalized data as a fleet operator would use it in MyGeotab

The code is real. The normalization logic, the Geotab diagnostic IDs, the DTC lookup table — all of it reflects how an actual connector would work.

---

## The product decisions I made

### 1. Rivian, not a generic connector

I chose Rivian specifically because it sits at the intersection of three things: an existing Geotab enterprise customer (Amazon) with an immediate gap, a direct competitive threat to Ford Pro E-Transit (which already has a Geotab connector), and a public developer API that makes the integration technically feasible. That's a defensible GTM story, not just a tech exercise.

### 2. Dispatcher as the primary user, not fleet manager

Most OEM connector demos show raw telemetry. I focused on what a **dispatcher** does with it — specifically, the fault triage workflow. A dispatcher doesn't care about raw DTC codes. They need to know: which vehicle needs attention right now, how urgent is it, and what action do they take?

The dashboard reflects this: faults are scored and sorted by severity (CRITICAL → HIGH → MEDIUM), each fault links to a specific maintenance action, and dismissal is an explicit dispatcher decision — not an auto-clear timer.

### 3. Fault-to-maintenance traceability

I built a two-path maintenance suggestion engine:

- **Immediate path**: active fault → MAINTENANCE_TRIGGERS lookup → urgency derived from fault severity (CRITICAL fault = critical urgency card). The urgency matches the fault severity — no mismatch between what the dispatcher sees in the fault panel and what they see in the maintenance panel.
- **Pattern path**: fault history over 14 days → threshold triggers (3+ BMS faults → battery inspection). This mirrors how a real fleet maintenance team would use historical fault data.

When a dispatcher clicks a specific fault, they see the maintenance suggestion for *that fault* — not the highest-priority issue on the vehicle. This distinction matters: if a vehicle has both a CRITICAL battery fault and a MEDIUM resolver error, the dispatcher clicking the resolver error needs the resolver action, not the battery action.

### 4. Data model fidelity

The key design decision in any Geotab OEM connector is the **1-to-many fan-out on StatusData**: Geotab's model stores one float per diagnostic record, so a single Rivian status update expands into 7 separate StatusData records (SOC, range, odometer, cabin temp, charge state, motor torque, regenerative braking). Each maps to a standard Geotab DiagnosticId — which is what lets Rivian data participate in existing MyGeotab exception rules, fuel reports, and maintenance workflows without special-casing.

This is not obvious from reading Geotab's public docs. I worked through it because it's the detail that separates a real connector from a data dump.

### 5. Fault persistence across restarts

On Render's free tier, the server process restarts after inactivity. I added file-based fault state persistence (`fault_state.json`) so the dispatcher's active fault queue survives server restarts — written on every fault mutation, loaded on startup. A real connector would use Geotab's database, but the pattern is the same.

---

## What the P0/P1/P2 breakdown says about how I prioritize

The PRD in the repository covers the full feature set. Here's the reasoning behind the tier structure:

**P0 (MVP):** Everything needed to make Rivian vehicles appear in MyGeotab with correct data. GPS, SOC, range, odometer, charge state, fault codes, vehicle provisioning. No Rivian-specific features — just parity with what any connected vehicle provides. This is the baseline a fleet manager needs to stop using two platforms.

**P1 (V1.1):** Features that are Rivian-specific value-adds — charging session history, cabin preconditioning, driver mapping, regenerative braking. These are the things that make the connector genuinely better than a generic GO device for EV fleet operators.

**P2 (Future):** Predictive battery degradation, V2G status, Rivian Spaces integration. These require deeper partnership and more data access than a v1 integration justifies.

The ordering is deliberate: get fleet managers off two platforms first (P0), then give them EV-specific superpowers (P1), then differentiate against other EV platforms (P2).

---

## What I'd do next if this were a real project

1. **OEM partnership alignment** — Rivian has a commercial API but production access requires a partnership agreement. The first milestone is that agreement, not the code. I'd involve Geotab's OEM partnerships team and Rivian's commercial sales team early.

2. **Amazon as design partner** — not a beta customer, a design partner. The connector should be built around their actual dispatch workflow, not a hypothetical one. Two or three sessions with their fleet ops team would reshape the P0 feature set.

3. **Connector reliability SLA** — 99.5% LogRecord completeness vs. vehicle active time. This is the metric that separates a real production connector from a demo. It requires rate limiting, retry logic, and latency monitoring against Rivian's API uptime.

4. **Mixed-fleet exception rules** — the real value unlock for enterprise customers is exception rules that span vehicle types. A "low range for assigned route" exception that covers both Ford Transit GO devices and Rivian EDVs in the same rule. That's a Geotab platform feature enabled by the connector, not part of the connector itself — but it's the thing that drives enterprise NPS.

---

## The full artifacts

| Artifact | What it shows |
|---|---|
| Live demo | Working normalization engine, dispatcher workflow, fault-to-maintenance traceability |
| PRD | 15-section product spec: problem, market sizing, personas, JTBD, P0/P1/P2 requirements, data mapping, NFRs, success metrics, GTM, risks, timeline |
| Source code | FastAPI normalization engine, Rivian DTC lookup, data model transformation, fault scoring |

The PRD can be read independently of the code. The code is deployable without reading the PRD. That separation is intentional — the PM artifact and the engineering artifact should stand on their own.

---

*I'm happy to walk through any part of this in more detail — the product decisions, the technical architecture, the GTM thinking, or the roadmap prioritization. This is how I approach a new domain before I start asking other people questions about it.*

— Sami Navaneeth
