from email.message import Message
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest

from xetra_data_loader.eodhd import EodhdTransport, RetryPolicy, scrub_url


class FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def read(self) -> bytes:
        return self.payload

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None


def test_missing_token_is_clear(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EODHD_API_TOKEN", raising=False)
    with pytest.raises(ValueError, match="EODHD_API_TOKEN is required"):
        EodhdTransport()


def test_typed_get_uses_fixture_seam() -> None:
    seen: list[str] = []

    def opener(request: Request, timeout: float) -> FakeResponse:
        assert timeout == 5.0
        seen.append(request.full_url)
        return FakeResponse(b'{"ok":true,"rows":2}')

    transport = EodhdTransport(token="top-secret", timeout_seconds=5.0, opener=opener)
    assert transport.get_json("exchange-symbol-list/XETRA", {"limit": 2}) == {
        "ok": True,
        "rows": 2,
    }
    assert "api_token=top-secret" in seen[0]


def test_network_retries_are_bounded() -> None:
    attempts = 0
    sleeps: list[float] = []

    def opener(request: Request, timeout: float) -> FakeResponse:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise URLError("temporary")
        return FakeResponse(b"[]")

    transport = EodhdTransport(
        token="secret",
        opener=opener,
        sleeper=sleeps.append,
        retry_policy=RetryPolicy(max_attempts=3, base_delay_seconds=0.1, max_delay_seconds=1.0),
    )
    assert transport.get_json("eod/AAA.XETRA") == []
    assert attempts == 3
    assert sleeps == [0.1, 0.2]


def test_permanent_http_error_is_not_retried_or_leaked() -> None:
    attempts = 0

    def opener(request: Request, timeout: float) -> FakeResponse:
        nonlocal attempts
        attempts += 1
        raise HTTPError(request.full_url, 400, "bad request", Message(), None)

    transport = EodhdTransport(token="do-not-leak", opener=opener)
    with pytest.raises(RuntimeError) as captured:
        transport.get_json("eod/AAA.XETRA")
    assert attempts == 1
    assert "do-not-leak" not in str(captured.value)
    assert "HTTP 400" in str(captured.value)


def test_scrub_url_removes_common_secret_query_parameters() -> None:
    scrubbed = scrub_url("https://eodhd.com/api/eod/AAA?api_token=secret&fmt=json")
    assert "secret" not in scrubbed
    assert "api_token=***" in scrubbed
    assert "fmt=json" in scrubbed
