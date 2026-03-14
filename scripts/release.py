"""Bump app version, commit, tag, push, and create a GitHub release."""

from __future__ import annotations

import argparse
from datetime import date
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_METADATA_PATH = PROJECT_ROOT / "app_metadata.py"
README_PATH = PROJECT_ROOT / "README.md"
SETTINGS_PATH = PROJECT_ROOT / "videosplitter.settings.json"
BUILD_SCRIPT_PATH = PROJECT_ROOT / "build_exe.py"
EXE_PATH = PROJECT_ROOT / "VideoSplitter.exe"
CHANGELOG_PATH = PROJECT_ROOT / "CHANGELOG.md"

CHANGELOG_CATEGORIES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Features", ("feat",)),
    ("Fixes", ("fix",)),
    ("Documentation", ("docs",)),
    ("Tests", ("test",)),
    ("Build and CI", ("build", "ci")),
    ("Maintenance", ("chore", "refactor", "perf", "style")),
)


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        details = "\n".join(part for part in (result.stdout.strip(), result.stderr.strip()) if part)
        raise RuntimeError(f"Comando fallido: {' '.join(command)}\n{details}".strip())
    return result


def normalize_repo_url(raw_url: str) -> str:
    normalized = raw_url.strip()
    if normalized.endswith(".git"):
        normalized = normalized[:-4]
    if normalized.startswith("git@github.com:"):
        normalized = f"https://github.com/{normalized.split(':', 1)[1]}"
    return normalized


def classify_subject(subject: str) -> str:
    lowered = subject.strip().lower()
    for category, prefixes in CHANGELOG_CATEGORIES:
        if any(lowered.startswith(f"{prefix}:") or lowered.startswith(f"{prefix}(") for prefix in prefixes):
            return category
    return "Other"


def categorize_commit_subjects(subjects: list[str]) -> dict[str, list[str]]:
    categories: dict[str, list[str]] = {name: [] for name, _ in CHANGELOG_CATEGORIES}
    categories["Other"] = []

    for subject in subjects:
        categories[classify_subject(subject)].append(subject)

    return {category: items for category, items in categories.items() if items}


def render_categorized_subjects(categories: dict[str, list[str]]) -> str:
    sections: list[str] = []
    for category, items in categories.items():
        sections.append(f"### {category}")
        sections.extend(f"- {item}" for item in items)
        sections.append("")
    return "\n".join(sections).strip()


def ensure_changelog_exists() -> None:
    if CHANGELOG_PATH.exists():
        return
    CHANGELOG_PATH.write_text(
        "# Changelog\n\nAll notable changes to this project will be documented in this file.\n\n",
        encoding="utf-8",
    )


def update_changelog(version_text: str, previous_tag: str | None, release_message: str) -> None:
    ensure_changelog_exists()
    existing = CHANGELOG_PATH.read_text(encoding="utf-8")

    subjects = commit_subjects_since(previous_tag)
    if release_message not in subjects:
        subjects.append(release_message)

    categorized = categorize_commit_subjects(subjects)
    categorized_markdown = render_categorized_subjects(categorized)

    compare_line = ""
    repo_url = repo_web_url()
    if previous_tag and repo_url:
        compare_line = f"- Compare: {repo_url}/compare/{previous_tag}...v{version_text}\n"

    entry = (
        f"## V{version_text} - {date.today().isoformat()}\n\n"
        f"- Release message: {release_message}\n"
        f"{compare_line}\n"
        f"{categorized_markdown}\n\n"
    )

    if existing.startswith("# Changelog"):
        head, _, tail = existing.partition("\n\n")
        updated = f"{head}\n\n{entry}{tail.lstrip()}"
    else:
        updated = f"# Changelog\n\n{entry}{existing}"
    CHANGELOG_PATH.write_text(updated, encoding="utf-8")


def read_version() -> tuple[int, int, int]:
    match = re.search(
        r'^APP_VERSION\s*=\s*"(?P<version>\d+\.\d+\.\d+)"',
        APP_METADATA_PATH.read_text(encoding="utf-8"),
        flags=re.MULTILINE,
    )
    if not match:
        raise RuntimeError("No se pudo leer APP_VERSION desde app_metadata.py")

    version_text = match.group("version")
    major, minor, patch = (int(part) for part in version_text.split("."))
    return major, minor, patch


def bump_version(current: tuple[int, int, int], level: str) -> tuple[int, int, int]:
    major, minor, patch = current
    if level == "major":
        return major + 1, 0, 0
    if level == "minor":
        return major, minor + 1, 0
    return major, minor, patch + 1


def replace_single(pattern: str, replacement: str, content: str) -> str:
    updated, count = re.subn(pattern, replacement, content, count=1, flags=re.MULTILINE)
    if count != 1:
        raise RuntimeError(f"No se pudo actualizar el patron: {pattern}")
    return updated


def update_version_files(version_text: str) -> None:
    metadata = APP_METADATA_PATH.read_text(encoding="utf-8")
    metadata = replace_single(
        r'^APP_VERSION\s*=\s*"\d+\.\d+\.\d+"',
        f'APP_VERSION = "{version_text}"',
        metadata,
    )
    APP_METADATA_PATH.write_text(metadata, encoding="utf-8")

    readme = README_PATH.read_text(encoding="utf-8")
    readme = replace_single(
        r'^# VideoSplitter V\d+\.\d+\.\d+',
        f'# VideoSplitter V{version_text}',
        readme,
    )
    README_PATH.write_text(readme, encoding="utf-8")

    settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    settings["app_version"] = version_text
    SETTINGS_PATH.write_text(json.dumps(settings, ensure_ascii=True, indent=2), encoding="utf-8")


def git_has_changes() -> bool:
    result = run(["git", "status", "--porcelain"])
    return bool(result.stdout.strip())


def latest_tag() -> str | None:
    result = run(["git", "tag", "--sort=-v:refname"])
    tags = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return tags[0] if tags else None


def repo_web_url() -> str | None:
    result = run(["git", "config", "--get", "remote.origin.url"])
    value = result.stdout.strip()
    if not value:
        return None
    return normalize_repo_url(value)


def changed_files_for_head() -> list[str]:
    result = run(["git", "diff-tree", "--no-commit-id", "--name-only", "--root", "-r", "HEAD"])
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def commit_subjects_since(previous_tag: str | None) -> list[str]:
    command = ["git", "log", "--pretty=format:%s"]
    if previous_tag:
        command.append(f"{previous_tag}..HEAD")
    else:
        command.extend(["-n", "1", "HEAD"])
    result = run(command)
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def build_release_notes(
    *,
    version_text: str,
    release_level: str,
    release_message: str,
    previous_tag: str | None,
    changed_files: list[str],
    commit_subjects: list[str],
    repo_url: str | None,
) -> str:
    tag_name = f"v{version_text}"
    compare_line = ""
    if previous_tag and repo_url:
        compare_line = f"- Compare: {repo_url}/compare/{previous_tag}...{tag_name}\n"

    file_lines = "\n".join(f"- `{file_path}`" for file_path in changed_files[:10]) or "- No file summary available"
    commit_lines = "\n".join(f"- {subject}" for subject in commit_subjects) or f"- {release_message}"
    categorized = categorize_commit_subjects(commit_subjects or [release_message])
    categorized_lines = render_categorized_subjects(categorized)

    return (
        f"# VideoSplitter V{version_text}\n\n"
        f"## Highlights\n"
        f"- Release type: {release_level}\n"
        f"- Main change: {release_message}\n"
        f"- Asset included: VideoSplitter.exe\n"
        f"{compare_line}\n"
        f"## Included Commits\n"
        f"{commit_lines}\n\n"
        f"## Change Types\n"
        f"{categorized_lines}\n\n"
        f"## Key Files\n"
        f"{file_lines}\n\n"
        f"## Notes\n"
        f"- App, tag and settings version are aligned to V{version_text}.\n"
        f"- Desktop executable was rebuilt for this release.\n"
    )


def ensure_clean_or_changes_present() -> None:
    if not git_has_changes():
        raise RuntimeError("No hay cambios para commitear.")


def build_executable() -> None:
    run([sys.executable, str(BUILD_SCRIPT_PATH)])


def create_commit_and_release(
    message: str,
    version_text: str,
    release_level: str,
    previous_tag: str | None,
    attach_exe: bool,
) -> None:
    tag_name = f"v{version_text}"
    release_title = f"V{version_text}"

    run(["git", "add", "-A"])
    run(["git", "commit", "-m", message])
    run(["git", "tag", "-a", tag_name, "-m", f"Release {release_title}"])
    run(["git", "push", "origin", "main"])
    run(["git", "push", "origin", tag_name])
    release_notes = build_release_notes(
        version_text=version_text,
        release_level=release_level,
        release_message=message,
        previous_tag=previous_tag,
        changed_files=changed_files_for_head(),
        commit_subjects=commit_subjects_since(previous_tag),
        repo_url=repo_web_url(),
    )
    command = [
        "gh",
        "release",
        "create",
        tag_name,
        "--title",
        release_title,
    ]
    with tempfile.TemporaryDirectory(prefix="videosplitter_release_notes_") as temp_dir:
        notes_path = Path(temp_dir) / "release_notes.md"
        notes_path.write_text(release_notes, encoding="utf-8")
        command.extend(["--notes-file", str(notes_path)])
        if attach_exe and EXE_PATH.exists():
            command.append(str(EXE_PATH))
        run(command)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Incrementa la version, crea commit, tag, push y release en GitHub."
    )
    parser.add_argument("message", help="Mensaje del commit de release")
    parser.add_argument(
        "--level",
        choices=("patch", "minor", "major"),
        default="patch",
        help="Nivel de incremento semantico. Por defecto: patch.",
    )
    parser.add_argument(
        "--skip-build-exe",
        action="store_true",
        help="No recompila ni adjunta VideoSplitter.exe a la release.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    ensure_clean_or_changes_present()
    previous_tag = latest_tag()

    current = read_version()
    next_version = bump_version(current, args.level)
    next_version_text = ".".join(str(part) for part in next_version)

    update_version_files(next_version_text)
    update_changelog(next_version_text, previous_tag, args.message)
    if not args.skip_build_exe:
        build_executable()
    create_commit_and_release(
        args.message,
        next_version_text,
        release_level=args.level,
        previous_tag=previous_tag,
        attach_exe=not args.skip_build_exe,
    )

    print(f"Release completada: V{next_version_text}")


if __name__ == "__main__":
    main()