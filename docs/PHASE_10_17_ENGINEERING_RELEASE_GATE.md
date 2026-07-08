# Engineering Release Gate

Patch 10.17 is an audit-only gate between presentation-evidence curation and
Word-report construction. It does not run a new mission, render media, create a
Word document, build a delivery ZIP or enable final release scripts.

A passing result is named `ENGINEERING_RELEASE_CANDIDATE`. This means that the
reference source, evidence manifests, curated assets, policy isolation and
release safeguards are internally consistent enough to begin controlled report
construction. It is not a distribution approval and does not claim external
certification or sea-trial validation.

The gate checks canonical version agreement, YAML and import integrity,
reference/Legacy isolation, release-script disablement, evidence presence,
curated source-to-copy SHA-256 equality, visual-QA status, explicit inclusion
of boundary/controlled-failure material, and absence of premature Word/ZIP
artifacts.
