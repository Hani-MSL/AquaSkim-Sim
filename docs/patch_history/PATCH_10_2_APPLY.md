# Patch 10.2 — Apply and Run

## Apply

```bat
cd /d C:\Projects
tar -xf "%USERPROFILE%\Downloads\AquaSkim-Sim_Patch_10_2_Parametric_Design_Synthesis.zip" -C C:\Projects
```

## Official phase run

```bat
cd /d C:\Projects\AquaSkim-Sim
scripts\run_patch_10_2.bat
```

## One-command interactive build

```bat
scripts\bootstrap_and_build.bat
```

The interactive build asks for local metadata and mission/design inputs. It does not generate the final Word report yet. Phase 10.2 adds mechanical synthesis, conceptual mesh exports, design traceability and the release-candidate visual quality gate.
