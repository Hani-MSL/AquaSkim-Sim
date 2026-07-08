from aquaskim.config import load_base_configuration
from aquaskim.design_synthesis import build_concept_assembly


def test_parametric_assembly_has_expected_subsystems_and_nonempty_meshes() -> None:
    parts = build_concept_assembly(load_base_configuration())
    identifiers = {part.identifier for part in parts}
    subsystems = {part.subsystem for part in parts}
    assert {"hull_port", "hull_starboard", "battery", "collector", "thruster_port", "thruster_starboard"} <= identifiers
    assert {"Flotation", "Energy", "Control", "Collection", "Propulsion"} <= subsystems
    assert len(parts) >= 10
    assert all(len(part.vertices) >= 8 and len(part.faces) >= 8 for part in parts)


def test_concept_mesh_extents_match_shared_geometry() -> None:
    config = load_base_configuration()
    geometry = config.data["mechanical"]["geometry"]
    parts = build_concept_assembly(config)
    hulls = [part for part in parts if part.identifier.startswith("hull_")]
    assert len(hulls) == 2
    for hull in hulls:
        extent_x = hull.vertices[:, 0].max() - hull.vertices[:, 0].min()
        extent_z = hull.vertices[:, 2].max() - hull.vertices[:, 2].min()
        assert abs(extent_x - float(geometry["hull_length_m"])) < 1e-9
        assert abs(extent_z - float(geometry["hull_height_m"])) < 1e-9
