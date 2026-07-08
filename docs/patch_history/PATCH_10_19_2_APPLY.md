# Patch 10.19.2 — Delivery Batch Preflight Syntax Hotfix

This hotfix fixes the Windows CMD syntax error introduced in the reproduction-script preflight.

## Apply

```bat
cd /d C:\Projects
tar -xf "%USERPROFILE%\Downloads\AquaSkim-Sim_Patch_10_19_2_Delivery_Batch_Preload_Syntax_Hotfix.zip" -C C:\Projects
```

## Run

```bat
cd /d C:\Projects\AquaSkim-Sim
scripts\run_patch_10_19_independent_rebuild_and_delivery.bat
```

The final delivery package version is `1.6.19`.
