import pytest
from aquaskim.config import load_base_configuration
from aquaskim.geometry import CatamaranGeometry, GeometryError

def test_geometry_valid_and_capacity_positive():
    g=CatamaranGeometry.from_config(load_base_configuration().data)
    assert g.overall_width_m > g.hull_width_m
    assert g.capacity_mass_kg > 0
    assert g.waterplane_area_m2 > 0

def test_full_design_preview_has_freeboard():
    cfg=load_base_configuration().data;g=CatamaranGeometry.from_config(cfg)
    assert g.freeboard_preview_m(3.0+cfg["mechanical"]["geometry"]["design_payload_kg"]) > 0

def test_invalid_collector_rejected():
    d=load_base_configuration().data
    d["mechanical"]["geometry"]["collector_outlet_width_m"]=1.0
    with pytest.raises(GeometryError): CatamaranGeometry.from_config(d)
