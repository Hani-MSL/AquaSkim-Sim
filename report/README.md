# Final Report Generator

## Main output

The final report is generated from validated Phase 02--09 outputs:

```text
outputs/reports/AquaSkim-Sim_Final_Report.docx
```

## One-command build

```bat
scripts\run_patch_10.bat
```

## Full project rebuild from a clean machine

```bat
scripts\bootstrap_and_build.bat
```

## Cover-page fields

Before final submission, edit `config/report_metadata.json` with the student's name, student ID, course, instructor, institution and semester. Then run the report build again.

## Evidence

The final report build stores a report manifest, final submission manifest, SHA-256 checksums, execution transcript, environment snapshot, artifact snapshot and Phase 10 handoff.
