"""Unit tests for the repository Git policy validator."""

from __future__ import annotations

import unittest

from scripts.ci.validate_git_policy import PolicyError, validate_policy


class GitPolicyValidatorTest(unittest.TestCase):
    def test_valid_metadata_passes(self) -> None:
        validate_policy(
            branch="feat/xdl-pr015-eod-quote-ingestion",
            commit_subjects=[
                "feat(xdl-pr015-eod-quote-ingestion): add deterministic quote ingestion",
                "test(xdl-pr015-eod-quote-ingestion): cover correction overlap",
            ],
            pr_title="feat(xdl-pr015-eod-quote-ingestion): add deterministic quote ingestion",
        )

    def test_branch_without_exact_work_order_fails(self) -> None:
        with self.assertRaises(PolicyError):
            validate_policy(
                branch="feat/quote-ingestion",
                commit_subjects=["feat(xdl-pr015-eod-quote-ingestion): add quotes"],
            )

    def test_non_conventional_commit_fails(self) -> None:
        with self.assertRaises(PolicyError):
            validate_policy(
                branch="feat/xdl-pr015-eod-quote-ingestion",
                commit_subjects=["add quotes"],
            )

    def test_commit_with_sibling_work_order_fails(self) -> None:
        with self.assertRaises(PolicyError):
            validate_policy(
                branch="feat/xdl-pr015-eod-quote-ingestion",
                commit_subjects=["feat(xdl-pr016-dividend-ingestion): add quotes"],
            )

    def test_pr_title_with_sibling_work_order_fails(self) -> None:
        with self.assertRaises(PolicyError):
            validate_policy(
                branch="feat/xdl-pr015-eod-quote-ingestion",
                commit_subjects=["feat(xdl-pr015-eod-quote-ingestion): add quotes"],
                pr_title="feat(xdl-pr016-dividend-ingestion): add quotes",
            )

    def test_missing_commits_fails(self) -> None:
        with self.assertRaises(PolicyError):
            validate_policy(
                branch="feat/xdl-pr015-eod-quote-ingestion",
                commit_subjects=[],
            )


if __name__ == "__main__":
    unittest.main()
