# Installation troubleshooting

Use `reason doctor --json` for stable DR diagnostic identifiers. Install failures use IF diagnostics and structured JSON with `--json`. An interrupted staged install is isolated under `versions/<version>.tmp-*`; the active `current` version is switched only after staging validation.
