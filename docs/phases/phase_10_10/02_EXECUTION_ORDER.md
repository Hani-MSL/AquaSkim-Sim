# Execution Order

The official Patch 10.10 script uses this exact order:

1. install the editable local package;
2. parse all YAML files;
3. import every package module;
4. compile all source files;
5. execute the full pytest suite;
6. write a source-integrity JSON and Markdown report.

No reference simulation, media renderer, Word builder, delivery archiver or
release command is called in this patch.
