from __future__ import annotations

"""Public-repository hygiene checks for AquaSkim-Sim."""

from dataclasses import dataclass
import json
import subprocess

from aquaskim.paths import PROJECT_ROOT

FORBIDDEN_ROOT_FILES = {"cd", "dir", "powershell", "tar", "type", "src_placeholder", "run_all.sh"}
FORBIDDEN_LOCAL_FILES = {
    "config/report_metadata.json",
    "config/user_profile.yaml",
}
REQUIRED_PUBLIC_FILES = {
    "README.md",
    "README_FA.md",
    "LICENSE",
    "environment.yml",
    "pyproject.toml",
    "scripts/run_from_zero_to_delivery.bat",
    "scripts/run_from_zero_to_delivery.sh",
    "src/aquaskim/rebuild_from_zero.py",
    "config/report_metadata.template.json",
    ".github/workflows/ci.yml",
}
REQUIRED_README_PHRASES = {
    "scripts\\run_from_zero_to_delivery.bat",
    "DELIVERY_PACKAGE_READY",
    "No sea-trial certification",
    "outputs\\deliverables\\AquaSkim-Sim_Final_Delivery_v1.6.21.zip",
}
ALLOWED_GENERATED_TRACKED_FILES = {
    "outputs/.gitkeep",
    "outputs/README_FA.md",
    "records/.gitkeep",
    "records/project_phase_registry.yaml",
}


@dataclass(frozen=True)
class ReadinessCheck:
    name: str
    passed: bool
    detail: str


def _exists(relative: str) -> bool:
    return (PROJECT_ROOT / relative).exists()


def _tracked_generated_artifacts() -> list[str]:
    """Return generated output files that are actually tracked by Git.

    CI and local audit commands may create untracked files under outputs/ or
    records/. Those files should not fail a public-repository hygiene check;
    only files that are part of the Git index should be treated as committed
    generated artifacts.
    """
    try:
        completed = subprocess.run(
            ["git", "ls-files", "outputs", "records"],
            cwd=PROJECT_ROOT,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError:
        return []
    if completed.returncode != 0:
        return []
    tracked = [line.strip().replace("\\", "/") for line in completed.stdout.splitlines() if line.strip()]
    return sorted(path for path in tracked if path not in ALLOWED_GENERATED_TRACKED_FILES)


def run_github_readiness_checks() -> list[ReadinessCheck]:
    checks: list[ReadinessCheck] = []

    missing = sorted(path for path in REQUIRED_PUBLIC_FILES if not _exists(path))
    checks.append(ReadinessCheck("required_public_files", not missing, json.dumps(missing, ensure_ascii=False)))

    root_hits = sorted(path.name for path in PROJECT_ROOT.iterdir() if path.is_file() and path.name in FORBIDDEN_ROOT_FILES)
    checks.append(ReadinessCheck("no_accidental_root_command_files", not root_hits, json.dumps(root_hits, ensure_ascii=False)))

    local_hits = sorted(path for path in FORBIDDEN_LOCAL_FILES if _exists(path))
    checks.append(ReadinessCheck("no_local_metadata_files", not local_hits, json.dumps(local_hits, ensure_ascii=False)))

    generated_hits = _tracked_generated_artifacts()
    checks.append(ReadinessCheck("no_generated_outputs_committed", not generated_hits, json.dumps(generated_hits, ensure_ascii=False)))

    readme = PROJECT_ROOT / "README.md"
    text = readme.read_text(encoding="utf-8") if readme.exists() else ""
    missing_phrases = sorted(phrase for phrase in REQUIRED_README_PHRASES if phrase not in text)
    checks.append(ReadinessCheck("readme_documents_one_command_rebuild", not missing_phrases, json.dumps(missing_phrases, ensure_ascii=False)))

    gitignore = PROJECT_ROOT / ".gitignore"
    gitignore_text = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    required_ignore_tokens = ["outputs/**", "records/**", "config/report_metadata.json", "config/user_profile.yaml"]
    missing_ignore_tokens = sorted(token for token in required_ignore_tokens if token not in gitignore_text)
    checks.append(ReadinessCheck("gitignore_protects_generated_and_local_files", not missing_ignore_tokens, json.dumps(missing_ignore_tokens, ensure_ascii=False)))

    return checks


def main() -> int:
    checks = run_github_readiness_checks()
    print("=" * 72)
    print("AquaSkim-Sim | GitHub publication readiness")
    print("=" * 72)
    for check in checks:
        state = "OK" if check.passed else "FAIL"
        print(f"[{state}] {check.name}: {check.detail}")
    passed = all(check.passed for check in checks)
    print(f"Status: {'PASS' if passed else 'FAIL'}")
    print("=" * 72)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
