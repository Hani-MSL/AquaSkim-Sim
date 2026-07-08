# Patch 10.11 — Apply Instructions

## Scope

This patch upgrades only the fixed, non-interactive reference-mission fidelity
and visual evidence pipeline. It adds a behaviour audit, a versioned visual
protocol, six long-form GIF/MP4 replays, a multi-animation contact sheet and
visual QA checks. It does **not** generate a Word report, delivery ZIP or a
release build.

## Required base

Apply after Patch 10.10, which restored `phase02.py`, `cli.py`, the source
integrity audit and the Reference/Legacy separation.

## Windows CMD steps

```bat
cd /d C:\Projects
powershell -NoProfile -Command "Compress-Archive -Path 'C:\Projects\AquaSkim-Sim\*' -DestinationPath 'C:\Projects\AquaSkim-Sim_backup_before_patch_10_11.zip' -Force"
tar -xf "%USERPROFILE%\Downloads\AquaSkim-Sim_Patch_10_11_Reference_Mission_Fidelity_and_Visual_Evidence.zip" -C C:\Projects
cd /d C:\Projects\AquaSkim-Sim
scripts\run_patch_10_11_reference_fidelity.bat
```

## Gate order

The batch script must execute the following order:

1. YAML parse audit
2. Import audit
3. `compileall`
4. Full `pytest`
5. Fixed reference mission and media generation
6. Visual-quality manifest and evidence snapshot

No GIF/MP4 is rendered if an earlier gate fails.

## Expected result

- Full test suite: at least `110 passed, 2 skipped`.
- Six GIFs and six MP4s, each GIF at least 96 frames and 9 seconds.
- `outputs\animations\reference_fidelity_visual_contact_sheet.png`
- `outputs\logs\reference_visual_evidence_quality_manifest.json`
- `outputs\reports\reference_mission_fidelity_and_visual_evidence.md`
- `records\phases\phase_10_11\runs\...`

## Explicitly still disabled

- Word report generation
- Submission ZIP generation
- Release build
- Historical quota-based mission pipeline
