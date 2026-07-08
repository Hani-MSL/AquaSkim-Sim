# Incident: Patch 10.19.1 batch preflight syntax

Patch 10.19.1 restored the missing reproduction script but used a multi-line CMD `for` list with a trailing continuation marker before the closing parenthesis. On Windows CMD this stopped with `The syntax of the command is incorrect` before full pytest and before delivery packaging.

Patch 10.19.2 replaces the fragile batch-loop preflight with a Python module preflight: `python -m aquaskim.delivery_package --preflight-scripts`. The Python preflight uses the same required script list as the package builder, so the batch script no longer duplicates complex CMD syntax.

No model, Word report, evidence, curated media, or certification claim is changed.
