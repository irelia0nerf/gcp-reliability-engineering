# Local fault runbook

Run from repository root with Python 3.12+.

```bash
python -m unittest discover -s tests -v
python -m src.scenarios --scenario all
```

Inspect JSON `before`, `after`, `business_mutations`, `events`, `passed` and evidence level.

R02: fail pre-commit then retry; R03: duplicate delivery; R04: lose ACK after commit and retry; R05: refuse admission without persistence; R06: poison message after 3 attempts becomes FAILED; R07: 50 operations executed sequentially locally; R08: simulate failed revision by rolling back uncommitted mutation. **R07 is not a scaled load benchmark and R08 is not CI/deployment rollback.**

Any missing effect, duplicate or unauthorized write sets CLOUD GO=HOLD until fixed and independently reverified. Do not induce region outages in shared projects.
