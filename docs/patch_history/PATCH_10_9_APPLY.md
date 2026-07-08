# Apply Patch 10.9

```bat
cd /d C:\Projects
tar -xf "%USERPROFILE%\Downloads\AquaSkim-Sim_Patch_10_9_MissionFidelity_and_VisualAudit.zip" -C C:\Projects
cd /d C:\Projects\AquaSkim-Sim
scripts\run_patch_10_9.bat
```

The run is non-interactive. It regenerates the fixed reference mission and
manoeuvre outputs. It can take several minutes because GIF and MP4 evidence is
rendered in addition to the numerical cases.
