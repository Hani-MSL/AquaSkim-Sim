from __future__ import annotations

import re

from aquaskim.paths import PROJECT_ROOT
from aquaskim.visual_quality import PALETTE


def test_phase10_11_uses_only_declared_visual_palette_keys() -> None:
    source = (PROJECT_ROOT / "src" / "aquaskim" / "phase10_11.py").read_text(encoding="utf-8")
    keys = re.findall(r"PALETTE\[['\"]([^'\"]+)['\"]\]", source)
    assert keys
    assert set(keys) <= set(PALETTE)
