# GitHub branch ruleset — main

**Status: ACTIVE, verified on 2026-10-12.**

The repository administrator imported the ruleset `foundation-protect-main` (GitHub ruleset ID `24908159`). A GitHub API read verified:

- `GET /repos/irelia0nerf/gcp-reliability-engineering/branches/main`: `protected: true`.
- `GET /repos/irelia0nerf/gcp-reliability-engineering/rulesets/24908159`: `enforcement: active`, target `refs/heads/main`.
- Force-push and deletion disallowed; pull requests and resolution of review threads required.
- Up-to-date required status checks: `tests`, `lint`, `security`, `terraform`.
- No bypass actors and **zero required approving reviews** (solo-maintainer policy).

[Inspect repository rules](https://github.com/irelia0nerf/gcp-reliability-engineering/settings/rules). The versioned [main.json](./main.json) is a configuration template, not a live binding; the live GitHub ruleset is the enforcement source of truth.

**Verification commands (read-only):**

```bash
gh api repos/irelia0nerf/gcp-reliability-engineering/branches/main --jq '.protected'
gh api repos/irelia0nerf/gcp-reliability-engineering/rulesets/24908159 --jq '{name, enforcement, conditions, rules}'
```

**Governance limitation:** GitHub does not require an independent approval under the current 0-review ruleset. The responsible maintainer should still review diffs and logs before merging. Raise the review count to 1 when an independent reviewer is available.

**Evidence is point-in-time.** Recheck protection and check names before every significant integration; a JSON file or a prior screenshot is not ongoing proof of enforcement.
