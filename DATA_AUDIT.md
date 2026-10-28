# TAI data audit

The organiser's freshly downloaded archive matches the earlier local archive by SHA-256. All 1,082 extracted files matched the earlier extracted copies, and their gzip streams passed verification. The organiser listing supplied sizes but no official SHA-256. The private manifest records individual hashes.

An earlier read-only audit of those same extracted bytes reported 412 installation files with 412 rows, 335 measurement-point files with 32,418 rows and 335 measurement-value files with 28,705,102 rows. It reported 30,988 blank values, 104,687 negative values and 3,425,231 zeros, with no nonblank date or numeric parse failures. These counts are not evidence that zero or negative values are invalid. Decoding replacement characters occurred in 46 files. The timezone, data availability, reporting period, input types, semantics and unit definitions remain unconfirmed.

The script-generated detailed reports, including point IDs and records, stay in a private local output directory. Until a complete run and the remaining checks finish, the outputs are preliminary. Ask TAI the questions in `TAI_QUESTIONS.md`; do not infer physical causes, operating limits or labels.

An exploratory metadata filter for `Influent` and `Volume` in the earlier audit included 682 points across several unit strings. It is not an approved incoming-flow slice or peer set. Selection requires confirmation of meaning, unit expression, measurement method and time availability.
