# FOUNDLAB | GOOGLE CLOUD RELIABILITY ENGINEERING CHALLENGE

**Version:** 1.0  
**Date:** 2026-10-11  
**Track:** Cloud Architect / Principal Infrastructure Engineer / SRE  
**Reference:** Google Cloud Infrastructure Reliability Guide  
**Classification:** Independent public engineering exercise, synthetic workload  
**Challenge name:** **FAILURE IS A CONTRACT**  
**Motto:** **Don't claim resilience. Demonstrate recovery.**

> **The assignment**  
> Design, implement, test, and defend the reliability of a small but consequential Google Cloud workload under compute failure, dependency disruption, asynchronous redelivery, sustained load, and simulated loss of a primary region. Prove behavior with reproducible evidence, not architecture diagrams alone.

**IMPORTANT — assessment status:** This file specifies an exercise. It does **not** report a deployment, completed test, measured SLO, verified disaster recovery, or Google Cloud certification. All target numbers below are **exercise acceptance targets**, not existing FoundLab production SLOs.

---

## Part 1 — Reliability fundamentals and boundaries

Reliable cloud infrastructure is not synonymous with deploying more instances. Availability of a user journey is determined by its dependencies, application correctness, capacity, recovery procedures, and operational controls. Identify the actual failure domains of each critical resource and whether its location scope is zonal, regional, multi-region, or global. Distinguish a Google Cloud product SLA from an **application SLO**.

### Required analysis

1. Map every component's **location scope**, shared dependencies, and failure domains. Include the control plane and operational dependencies as possible failure modes when material.
2. Classify each component into `critical path`, `asynchronous/recoverable`, or `optional/degradable`.
3. Define *user-visible* reliability for each journey, not only container uptime. An HTTP 202 is a successful admission only if the operation is durably admitted under the stated persistence contract.
4. Select a deployment archetype and justify **why single region, regional HA, or multi-region** is proportionate to the SLO, RTO, RPO, operational complexity, cost, and data residency.
5. Explicitly distinguish **assumptions**, **simulated evidence**, **cloud-observed evidence**, and **not tested**.

Google Cloud's reference targets for deployment-location availability are illustrative infrastructure targets and **not automatic application guarantees**. Product-specific SLAs and end-to-end reliability depend on the actual stack. See official sources at the end.

---

## Part 2 — Synthetic workload

### Scenario: `Atlas Operations API`

Build a fictional, tenant-scoped operations service that receives requests, durably admits them, processes them asynchronously, and exposes an auditable terminal outcome. It has no connection to REX Guard, FoundLab's private architecture, customers, or real financial transactions.

**Required operations**

- `POST /v1/jobs`: accepts a validated operation with an idempotency key; returns a stable job ID and admission state only after the chosen durable admission boundary succeeds.
- `GET /v1/jobs/{id}`: shows `ACCEPTED`, `PROCESSING`, `SUCCEEDED`, `FAILED`, or `UNKNOWN` and a consistent operation history.
- `GET /health/live`: answers whether the process is running. Does **not** claim dependencies are operational.
- `GET /health/ready`: states whether the instance can safely receive work given its critical dependencies. Its usage in routing/health mechanisms must be specified, not assumed.
- A background worker updates a **synthetic target ledger** (e.g., `applied_jobs`), idempotently.

**Mandatory invariants**

1. One logical command must not apply its effect twice, even if the message or HTTP request is delivered more than once. Document the chosen scope and concurrency guarantees.
2. An admitted job must not silently disappear. If a guarantee is bounded by the persistence/replication design, disclose that bound and measure what happens during recovery.
3. A timeout after sending a command cannot automatically be interpreted as failure. Use a safe `UNKNOWN`/reconciliation path where necessary.
4. Failure of a noncritical component must not take down unrelated read-only or health functionality without justification.
5. Failed dependency checks, excessive load, and recovery must yield intentional outcomes, not uncontrolled duplicates or hidden data corruption.
6. Tenant A must not read or change Tenant B jobs. No secret or PII may be used in fixtures.

### Technology choices (not all mandatory)

| Capability | Suggested GCP option | Decision to justify |
|---|---|---|
| HTTP application | Cloud Run | Region, scaling, cold starts, readiness, backpressure |
| Durable storage | Cloud SQL / Firestore / Spanner | Persistence boundary, consistency, backup, regional recovery |
| Background delivery | Cloud Tasks or Pub/Sub | Retry semantics, delivery guarantees, duplicate-handling |
| Monitoring | Cloud Monitoring, Logging, Trace | User-journey SLI, data quality, cost, recovery visibility |
| Build / deployment | GitHub Actions + Terraform | Reproducibility, approvals, rollback, least privilege |
| Multi-region entry | Global external Application Load Balancer + Cloud Run serverless NEGs, with a verified health mechanism | Health-based routing, failover/failback, global configuration risk |

**Non-negotiable:** In a Cloud Run multi-region configuration, **multiple backends alone do not prove automatic failover**. Validate the exact routing behavior and the availability of a supported health-based failover mechanism. Likewise, Cloud Tasks and ordinary Pub/Sub flows need application-level idempotency; do not assert exactly-once business effects based on message delivery claims.

---

## Part 3 — Reliability requirements and SLO contract

Define precise SLIs from the **user's perspective**. The following targets are **assigned for this exercise**, subject to evidence; they are not assertions about Google Cloud guarantees.

### Baseline objectives — regional phase

| Requirement | Assigned target | Measurement / interpretation |
|---|---|---|
| API successful admission | **99.95%** over a rolling 30-day window | Eligible valid `POST /jobs` operations admitted durably / total eligible valid attempts, excluding only specified client errors |
| Read availability | **99.95%** over a rolling 30-day window | Successful and correct `GET /jobs` responses / eligible reads |
| Admission latency | **p95 <= 1,000 ms** at exercise baseline load | End-to-end, client-observed; count timeouts and errors separately |
| Job completion latency | **p95 <= 60 s** at baseline | Accepted-to-terminal `SUCCEEDED` (excluding explicitly invalid commands); publish queue depth and backlog |
| Duplicate business effects | **0** across specified injected duplicate/retry cases | Compare immutable logical operation IDs and the synthetic target ledger |
| Undetected lost admitted jobs | **0** in normal, duplicate, and simulated dependency-failure test cases | Reconciliation must identify any nonterminal admitted operation |
| Observability | **100% of sampled fault scenarios** have correlation IDs and structured evidence | Trace or linked request/job/failure identifiers; identify missing spans honestly |

**Exercise workload assumptions:** Start with **10 valid requests/second for 5 minutes**, then run a **5× burst for 2 minutes**. If cost or quota prevents cloud validation, execute locally and mark the relevant result `SIMULATED`, not `CLOUD_VERIFIED`. Define the generator, client region, payload distribution, ramp-up, warm/cold instance conditions, and service limits before benchmarking. These targets are acceptance criteria; missing them is a finding, not a reason to omit the run.

### Error budget example

A 99.95% *time-based* availability target leaves 0.05% of a 30-day window unavailable: **21.6 minutes**. This is an intuition aid, **not the same accounting model** as a request-based SLO. For request-based objectives, the budget is `0.0005 × eligible_requests` unsuccessful requests. Do not interchange time-based and request-based error budgets.

### Advanced objectives — cross-region phase

| Requirement | Challenge target | Caution |
|---|---|---|
| Regional evacuation and service restoration | **RTO <= 10 minutes** in the controlled failover exercise | Timer starts at defined fault time, ends at restored **correct user journey** |
| Recoverable data | **RPO <= 5 minutes** under declared data architecture | Measure last durable/consistent recovery point against incident time |
| Recovery correctness | **No silent loss, double effects, or cross-region conflicts** in tested scenarios | Distinguish zero-corruption from zero-data-loss; document any permitted RPO loss |
| Operability | Tested failback and rollback, with runbook and exact evidence | Health returning is not sufficient for safe write resumption |

**Critical qualification:** An RPO of 5 minutes does **not** justify silently dropping an operation after telling a client it was durably accepted if your published admission contract promises stronger durability. Pick either a truly compatible persistence/replication boundary or explicitly document a weaker admission contract and its recovery behavior. Architecture cannot promise stronger durability than its weakest critical dependency.

---

## Part 4 — Required architecture decisions

Author an ADR for each of the decisions below. Each ADR must contain: context, at least two viable options, chosen approach, consequences, failure modes, test plan, and cost impact.

- **ADR-001 — Location strategy:** regional first vs. multi-region; data residency constraints and cross-region eligibility.
- **ADR-002 — Persistence and admission:** durable-write semantics, transaction scope, eventual consistency, backups, RPO reality.
- **ADR-003 — Asynchronous dispatch:** Cloud Tasks or Pub/Sub, redelivery semantics, retries, DLQ/poison message strategy, capacity throttling.
- **ADR-004 — Idempotency and reconciliation:** stable operation key, atomicity strategy, concurrent workers, client retries, unknown outcomes.
- **ADR-005 — Traffic and failover:** initial routing, health signal, region evacuation, failback, handling global routing misconfiguration.
- **ADR-006 — Release engineering:** gradual rollout, CI quality gates, rollback, schema evolution, secrets/IAM, infrastructure drift.

**Diagram requirements**: produce a C4-style context and container diagram, a geographic failure-domain diagram, and one sequence diagram for timeout-after-write. Diagrams must clearly distinguish data plane vs. control plane and the critical vs. noncritical path.

---

## Part 5 — Practical phases

### Phase 0 — Architecture and failure budget (no cloud spend)

Deliver: `docs/reliability-contract.md`, `docs/failure-domain-map.md`, ADRs, Mermaid diagrams, SLI specification, error budget computation, assumptions, and estimated costs.

**Gate P0**: the design states exactly what is *available*, *durable*, *correct*, and *recoverable*. Definitions are executable or independently measurable. No unsupported 4-nines/5-nines claim.

### Phase 1 — Executable local resilience lab

Build a deterministic local implementation and test runner. Model the network, queue, datastore, region health, and execution state with adapters or test doubles. Simulate failure by dependency injection, process termination, retries, delayed acknowledgments, throttling, and region selection.

Deliver: application, synthetic ledger, local failure injector, tests, correlated JSON evidence, Makefile or scripts, and negative tests.

**Gate P1**: all local invariants pass from clean state with a reproducible command. If a negative test can force a second effect or lose track of an admitted job, P1 is HOLD.

### Phase 2 — Google Cloud regional proof

Create a disposable sandbox project. Use Terraform to provision the minimum **regional** architecture with explicit budgets/alerts, limits, IAM, tags/labels, logging, and teardown. Deploy and run the same checks against *actual GCP resources* where supported.

Deliver: Terraform plan/apply evidence (redacted), runtime revision/digests, CI runs, regional observed load test, rollback and teardown evidence.

**Gate P2**: cloud-based assertions are supported by cloud-derived measurements. A green Terraform plan is not proof of functional resilience.

### Phase 3 — Multi-region / disaster recovery proof (advanced, cost-gated)

Architect two regional Cloud Run deployments with a justified data topology and evaluated failover strategy. Before provisioning global load balancing, estimate expense, verify prerequisites for Cloud Run service health and whether required features are available in the selected regions. Simulate the loss of a region by **disabling/draining only the sandbox backend**, without attacking or impairing shared cloud infrastructure.

Deliver: failover and failback runbooks, measured RTO, measured recovery point/RPO, capacity impact, consistency checks, and a clear list of single points of failure.

**Gate P3**: only label **CLOUD_VERIFIED** capabilities actually exercised. Mark platform outage behavior **INFERRED** if the test only disabled a backend or simulated health loss; a sandbox evacuation is not proof of surviving every regional Google outage.

---

## Part 6 — Adversarial reliability test matrix

| ID | Injected fault | Required assertion | Evidence |
|---|---|---|---|
| R01 | Healthy baseline | Valid requests admitted durably; correct results | Request/operation trace, success counters, baseline latency |
| R02 | Kill application instance mid-request | Retry safe; no inconsistent state or duplicate effect | Before/after target, trace, retry record |
| R03 | Queue delivers same logical task twice | One business effect for one logical operation | `operation_id`, attempt count, mutation count |
| R04 | Worker commits effect, loses ACK | Reconciliation classifies true outcome, no second effect | State transitions, timeout, read-after-timeout |
| R05 | Datastore unavailable | Admission fails/defers according to durability contract; no false 202 | Error response, dependency status, persisted count |
| R06 | Poison message repeatedly fails | Bounded retry, observable terminal handling, no infinite hot loop | Attempts/backoff/terminal state; DLQ if chosen |
| R07 | Burst of 5× baseline traffic | Scaling or intentional overload handling; no hidden data corruption | p50/p95/p99, error rate, queue depth, scaling data |
| R08 | CI deploys faulty revision | Canary/rollout detection + rollback, without uncontrolled data side effects | Revision/digest, timeline, rollback evidence |
| R09 | Primary region backend unavailable | Routing follows declared behavior; recovery time measured | Region tags, synthetic probes, health, transition timestamps |
| R10 | Primary region recovers | Controlled failback, no split-brain or duplicate processing | Routing, ownership fencing, operation histories |
| R11 | Dependency in a global/shared resource is misconfigured | Risk identified and blast radius modeled; rollback path specified | ADR, plan diff, safe tabletop exercise |
| R12 | Region failure during writes / replication lag | RPO calculated from actual acknowledged/durable state; discrepancies reconciled | Snapshot/commit checkpoints, loss and conflict counts |

**Required execution:** R01–R08 in Phase 1 (locally) and the GCP-observable subset in Phase 2; R09–R12 in tabletop/simulation in the baseline. For Phase 3, R09/R10/R12 require controlled sandbox-cloud validation or must be clearly marked `NOT_TESTED`/`INFERRED`. Do **not** create actual region-wide failures or run destructive tests against shared projects.

**Reviewer-reserved mutations**: introduce unexpected duplicate message IDs, a database timeout after commit, mismatched tenant scope, stale region health, two simultaneous retries, a stuck worker, and a false-healthy dependency. The reviewer may alter fixtures without prior notice. No hidden credentials or production systems are needed.

---

## Part 7 — Evidence contract

A result only counts if it can be traced to a test run and tied to the observed state of the target. Proposed JSON structure:

```json
{
  "run_id": "lab-2026-10-11-001",
  "scenario_id": "R04",
  "environment": "LOCAL_SIMULATION",
  "claim": "worker retry does not duplicate business effect",
  "image_digest": "PLACEHOLDER_TO_FILL_FROM_REAL_BUILD",
  "started_at": "YYYY-MM-DDTHH:MM:SSZ",
  "finished_at": "YYYY-MM-DDTHH:MM:SSZ",
  "injected_fault": "ack_timeout_after_commit",
  "operation_id": "synthetic-job-001",
  "attempts": 2,
  "business_mutations": 1,
  "before": { "applied_jobs": 0 },
  "after": { "applied_jobs": 1 },
  "outcome": "PASS",
  "evidence_level": "SIMULATED",
  "artifacts": ["tests/results/R04.json", "tests/results/R04.log"],
  "limitations": ["Synthetic target; no cloud region failure exercised"]
}
```

**Evidence taxonomy**

- `DESIGN_ONLY` — reasoned architectural claim, not executed.
- `SIMULATED` — deterministic local or tabletop evidence.
- `CLOUD_VERIFIED` — observed in specified disposable GCP resources, with timestamps/artifact references.
- `INFERRED` — extrapolation from a narrower test; must state its limits.
- `NOT_TESTED` — no supported evidence yet.

**Mandatory evidence fields:** test ID, source code commit SHA, build image digest if used, UTC timestamps, environment, input/fixture, injected fault, pre-state, post-state, execution or mutation count, SLI observation (when applicable), result, limitations, and artifact path. Redact secrets, project identifiers where necessary, access tokens, and real user data before public sharing.

### Reliability dossier

Create `evidence/RELIABILITY_DOSSIER.md` including:

1. Declared requirements and architecture version.
2. Scope/location table and dependencies.
3. SLI definitions and a raw metric-to-SLO derivation with numerator, denominator, window, and excluded traffic.
4. Per-test outcomes and links to machine-readable evidence.
5. Fault-recovery timelines for R09/R10, including RTO measurement definition and observed result.
6. Data recovery analysis: actual recovery checkpoint, measured RPO, missing/conflicted accepted jobs.
7. Risk register: known limits, unknowns, cloud-vs-local evidence, error-budget and cost trade-offs.
8. Formal verdict: GO / CONDITIONAL GO / HOLD for **this synthetic lab only**.

---

## Part 8 — Repository structure (suggested)

```text
cloud-reliability-engineering-challenge/
├── README.md
├── architecture/
│   ├── context.mmd
│   ├── deployment.mmd
│   └── failure-domains.mmd
├── docs/
│   ├── reliability-contract.md
│   ├── failure-domain-map.md
│   ├── threat-and-fault-model.md
│   ├── cost-and-capacity.md
│   ├── runbook-failover.md
│   └── runbook-rollback.md
├── adr/
│   ├── ADR-001-location-strategy.md
│   ├── ADR-002-persistence.md
│   ├── ADR-003-messaging.md
│   ├── ADR-004-idempotency.md
│   ├── ADR-005-failover.md
│   └── ADR-006-releases.md
├── app/
│   ├── api/
│   ├── worker/
│   └── common/
├── infra/
│   ├── regional/
│   └── multi-region/          # advanced optional
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── reliability/
│   ├── load/
│   └── fixtures/
├── evidence/
│   ├── RELIABILITY_DOSSIER.md
│   ├── manifests/
│   └── runs/
├── .github/workflows/
│   └── validate.yml
├── Makefile
└── .gitignore
```

**Do not fabricate runnable commands or green tests.** Implement real repository commands such as `make test`, `make faults`, `make evidence`, `make tf-plan`, and `make destroy`, and document their prerequisites. `make destroy` must target only the sandbox and be protected against wrong project selection.

---

## Part 9 — Secure execution and cost controls

1. Use a **separate GCP sandbox project** with no FoundLab production access. No real customer identifiers, datasets, traffic, secrets, or keys.
2. Establish cost estimates *before* deployment. Google Cloud budget alerts are **not hard spending caps**; use small quotas/limits, resource labels, bounded test windows, and teardown automation.
3. Prefer short-lived workload identity federation for GitHub Actions; do not commit long-lived service-account keys. Pin permissions to the minimum needed.
4. Use Cloud Run min instances only when justified and quantify recurring idle cost. Document service-health prerequisites and any features/regions/quotas that affect the test.
5. Run load tests only against owned sandbox endpoints with safe throughput/time limits. No region-wide chaos injection or third-party targets.
6. Avoid production-like persistent databases when a simpler bounded test proves the same claim. Advanced services are optional until the ADR justifies their cost.
7. Require reviewed Terraform plans for regional/global IAM and load balancer changes; ensure a rollback strategy and clear teardown order.
8. Public proof may include sanitized metrics and manifests, but must not reveal access tokens, project IDs if sensitive, internal network details, or business/customer data.
9. **Do not** present this public exercise as a REX Guard implementation, an institutional certification, a Google Cloud validation, or an SLO already achieved.

---

## Part 10 — Review rubric (100 points)

| Dimension | Weight | What the reviewer must inspect |
|---|---:|---|
| Failure domains and architecture trade-offs | **20** | Proper location scopes, shared dependencies, viable ADRs, realistic blast radius |
| SLI/SLO, recovery objectives, and measurement | **20** | Correct definitions, math, windowing, measurable RTO/RPO, honest claims |
| Data correctness, retries, idempotency, reconciliation | **20** | R03/R04/R05/R12 adversarial evidence, no hidden or duplicate effects |
| Failure injection and recovery | **15** | Deterministic tests, fault timeline, safe failover/failback, rollback |
| Reproducibility, Terraform, CI, least privilege | **10** | Clean checkout, gates that actually execute, safe sandbox provisioning/teardown |
| Observability and evidence quality | **10** | Correlated traces/logs/metrics and machine-verifiable dossiers |
| Technical defense, limitations, costs | **5** | Clear answers to reviewer surprises; no exaggerated availability claims |
| **Total** | **100** | |

### Formal verdict

- **GO**: at least **85/100**, all applicable mandatory tests pass, and no critical violation of correctness/admission guarantees. The scope of GO is explicitly named: `LOCAL_GO`, `REGIONAL_SANDBOX_GO`, or `MULTI_REGION_SANDBOX_GO`.
- **CONDITIONAL GO**: **70–84/100**, all safety-critical invariants hold, and bounded, retestable gaps remain.
- **HOLD**: below **70/100** or *any* blocker below, irrespective of score.

### Absolute blockers (NO-GO for affected phase)

- Duplicate irreversible business effect for a single logical operation during supported retries.
- Silent loss of operations contrary to the declared durable-admission contract.
- Fail-open write path following critical dependency failure.
- Claim of verified failover, RTO, RPO, or regional outage survival without matching evidence.
- Unsafe or destructive tests outside the sandbox scope.
- Exposure of secret material or internal/customer data in the public repository.

A passing synthetic exercise is **not** approval for deployment in a regulated institution. It is evidence of engineering competence for the specific controls tested.

---

## Part 11 — Suggested execution sequence

**Days 1–3 — Design:** business impact, failure-domain map, requirements and six ADRs. No infrastructure provisioned until SLO and cost constraints are explicit.  
**Days 4–8 — Local core:** API, worker, data model, idempotency, retry/reconciliation and negative tests.  
**Days 9–12 — Regional cloud proof:** scoped Terraform, CI, telemetry and safe load/fault exercises.  
**Days 13–15 — Dossier + review:** independent reproduction and defense; remediate material findings.

**Advanced continuation (after cost/feasibility gate):** multi-region implementation, controlled region-backend evacuation, recovery and failback evidence, measured RTO/RPO, and comparative total cost.

### Review meeting: questions the architect must answer

- How can your API return 202 and still lose an admitted job? What precise persistence step makes admission durable?
- Which failures are **zonal**, **regional**, or **global**, and which are common-mode configuration failures?
- Does failover preserve not only HTTP reachability but also correct and consistent writes?
- What happens if the primary database committed but the worker timed out and retries in another region?
- What exact health signal moves traffic away from an unhealthy Cloud Run region? Does your deployed configuration have that capability **enabled and tested**?
- How does RTO start/stop? How is actual RPO computed from checkpoints rather than asserted from replication settings?
- If the primary region has been degraded, can the secondary region absorb the full expected load? What is the cost of maintaining that capacity?
- Can you prove that failback does not create split brain or duplicate side effects?
- What happens when the *global load balancer configuration itself* is wrong?
- What does your evidence **not** justify claiming?

---

## Part 12 — Official source of truth (checked 2026-10-11)

The following original Google Cloud documents are the reference materials. Do not mistake their illustrative availability numbers for unconditional guarantees; verify chosen product/region/SLA/features again during implementation.

1. [Google Cloud Infrastructure Reliability — Building blocks](https://docs.cloud.google.com/architecture/infra-reliability-guide/building-blocks) — region/zone resource scope, common-mode failures, stack reliability, service SLAs.
2. [Assess workload reliability requirements](https://docs.cloud.google.com/architecture/infra-reliability-guide/requirements) — journey-specific objectives and critical periods.
3. [Design reliable cloud infrastructure](https://docs.cloud.google.com/architecture/infra-reliability-guide/design) — redundancy patterns, stack dependencies, regional/multi-regional designs.
4. [Manage traffic and load](https://docs.cloud.google.com/architecture/infra-reliability-guide/traffic-load) — capacity planning, scaling, stress and routing.
5. [Manage and monitor infrastructure](https://docs.cloud.google.com/architecture/infra-reliability-guide/manage-and-monitor) — gradual releases, change controls and observability.
6. [Disaster recovery planning](https://docs.cloud.google.com/architecture/dr-scenarios-planning-guide) — business impact, RTO/RPO, DR trade-offs.
7. [Cloud Run multi-region deployments](https://docs.cloud.google.com/run/docs/multiple-regions) — regional backends, global routing, health/failover limitations.
8. [Cloud Run service health — cross-region failover](https://docs.cloud.google.com/run/docs/configuring/configure-service-health) — readiness and supported automatic failover mechanisms.
9. [Cloud Tasks delivery semantics](https://docs.cloud.google.com/tasks/docs/dual-overview) — at-least-once task dispatch and idempotent handlers.
10. [Pub/Sub exactly-once delivery](https://docs.cloud.google.com/pubsub/docs/exactly-once-delivery) — applicable to *pull subscriptions* under regional conditions; not a substitute for business-level idempotency.
11. [Google Cloud SLO concepts](https://docs.cloud.google.com/stackdriver/docs/solutions/slo-monitoring) — SLIs, SLOs, request-based vs window-based measurements and error budgets.

**License / authorship note:** This challenge is an original derived exercise inspired by public Google Cloud documentation, not a reproduction of or an endorsement by Google. Any future public artifact should credit documentation used and preserve third-party notices for any reused code.

---

## Final acceptance statement

> **Reliable infrastructure is not architecture that has never failed. It is infrastructure whose failure boundaries, recovery behavior, data correctness, and operational limits have been tested and can be explained with evidence.**

A reviewer must be able to clone the repository, reproduce at least the mandatory local test cases, inspect the metric calculations and failure-domain decisions, and determine **which reliability claims are observed, simulated, inferred, or unknown** without needing access to internal FoundLab systems.