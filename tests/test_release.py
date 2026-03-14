from __future__ import annotations

import unittest

from scripts import release


class ReleaseScriptTests(unittest.TestCase):
    def test_build_release_notes_contains_summary_sections(self) -> None:
        notes = release.build_release_notes(
            version_text="1.0.2",
            release_level="patch",
            release_message="docs: improve release notes",
            previous_tag="v1.0.1",
            changed_files=["README.md", "scripts/release.py", "tests/test_release.py"],
            commit_subjects=["docs: improve release notes"],
            repo_url="https://github.com/example/videosplitter",
        )

        self.assertIn("# VideoSplitter V1.0.2", notes)
        self.assertIn("## Highlights", notes)
        self.assertIn("## Change Types", notes)
        self.assertIn("### Documentation", notes)
        self.assertIn("README.md", notes)
        self.assertIn("https://github.com/example/videosplitter/compare/v1.0.1...v1.0.2", notes)

    def test_normalize_repo_url_supports_ssh_style(self) -> None:
        normalized = release.normalize_repo_url("git@github.com:example/videosplitter.git")
        self.assertEqual(normalized, "https://github.com/example/videosplitter")

    def test_categorize_commit_subjects_groups_by_type(self) -> None:
        categorized = release.categorize_commit_subjects(
            [
                "feat: new equal parts preview",
                "fix: repair ffmpeg lock handling",
                "docs: improve badges",
                "chore: tidy workflow",
            ]
        )

        self.assertIn("Features", categorized)
        self.assertIn("Fixes", categorized)
        self.assertIn("Documentation", categorized)
        self.assertIn("Maintenance", categorized)


if __name__ == "__main__":
    unittest.main()