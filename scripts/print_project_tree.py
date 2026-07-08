from __future__ import annotations

from pathlib import Path

from aquaskim.paths import PROJECT_ROOT


def render_tree(path: Path, prefix: str = "") -> list[str]:
    ignored = {".git", "__pycache__", ".pytest_cache"}
    children = [child for child in sorted(path.iterdir()) if child.name not in ignored]
    lines: list[str] = []
    for index, child in enumerate(children):
        connector = "└── " if index == len(children) - 1 else "├── "
        lines.append(f"{prefix}{connector}{child.name}")
        if child.is_dir():
            extension = "    " if index == len(children) - 1 else "│   "
            lines.extend(render_tree(child, prefix + extension))
    return lines


if __name__ == "__main__":
    print(PROJECT_ROOT.name)
    print("\n".join(render_tree(PROJECT_ROOT)))
