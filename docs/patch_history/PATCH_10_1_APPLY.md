# Patch 10.1 Apply Instructions

This patch fixes the Windows CMD banner parsing error in `run_patch_10.bat` and makes `semester` optional in the report cover metadata.

## Apply

Extract this ZIP into `C:\Projects`, allowing replacement of existing files.

## Run

```bat
cd /d C:\Projects\AquaSkim-Sim
scripts\run_patch_10.bat
```

## Metadata

`config\report_metadata.json` is valid JSON and already contains the supplied cover information. The optional `semester` key is intentionally absent, so no semester row will appear on the Word cover.
