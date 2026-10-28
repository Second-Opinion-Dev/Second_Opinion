# TAI work log

## 28 October 2026

- Local branch `oindrilla-tai-data-cleaning` was fast-forwarded to fetched `origin/main` commit `b9151e8`, containing the updated Second Opinion idea merged from `smriti-update-project-idea`. The idea has no team-division section; scope follows the user's assignment. The updated idea asks whether historical validation limits and outcomes are available, and prohibits claiming existing checks missed readings without that evidence.
- Earlier private audit recorded 412 installation files (412 rows), 335 point files (32,418 rows) and 335 value files (28,705,102 rows). These are prior observations, not a fresh download verification. The audit is at `../tai-analysis/DATA_AUDIT.md` where available.
- Added a separate verified re-download script, streaming preliminary preparation and sequence-report scripts, handoff instructions and questions for TAI. After the user provided the organiser key, the fresh TAI archive was downloaded and extracted privately. Its SHA-256 matched the earlier archive, all 1,082 gzip files passed extraction checks, and all 1,082 extracted files matched the earlier copies by SHA-256. The fresh manifest is private at `../tai-redownload/manifest.json`; no official SHA-256 was supplied in the listing unless the manifest records one.
- A partial five-file-per-table smoke run processed 260,277 value rows. Partial metadata and installation samples must not be used to infer full-data join completeness. The complete run and remaining checks are described in the handoff.
