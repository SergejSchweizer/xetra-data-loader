# Repository governance

This repository uses pull-request-only delivery to `main` after XDL-PR006.

## XDL-PR035 repair evidence

Observed before the XDL-PR035 repair (2026-08-24): GitHub returned `404 Branch not
protected` for `main`, and the repository reported `allow_auto_merge=false`.

Verified after the repair: GitHub reports `main.protected=true`, requires the exact
`merge-gate` check with strict current-head enforcement, requires pull requests,
enforces protections for administrators, blocks force pushes and branch deletion,
requires conversation resolution, and reports `allow_auto_merge=true`.

GitHub enforces direct-push rejection through this protection. The enforcement
configuration above is the safe verification evidence; attempting a known-invalid
push solely to prove rejection is not part of normal repository operation.

## Required `main` protections

The GitHub repository configuration is part of the XDL-PR006 acceptance contract and must enforce all of the following:

- pull requests are required before changes can reach `main`;
- the required status check is exactly `merge-gate` from `.github/workflows/merge-quality.yml`;
- required checks must pass on the current PR head before merge;
- direct feature pushes to `main` are blocked;
- force pushes are blocked;
- branch deletion is blocked;
- repository auto-merge is enabled.

The workflows intentionally keep `lint`, `type`, `unit`, `integration`, and `policy` independent. The final `merge-gate` succeeds only if every required job reports `success`.

## Auto-merge procedure

1. Create a work-order branch from its exact merged dependency SHA.
2. Push only commits whose Conventional Commit scope is the exact `xdl-prNNN-*` work-order.
3. Open a PR whose title uses the same exact work-order scope.
4. Wait for the push and merge quality workflows to complete on the current head SHA.
5. Once the PR is review-ready, enable GitHub auto-merge.
6. Do not manually merge around a failing, cancelled, skipped, or pending `merge-gate`.

## Verification checklist

XDL-PR006 is complete only after GitHub reports the repository settings above as active and a representative PR demonstrates both states:

- merge is blocked while `merge-gate` is pending or failing;
- auto-merge completes only after all required checks, including `merge-gate`, pass.

Repository settings are operational state, not secrets. Provider tokens, database passwords, and full DSNs must never be committed while exercising this procedure.
