# Incident: Phase 10 batch title parsing and report metadata

## Observed symptom

The Phase 10 launcher stopped immediately with:

```text
'Patch' is not recognized as an internal or external command,
operable program or batch file.
```

## Root cause

The batch file printed its title using an unescaped vertical bar (`|`):

```bat
echo AquaSkim-Sim | Patch 10 - Final Report and Delivery Package
```

In Windows CMD, `|` is a pipeline operator. CMD therefore interpreted `Patch` as the name of a command instead of literal text.

## Corrective actions

1. The literal `|` was removed from the banner line.
2. Report-cover metadata now treats `semester` as optional.
3. The metadata file was rewritten as valid JSON without a trailing comma.
4. A regression test checks that an absent semester remains valid and is represented as an empty optional field.

## Preventive rule

All future Windows `.bat` banners must avoid unescaped CMD metacharacters such as `|`, `&`, `<`, `>` and parentheses in literal output. If needed, they must be escaped explicitly.
