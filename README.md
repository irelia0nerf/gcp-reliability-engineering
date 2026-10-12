# GCP Reliability Engineering — FAILURE IS A CONTRACT

**Status: Executable local simulation. No Google Cloud deployment, measured production SLO, or regional-failover claim.**

This public Atlas Operations lab demonstrates tenant-scoped local durable admission, SQLite transactional effect idempotency, safe retries after a lost ACK, concurrent duplicate-worker delivery, and synthetic fault injection.

## Reproduce

```bash
python -m unittest discover -s tests -v
python -m src.demo --scenario R04
```

Local simulation is not cloud availability evidence. SQLite is single-host storage and must **never** be used as an authoritative durable Cloud Run database. Tenant identifiers in this exercise are untrusted inputs, not proof of authentication. Do not expose the lab as a production service.

| Capability | Evidence |
|---|---|
| Atomic local synthetic effect | LOCAL_SIMULATION |
| Lost-ACK retry and replay | LOCAL_SIMULATION |
| Admission refusal during store failure | LOCAL_SIMULATION |
| Google Cloud regional resilience | NOT_DEPLOYED |
| SLO / RTO / RPO | NOT_MEASURED |
| Cross-region failover | NOT_TESTED |

Read the [reliability contract](docs/reliability-contract.md), [ADR-001](docs/adr/001-regional-first.md), and [evidence dossier](evidence/RELIABILITY_DOSSIER.md).

**Next steps:** authenticated tenancy, durable managed storage and async transport, cloud deployment under separate approval, monitored SLIs, and multi-region failure drills only after the persistence contract is specified.

**Source:** Google Cloud [Infrastructure Reliability Guide](https://docs.cloud.google.com/architecture/infra-reliability-guide/building-blocks).
