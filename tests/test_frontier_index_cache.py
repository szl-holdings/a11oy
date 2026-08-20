from __future__ import annotations

import datetime as dt

import szl_frontier_index as frontier


def _clear_catalog_cache() -> None:
    if hasattr(frontier.build_catalog, "_cache"):
        delattr(frontier.build_catalog, "_cache")


def test_catalog_ttl_starts_after_probe_completes(monkeypatch) -> None:
    """A slow catalog build must not consume its own cache lifetime."""

    real_datetime = dt.datetime
    ticks = iter([100.0, 200.0, 201.0])

    class FakeDatetime(real_datetime):
        @classmethod
        def now(cls, tz=None):
            return real_datetime.fromtimestamp(next(ticks), tz)

    app = object()
    catalog = {"surfaces": []}
    calls: list[tuple[object, str]] = []

    monkeypatch.setattr(frontier.datetime, "datetime", FakeDatetime)
    monkeypatch.setattr(
        frontier,
        "_build_catalog",
        lambda current_app, namespace: calls.append((current_app, namespace))
        or catalog,
    )

    _clear_catalog_cache()
    try:
        first = frontier.build_catalog(app, "a11oy")
        second = frontier.build_catalog(app, "a11oy")
    finally:
        _clear_catalog_cache()

    assert first is catalog
    assert second is catalog
    assert calls == [(app, "a11oy")]
