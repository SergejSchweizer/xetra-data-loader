from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "workflow",
    (".github/workflows/push-quality.yml", ".github/workflows/merge-quality.yml"),
)
def test_integration_job_provisions_and_requires_postgres(workflow: str) -> None:
    contents = Path(workflow).read_text(encoding="utf-8")

    integration = contents.split("  integration:\n", 1)[1].split("  policy:\n", 1)[0]
    assert "image: postgres:16" in integration
    assert "XDL_REQUIRE_POSTGRES_INTEGRATION: \"1\"" in integration
    expected_dsn = "XDL_TEST_POSTGRES_DSN: postgresql://postgres:postgres@localhost:5432/xdl_test"
    assert expected_dsn in integration
