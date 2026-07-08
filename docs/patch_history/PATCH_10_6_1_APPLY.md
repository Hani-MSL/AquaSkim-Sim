# Apply Patch 10.6.1

This patch repairs the source-level path contract that caused the immediate
`ModuleNotFoundError`.

```bat
cd /d C:\Projects
tar -xf "%USERPROFILE%\Downloads\AquaSkim-Sim_Patch_10_6_1_PathCompatibilityHotfix.zip" -C C:\Projects
cd /d C:\Projects\AquaSkim-Sim
scripts\run_patch_10_6_hotfix.bat
```
