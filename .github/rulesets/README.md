# Administrative gate: main is not protected yet

This file is a proposed branch ruleset, **not evidence that protection is active**. GitHub connector access here supports code writes, but not administrative ruleset changes.

Open [repository rules settings](https://github.com/irelia0nerf/gcp-reliability-engineering/settings/rules), choose **New branch ruleset**, target `main`, enforcement **Active**. Disable force pushes and deletions; require pull requests; require strict up-to-date status checks **tests**, **lint**, **security**, **terraform**. For independent reviewer availability, increase approvals to one.

Do not enforce until each status check actually appears after GitHub Actions run. Verify subsequently that `GET /branches/main` reports protected and active rulesets appear at `GET /rulesets`. GitHub supports [importing a prebuilt ruleset](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/creating-rulesets-for-a-repository).

Until verified: `MAIN_PROTECTION=NOT_CONFIGURED`.
