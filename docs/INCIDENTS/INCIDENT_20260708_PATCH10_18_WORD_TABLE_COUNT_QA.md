# Incident — Patch 10.18 Word table-count QA stop

## Symptom
Patch 10.18 generated `outputs/reports/AquaSkim-Sim_Final_Report.docx`, but QA stopped before writing the final manifest and handoff because `table_count_ge_8` was false.

## Root cause
The Word report contained seven real Word tables while the structural QA contract required at least eight tables. The QA gate behaved correctly and blocked finalization.

## Corrective action
Patch 10.18.1 adds a genuine model-boundary / non-claim table to the limitations section and keeps the minimum-table QA threshold unchanged. It also writes diagnostic QA JSON/Markdown before raising a failure, so any future QA stop is inspectable.

## Scope
No simulation, media rendering, delivery ZIP or release build is enabled by this hotfix.
