# Patch 10.18.1 — Final Word Table-count QA Hotfix

## Purpose
Fix the Patch 10.18 QA stop where the DOCX was generated but had only seven Word tables while the release-report contract required at least eight.

## Changes
- Adds a real model-boundary / non-claim table to the final Word report.
- Preserves the `table_count_ge_8` QA threshold.
- Writes `final_word_report_qa.json` and `final_word_report_qa.md` even when QA fails, before raising the blocking error.
- Extends the Word regression test to assert the minimum table count.
- Keeps delivery ZIP and final release scripts disabled.

## Expected result
Re-running `scripts\run_patch_10_18_final_word_report.bat` should rebuild the DOCX and continue to manifest, QA markdown and handoff generation.
