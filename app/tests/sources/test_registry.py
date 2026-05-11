import asyncio

import pytest

from shared_config_manager import config, configuration
from shared_config_manager.sources import registry


class _ConcurrencyProbe:
    def __init__(self) -> None:
        self.active = 0
        self.max_active = 0
        self._lock = asyncio.Lock()

    async def run(self) -> None:
        async with self._lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        await asyncio.sleep(0.05)
        async with self._lock:
            self.active -= 1


class _DummySource:
    def __init__(
        self,
        source_id: str,
        source_config: configuration.SourceConfig,
        probe: _ConcurrencyProbe,
    ) -> None:
        self._source_id = source_id
        self._source_config = source_config
        self._probe = probe

    async def refresh_or_fetch(self) -> None:
        await self._probe.run()

    async def delete(self) -> None:
        pass

    def get_config(self) -> configuration.SourceConfig:
        return self._source_config


@pytest.mark.asyncio
async def test_do_handle_master_config_loads_sources_concurrently(monkeypatch: pytest.MonkeyPatch) -> None:
    probe = _ConcurrencyProbe()

    monkeypatch.setattr(registry, "_SOURCES", {})
    monkeypatch.setattr(registry, "FILTERED_SOURCES", {})
    monkeypatch.setattr(config.settings.slave, "tag_filter", None)
    monkeypatch.setattr(config.settings.slave, "init_sources_concurrency", 2)

    def create_source(
        source_id: str,
        source_config: configuration.SourceConfig,
        is_master: bool = False,
    ) -> _DummySource:
        del is_master
        return _DummySource(source_id, source_config, probe)

    monkeypatch.setattr(registry, "_create_source", create_source)

    master_config: configuration.Config = {
        "sources": {f"source-{index}": {"type": "git"} for index in range(5)}
    }

    success, errors = await registry._do_handle_master_config(master_config)

    assert success == 5
    assert errors == 0
    assert probe.max_active == 2
