# Reliability contract (challenge targets, NOT measured)

- API admission target: 99.95% successful eligible attempts over rolling 30 days.
- Read availability target: 99.95% over rolling 30 days.
- Completion latency p95 target: 60 seconds under declared load.
- Duplicate business effects: zero within the stated exercise fault envelope.
- Request-based error budget: 0.0005 × eligible requests.
- 30-day time-based illustration: 21.6 minutes; not equivalent to request-based accounting.

## Known limitations

SQLite is a single-host local file. No managed storage, durable queue, cross-host transaction, Cloud Run service or multi-region data replication exists in this implementation. A region failure, load test, failback and real disaster-recovery RTO/RPO remain **NOT_TESTED**.

The sample tenant string is untrusted; production use requires authentication and trustworthy binding of principal-to-tenant. Lab 202 admission is committed only to local SQLite and must not be described as GCP-durable.
