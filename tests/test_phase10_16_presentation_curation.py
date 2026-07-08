from __future__ import annotations

from aquaskim.presentation_curation import load_presentation_curation, validate_curation_spec


def test_presentation_curation_is_reference_only_and_contains_explicit_limits() -> None:
    spec = load_presentation_curation()
    assert len(spec["figures"]) >= 12
    assert len(spec["media"]) >= 10
    assert all(str(entry["source"]).startswith("outputs/figures/reference_") for entry in spec["figures"])
    assert all(str(entry["gif"]).startswith("outputs/animations/reference_") for entry in spec["media"])
    assert all(str(entry["mp4"]).startswith("outputs/videos/reference_") for entry in spec["media"])
    claims = {str(entry["claim_class"]) for entry in spec["media"]}
    assert {"boundary", "controlled_failure"}.issubset(claims)


def test_presentation_curation_rejects_legacy_or_hidden_limit_selection() -> None:
    spec = load_presentation_curation()
    invalid = {key: value for key, value in spec.items()}
    invalid["media"] = [dict(entry) for entry in spec["media"]]
    invalid["media"][0]["gif"] = "outputs/animations/phase09_2_energy_return.gif"
    try:
        validate_curation_spec(invalid)
    except ValueError as exc:
        assert "reference evidence" in str(exc) or "legacy" in str(exc)
    else:
        raise AssertionError("Legacy media must be rejected from the curated set.")
