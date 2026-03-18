import types

import c2casgiutils
import pytest

from shared_config_manager import sentry


def _make_sentry_config(dsn: str | None, tags: dict[str, str] | None) -> types.SimpleNamespace:
    return types.SimpleNamespace(
        dsn=dsn,
        tags=tags,
        model_dump=lambda: {
            "dsn": dsn,
            "environment": "test",
            "tags": tags,
            "traces_sample_rate": None,
        },
    )


def _make_settings(dsn: str | None, tags: dict[str, str] | None) -> types.SimpleNamespace:
    return types.SimpleNamespace(sentry=_make_sentry_config(dsn, tags))


def test_init_sentry_skips_without_dsn(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, list[tuple | dict]] = {"init": [], "tag": []}

    monkeypatch.setattr(sentry, "c2casgiutils", types.SimpleNamespace(config=types.SimpleNamespace()))
    monkeypatch.setattr(
        c2casgiutils.config,
        "settings",
        _make_settings(dsn=None, tags={"service": "scm"}),
    )
    monkeypatch.setattr(sentry.sentry_sdk, "init", lambda **kwargs: calls["init"].append(kwargs))
    monkeypatch.setattr(
        sentry.sentry_sdk,
        "set_tag",
        lambda tag, value: calls["tag"].append((tag, value)),
    )

    sentry.init_sentry()

    assert calls["init"] == []
    assert calls["tag"] == []


def test_init_sentry_sets_tags(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, list[tuple | dict]] = {"init": [], "tag": []}

    monkeypatch.setattr(sentry, "c2casgiutils", types.SimpleNamespace(config=types.SimpleNamespace()))
    monkeypatch.setattr(
        c2casgiutils.config,
        "settings",
        _make_settings(dsn="https://example.com/1", tags={"service": "scm"}),
    )
    monkeypatch.setattr(sentry.sentry_sdk, "init", lambda **kwargs: calls["init"].append(kwargs))
    monkeypatch.setattr(
        sentry.sentry_sdk,
        "set_tag",
        lambda tag, value: calls["tag"].append((tag, value)),
    )

    sentry.init_sentry()

    assert calls["init"] == [{"dsn": "https://example.com/1", "environment": "test"}]
    assert calls["tag"] == [("service", "scm")]
