# Chapter 1 – Introduction

## 1.1 Project Background

Urban traffic signal networks are designed around fixed or adaptive cycle plans
that optimize throughput for *normal* traffic. Emergency vehicles (ambulances, fire
trucks, police) must periodically override this normal flow to reach an incident or
hospital as fast as possible. The mechanism that lets a signal network yield to an
emergency vehicle is called **Emergency Vehicle Preemption (EVP)**, and it sits
within the broader domain of **Intelligent Transportation Systems (ITS)**.

Most EVP deployments today are **reactive**: a signal only becomes aware of an
approaching emergency vehicle once it is within a short range (roughly 150–300
metres) of the intersection — typically via an optical strobe detector, RF/GPS
emitter, or acoustic siren detector mounted at the junction. On detection, the
signal controller immediately truncates its current phase and forces a green phase
in the emergency vehicle's direction of travel. When the vehicle clears the
junction, the controller resets to its normal cycle, usually within one cycle or
even instantly.

This project, the **Predictive Green Corridor System**, targets the same domain —
signal preemption for emergency vehicles — but reframes it as a *predictive,
multi-junction coordination* problem rather than a single-junction reactive
override, and treats the *return to normal operation* as a first-class part of the
problem rather than an afterthought.

The system is built and evaluated as a **traffic simulation**: a synthetic (and
optionally OpenStreetMap-derived) road network with signalized junctions,
background vehicle traffic, and a single ambulance agent, run in a discrete-event
simulator. This lets the coordination and recovery algorithms be validated and
measured before any real hardware or traffic-authority integration is considered.

## 1.2 Problem Statement

Existing reactive EVP systems have two structural weaknesses:

1. **Short detection horizon, single-junction scope.** Because the signal only
   reacts within a few hundred metres of the vehicle, there is no coordination
   across the multiple junctions the vehicle will pass through on its route. Each
   junction reacts independently and late, which can still leave the ambulance
   queued behind traffic that had no time to clear.
2. **Abrupt recovery.** Once the ambulance clears a junction, the signal resets to
   its normal cycle immediately. Traffic that was held during preemption is
   released all at once with no ramp-back, which creates a secondary shockwave of
   congestion and delay for ordinary vehicles at and near that junction.

There is currently no system in this project's scope of reference that:
- Predicts an ambulance's arrival time at *each* upcoming junction on its route
  (not just the next one), updating that prediction continuously as the vehicle
  moves, **and**
- Uses that prediction to pre-schedule a green corridor across multiple junctions
  ahead of time, **and**
- Restores each junction's normal timing gradually after the vehicle passes,
  instead of snapping back instantly.

## 1.3 Motivation

Field studies of deployed EVP systems already show that preemption in general
works: response-time improvements of 14–50% and up to 70% fewer emergency-vehicle
collisions have been reported. That validates the basic concept but says nothing
about *how well* the coordination and recovery are done.

Research specifically targeting proactive (predictive) preemption combined with a
graceful recovery phase has shown up to a **43% reduction in non-emergency traffic
delay** compared to purely reactive approaches — and the recovery phase alone was
responsible for roughly **21 percentage points** of that improvement. In other
words, a large share of the benefit of a "smarter" EVP system comes not from
detecting the ambulance earlier, but from how the signal network *lets go* of the
preemption afterward. That is a gap current reactive systems do not address, and it
is the specific gap this project targets: not proving preemption works (already
established), but building and measuring a coordination + recovery strategy that
narrows that gap in a controlled, reproducible simulation.

## 1.4 Project Objectives

The project's objectives are stated so they can be measured directly from
simulation output (baseline run vs. corridor+recovery run, same network, same
background traffic, same ambulance start/end):

1. **Reduce ambulance transit time** — measurably lower total travel time from
   start to destination under the predictive corridor mode compared to a
   no-preemption baseline.
2. **Reduce disruption to background traffic** — average delay imposed on
   non-emergency vehicles under corridor + recovery mode should not be
   dramatically worse than the no-preemption baseline, and should be measurably
   better than a naive reactive-preemption baseline (which resets instantly).
3. **Improve prediction accuracy over time** — the per-junction ETA prediction
   should converge toward the ambulance's actual arrival time as it gets closer
   (i.e., prediction error should shrink as new position data comes in, not stay
   flat).
4. **Bound worst-case disruption** — perpendicular/cross traffic at any
   coordinated junction should never be held beyond a configured maximum
   threshold, regardless of how the corridor schedule shifts.
5. **Produce automated, reproducible reporting** — every simulation run should
   automatically output transit-time, delay, and signal-state metrics/plots
   without manual data collection, so baseline and corridor runs can be compared
   directly.

(Role-based access and manual-processing reduction, listed as example objective
categories in the report template, are not directly applicable to a single-user
simulation tool at MVP stage; they are addressed under Section 1.5 as out of
scope for now, and would become relevant only if this system were extended toward
a multi-operator, real traffic-authority deployment.)

## 1.5 Scope of the Project

**Included (MVP scope):**
- A synthetic grid road network (and optionally a small OpenStreetMap-derived
  network) with signalized junctions running fixed-cycle timing plans.
- Background traffic agents generating normal congestion on the network.
- A single ambulance agent with a defined start point and destination.
- A shortest-*time* (not shortest-distance) routing module for the ambulance.
- A continuously-updated ETA prediction module for each junction on the
  ambulance's route.
- A corridor coordination module that pre-schedules green phases across multiple
  upcoming junctions, bounded by a maximum allowed hold time for cross traffic.
- A graceful recovery module that interpolates each junction back to its normal
  cycle over one to two cycles after the ambulance clears it.
- A naive reactive-preemption baseline mode (detect within ~200m, reset
  instantly) for comparison.
- Metrics and visualization: ambulance transit time, average background-traffic
  delay, and a signal-state timeline, computed automatically for each run.

**Excluded (out of scope for this project):**
- Integration with real, physical traffic signal controllers or V2X hardware.
- Ingestion of a live/real GPS feed (GPS is simulated).
- Coordinating more than one emergency vehicle at a time (multi-ambulance
  conflict resolution).
- Machine-learning-based traffic prediction (simple density/speed heuristics are
  used instead).
- Multi-operator role-based access control, authentication, or any production
  deployment concerns — this is a single-user research/demonstration tool.

## 1.6 Stakeholders

- **End users** — the person running and observing the simulation (in this
  project's context, primarily the student/developer and course
  evaluators); in a real-world extension, this role would map to EMS
  dispatch/drivers who benefit from a faster, more coordinated route.
- **Administrators** — whoever configures a simulation scenario: network layout,
  signal cycle plans, background traffic density, and the ambulance's
  start/destination.
- **System administrators** — whoever sets up and maintains the simulation
  environment itself (Python environment, simulation engine, dependencies).
- **External systems** — the simulation engine and mapping data sources the
  project depends on (e.g. a traffic simulation engine's Python API, and
  optionally OpenStreetMap data for real road network import). No real traffic
  authority systems are integrated at this stage.
- **Managers** — the course instructor/evaluator assessing the project against
  its stated objectives, and, in a real-world extension, a city traffic
  management authority that would ultimately own and approve any live
  deployment.

## 1.7 Assumptions and Constraints

- **Internet availability** — assumed available for installing dependencies and,
  optionally, for pulling a real road network extract from OpenStreetMap; not
  required at simulation runtime once the network and dependencies are in place.
- **Hardware limitations** — the project runs entirely as software simulation on
  a standard development laptop; no traffic-controller hardware, sensors, or
  embedded devices are involved.
- **Budget** — zero monetary budget assumed; only free, open-source tools and
  publicly available map data are used.
- **Security constraints** — no real personal data, real vehicle telemetry, or
  real traffic-control systems are touched, so this stays outside regulated data
  handling; if ever extended toward a real deployment, safety-critical
  certification and access-control requirements would apply and are explicitly
  out of scope here.
- **Development time** — the project is scoped to be completed within a single
  academic semester by a small (student-sized) team, which is why the MVP is
  explicitly bounded (Section 1.5) and phased (see
  [docs/BUILD-PLAN.md](../BUILD-PLAN.md)).
