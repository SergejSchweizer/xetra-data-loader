from pathlib import Path

from xetra_loader.ops.reset import build_reset_plan, execute_reset, main


class _Context:
    def __init__(self, value: object) -> None:
        self.value = value

    def __enter__(self) -> object:
        return self.value

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None


class FakeCursor:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def execute(self, statement: str) -> None:
        self.statements.append(statement)


class FakeConnection:
    def __init__(self) -> None:
        self.cursor_value = FakeCursor()

    def transaction(self) -> _Context:
        return _Context(object())

    def cursor(self) -> _Context:
        return _Context(self.cursor_value)


def test_plan_contains_only_loader_owned_scope(tmp_path: Path) -> None:
    plan = build_reset_plan(tmp_path)
    assert plan.schemas == ("xetra_loader_sync", "xetra_loader")
    assert plan.medallion_paths == (
        tmp_path.resolve() / "bronze",
        tmp_path.resolve() / "silver",
        tmp_path.resolve() / "gold",
    )


def test_no_confirmation_performs_zero_deletion(tmp_path: Path) -> None:
    owned = tmp_path / "gold"
    owned.mkdir()
    marker = owned / "keep.txt"
    marker.write_text("safe", encoding="utf-8")
    execute_reset(build_reset_plan(tmp_path), confirmed=False, dry_run=False)
    assert marker.exists()


def test_dry_run_performs_zero_deletion_even_when_confirmed(tmp_path: Path) -> None:
    owned = tmp_path / "silver"
    owned.mkdir()
    marker = owned / "keep.txt"
    marker.write_text("safe", encoding="utf-8")
    execute_reset(build_reset_plan(tmp_path), confirmed=True, dry_run=True)
    assert marker.exists()


def test_confirmed_reset_deletes_owned_paths_and_leaves_unrelated_path(tmp_path: Path) -> None:
    for layer in ("bronze", "silver", "gold"):
        path = tmp_path / layer
        path.mkdir()
        (path / "data.txt").write_text(layer, encoding="utf-8")
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()
    (unrelated / "data.txt").write_text("untouched", encoding="utf-8")

    connection = FakeConnection()
    execute_reset(
        build_reset_plan(tmp_path),
        confirmed=True,
        dry_run=False,
        connection=connection,  # type: ignore[arg-type]
    )
    assert all(not (tmp_path / layer).exists() for layer in ("bronze", "silver", "gold"))
    assert (unrelated / "data.txt").read_text(encoding="utf-8") == "untouched"
    assert connection.cursor_value.statements == [
        "SET LOCAL TIME ZONE 'UTC'",
        'DROP SCHEMA IF EXISTS "xetra_loader_sync" CASCADE',
        'DROP SCHEMA IF EXISTS "xetra_loader" CASCADE',
    ]


def test_cli_without_confirmation_only_prints_plan(tmp_path: Path) -> None:
    assert main(["--medallion-root", str(tmp_path)]) == 0
