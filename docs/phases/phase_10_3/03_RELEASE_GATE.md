# Release-quality gate before Word generation

The final Word report is not a source of truth. It is a presentation layer created only after generated engineering artifacts, tests and evidence are available.

## Gate requirements

- engineering phases 02, 03, 04, 05, 06, 07, 08.2, 09.2, 10.2 and 10.3 have PASS evidence;
- source code passes the syntax gate;
- numerical CSV tables, JSON summaries and Markdown phase reports exist;
- report-quality PNG and SVG figures exist;
- required GIF and MP4 mission evidence exists;
- all source artifacts are hashed and snapshot in the official phase run;
- retained limitations are included in the final report.

The Phase 10.3 inventory reports any missing portfolio category as `WARNING`; missing evidence is never silently treated as success.
