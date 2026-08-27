# Controlled PostgreSQL rewrite

`xdl-verify-production-sync --execute-full-sync --confirm-destructive-reset`
is the one-off final cutover command. It refuses to run unless the recurring
`xdl-weekly` cron entry has first been disabled, the configured administrative
connection resolves exactly to `10.10.1.3:54321`, a lock is acquired, and a
backup root outside this repository is supplied.

The command backs up only `xetra_loader` and `xetra_loader_sync` plus the Gold
manifests, performs the confirmed loader-owned reset, and fetches the complete
active and delisted universe. Administrative credentials are used only for the
backup and reset; all serving publication is performed through the configured
non-superuser writer. It then runs the guarded weekly path once against the
unchanged source and writes the sanitized V2 acceptance report.

Keep the cron entry disabled until that report is `PASS`. Restore exactly the
Sunday `08:00 Europe/Vienna` `xdl-weekly` entry only after a successful run.
