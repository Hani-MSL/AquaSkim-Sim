# Report workflow

The final Word report is generated automatically by the public rebuild workflow:

```bat
scripts\run_from_zero_to_delivery.bat
```

The generated DOCX is written to:

```text
outputs\reports\AquaSkim-Sim_Final_Report.docx
```

The report is intentionally generated in English. Optional personal/course metadata can be supplied locally through `config/report_metadata.json`, which is ignored by Git.
