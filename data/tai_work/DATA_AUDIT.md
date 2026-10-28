# TAI data audit

The organiser's freshly downloaded archive matches the earlier local archive by SHA-256. All 1,082 extracted files matched the earlier extracted copies, and their gzip streams passed verification. The organiser listing supplied sizes but no official SHA-256. The private manifest records individual hashes.

An earlier read-only audit of those same extracted bytes reported 412 installation files with 412 rows, 335 measurement-point files with 32,418 rows and 335 measurement-value files with 28,705,102 rows. It reported 30,988 blank values, 104,687 negative values and 3,425,231 zeros, with no nonblank date or numeric parse failures. These counts are not evidence that zero or negative values are invalid. Decoding replacement characters occurred in 46 files. The timezone, data availability, reporting period, input types, semantics and unit definitions remain unconfirmed.

The full scripted pass of the hash-matched files confirmed the row counts and parsing counts above. It found zero value rows with an unmatched literal point ID or origin installation code, and each value's point ID matched one metadata row. Literal-key meaning still needs confirmation with TAI. It identified 6,883 same-point, same-date groups with more than one distinct record hash and no exact-duplicate candidates under the 64-bit hash check; review the records and confirm semantics before treating them as conflicts or deduplicating. Counts are based on literal dates and all recorded fields.

Under a literal destination-to-installation join, 22,378,980 measurement rows have a blank destination, 5,661,266 match one installation, and 664,856 do not match. Whether destination is optional and whether this is the correct join remain questions for TAI. All 28,705,102 origin codes matched one installation under the analogous literal check.

The sequence report covers 22,946 point IDs with observations. It found calendar gaps between observations for 13,193 points, adjacent repeated nonblank value strings for 20,336 points, and no adjacent unit-string changes. A calendar gap is not proof of a missing expected reading, repeated values may be valid, and literal date ordering and same-date ties limit this summary.

The script-generated detailed reports, including point IDs and records, stay in a private local output directory. The outputs remain preliminary while expert questions and further checks are unresolved. Ask TAI the questions in `data/tai_work/QUESTIONS.md`; do not infer physical causes, operating limits or labels.

An exploratory metadata filter for `Influent` and `Volume` included 682 point metadata rows across several unit strings and copied 871,475 measurements. It is not an approved incoming-flow slice or peer set. Selection requires confirmation of meaning, unit expression, measurement method and time availability. The review-candidate export copied 30,988 blank-value records for inspection; all remain in the retained dataset.
