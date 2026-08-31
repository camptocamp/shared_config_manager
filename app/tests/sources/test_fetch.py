# Copyright (c) 2026, Camptocamp SA
import asyncio
import gzip
import io
import tarfile
from collections.abc import AsyncIterator
from pathlib import Path

import aiohttp
import pytest
import pytest_asyncio
from aiohttp import web

from shared_config_manager import config
from shared_config_manager.sources import base, mode, registry

SOURCE_ID = "test-src"


def _make_tar_gz(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        for name, content in files.items():
            data = content.encode("utf-8")
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return gzip.compress(buffer.getvalue())


class _MasterServer:
    def __init__(self) -> None:
        self.port = 0
        self.requests = 0
        self.status = 200
        self.payload = b""
        self.delay = 0.0

    async def handler(self, request: web.Request) -> web.Response:
        del request
        self.requests += 1
        if self.delay > 0:
            await asyncio.sleep(self.delay)
        if self.status != 200:
            return web.Response(status=self.status)
        return web.Response(body=self.payload)


@pytest_asyncio.fixture
async def master_server() -> AsyncIterator[_MasterServer]:
    server = _MasterServer()
    app = web.Application()
    app.router.add_get("/1/tarball/{source_id}", server.handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    server.port = site._server.sockets[0].getsockname()[1]
    try:
        yield server
    finally:
        await runner.cleanup()


@pytest_asyncio.fixture
async def slave_env(tmp_path, monkeypatch, master_server) -> AsyncIterator[Path]:
    await base.init()
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    monkeypatch.setattr(config.settings.slave, "target", config_dir)
    monkeypatch.setattr(config.settings.slave, "api_base_url", f"http://127.0.0.1:{master_server.port}/")
    monkeypatch.setattr(config.settings.slave, "retry_delay", 0)
    monkeypatch.setattr(mode, "_SLAVE", True)
    yield config_dir


def _create_source(source_config: dict) -> base.BaseSource:
    return registry._create_source(SOURCE_ID, source_config)


@pytest.mark.asyncio
async def test_fetch_installs_content_and_evaluates_templates(slave_env, master_server) -> None:
    master_server.payload = _make_tar_gz(
        {
            "config.yaml.mako": "value: ${FOO}",
            "other.txt": "static",
        },
    )
    source = _create_source(
        {
            "type": "rsync",
            "source": "/unused",
            "template_engines": [{"type": "mako", "data": {"FOO": "bar"}}],
        },
    )

    await source.fetch()

    target = slave_env / SOURCE_ID
    assert (target / "config.yaml").read_text(encoding="utf-8") == "value: bar"
    assert (target / "config.yaml.mako").read_text(encoding="utf-8") == "value: ${FOO}"
    assert (target / "other.txt").read_text(encoding="utf-8") == "static"
    assert source.is_loaded()
    leftovers = [path.name for path in slave_env.iterdir() if path.name.startswith(f".{SOURCE_ID}.")]
    assert leftovers == []


@pytest.mark.asyncio
async def test_fetch_keeps_previous_content_until_ready(slave_env, master_server) -> None:
    target = slave_env / SOURCE_ID
    target.mkdir()
    (target / "old-marker").write_text("old", encoding="utf-8")
    master_server.payload = _make_tar_gz({"new-file": "new"})
    master_server.delay = 0.5

    source = _create_source({"type": "rsync", "source": "/unused"})
    fetch_task = asyncio.create_task(source.fetch())
    await asyncio.sleep(0.1)
    assert (target / "old-marker").is_file()
    assert not (target / "new-file").exists()
    await fetch_task
    assert not (target / "old-marker").exists()
    assert (target / "new-file").read_text(encoding="utf-8") == "new"


@pytest.mark.asyncio
async def test_concurrent_fetches_are_serialized(slave_env, master_server) -> None:
    master_server.payload = _make_tar_gz({"new-file": "new"})
    master_server.delay = 0.1
    source = _create_source({"type": "rsync", "source": "/unused"})
    target = slave_env / SOURCE_ID

    tasks = [asyncio.create_task(source.fetch()) for _ in range(3)]
    created = False
    missing_after_created = False
    while not all(task.done() for task in tasks):
        exists = target.is_dir()
        if created and not exists:
            missing_after_created = True
        created = created or exists
        await asyncio.sleep(0.01)
    await asyncio.gather(*tasks)

    assert not missing_after_created
    assert created
    assert master_server.requests == 3
    assert (target / "new-file").read_text(encoding="utf-8") == "new"
    leftovers = [path.name for path in slave_env.iterdir() if path.name.startswith(f".{SOURCE_ID}.")]
    assert leftovers == []


@pytest.mark.asyncio
async def test_fetch_error_keeps_previous_content(slave_env, master_server) -> None:
    target = slave_env / SOURCE_ID
    target.mkdir()
    (target / "old-marker").write_text("old", encoding="utf-8")
    master_server.status = 404

    source = _create_source({"type": "rsync", "source": "/unused"})
    with pytest.raises(aiohttp.ClientResponseError):
        await source.fetch()

    assert master_server.requests == config.settings.slave.retry_number
    assert (target / "old-marker").read_text(encoding="utf-8") == "old"
    leftovers = [path.name for path in slave_env.iterdir() if path.name.startswith(f".{SOURCE_ID}.")]
    assert leftovers == []


@pytest.mark.asyncio
async def test_fetch_cleans_up_stale_leftovers(slave_env, master_server) -> None:
    fetch_leftover = slave_env / f".{SOURCE_ID}.fetch-deadbeef"
    fetch_leftover.mkdir()
    (fetch_leftover / "file").write_text("stale", encoding="utf-8")
    old_leftover = slave_env / f".{SOURCE_ID}.old-feedbeef"
    old_leftover.mkdir()
    master_server.payload = _make_tar_gz({"new-file": "new"})

    source = _create_source({"type": "rsync", "source": "/unused"})
    await source.fetch()

    leftovers = [path.name for path in slave_env.iterdir() if path.name.startswith(f".{SOURCE_ID}.")]
    assert leftovers == []
    assert (slave_env / SOURCE_ID / "new-file").read_text(encoding="utf-8") == "new"


@pytest.mark.asyncio
async def test_delete_target_dir_cleans_up_leftovers(slave_env) -> None:
    target = slave_env / SOURCE_ID
    target.mkdir()
    (target / "file").write_text("content", encoding="utf-8")
    leftover = slave_env / f".{SOURCE_ID}.fetch-deadbeef"
    leftover.mkdir()

    source = _create_source({"type": "rsync", "source": "/unused"})
    await source.delete()

    assert not target.exists()
    assert not leftover.exists()
