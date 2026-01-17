import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import c2casgiutils.config
import sentry_sdk
from c2casgiutils import broadcast, headers, health_checks
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from prometheus_client import start_http_server
from prometheus_fastapi_instrumentator import Instrumentator

from shared_config_manager import api, config, nonce, slave_status, ui
from shared_config_manager.sources import base, registry

_LOGGER = logging.getLogger(__name__)
_WATCH_SOURCE_TASK: asyncio.Task[None] | None = None


async def _source_needs_refresh(source_id: str) -> bool:
    """Check if a source needs to be refreshed based on slave statuses."""
    slaves = await slave_status.get_source_status(source_id=source_id) or []
    hash_ = ""
    for slave in slaves:
        if slave is None or slave.get("filtered", False):
            continue

        slave_hash = slave.get("hash")
        hostname = slave.get("hostname")
        _LOGGER.debug("Watching slave %s for source %s, with hash %s", hostname, source_id, slave_hash)

        if slave_hash is None:
            _LOGGER.warning("No hash in slave '%s' status for source '%s' -> refresh.", hostname, source_id)
            return True

        if not isinstance(slave_hash, str):
            _LOGGER.warning(
                "Hash '%s' in slave '%s' status for source '%s' is not a string -> refresh.",
                slave_hash,
                hostname,
                source_id,
            )
            return True

        if not hash_:
            hash_ = slave_hash
        elif slave_hash != hash_:
            _LOGGER.warning(
                "Hash in slave '%s' for source '%s' is different from other slaves -> refresh.",
                hostname,
                source_id,
            )
            return True
    return False


async def _watch_source() -> None:
    """Watch the source."""
    while True:
        _LOGGER.debug("Watching the sources")
        try:
            has_error = False
            for key, source in registry.get_sources().items():
                _LOGGER.debug("Watching the source %s", key)
                try:
                    if source.is_master():
                        continue

                    if await _source_needs_refresh(key):
                        await source.refresh()
                        await broadcast.broadcast("slave_fetch", params={"source_id": key})

                except Exception:  # noqa: BLE001
                    await registry.update_flag("SOURCE_ERROR")
                    _LOGGER.warning("Error while watching the source %s", key, exc_info=True)
                    has_error = True
            if not has_error:
                await registry.update_flag("READY")
        except Exception:
            await registry.update_flag("ERROR")
            _LOGGER.exception("Error while watching the sources")
        await asyncio.sleep(config.settings.watch_source_interval)


# Initialize Sentry if the URL is provided
if c2casgiutils.config.settings.sentry.dsn:
    _LOGGER.info("Sentry is enabled with URL: %s", c2casgiutils.config.settings.sentry.dsn)
    sentry_sdk.init(**c2casgiutils.config.settings.sentry.model_dump())


@asynccontextmanager
async def _lifespan(main_app: FastAPI) -> AsyncGenerator[None, None]:
    """Handle application lifespan events."""

    _LOGGER.info("Starting the application")
    await c2casgiutils.startup(main_app)
    await slave_status.init()
    await base.init()
    await api.startup(main_app)

    global _WATCH_SOURCE_TASK  # noqa: PLW0603
    _WATCH_SOURCE_TASK = asyncio.create_task(_watch_source())

    if not config.settings.is_slave:
        await registry.init(slave=False)

    yield


# Core Application Instance
app = FastAPI(title="Shared config manager", lifespan=_lifespan)

# Add TrustedHostMiddleware (should be first)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"],  # Configure with specific hosts in production
)

http = config.settings.http
# Add HTTPSRedirectMiddleware
if not http:
    _LOGGER.info("HTTPS redirect middleware is enabled")
    app.add_middleware(HTTPSRedirectMiddleware)

# Add GZipMiddleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Set all CORS origins enabled
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_ui_headers: dict[str, str | list[str] | dict[str, str] | dict[str, list[str]] | None] = {
    "Content-Security-Policy": {
        "default-src": ["'self'"],
        "script-src-elem": ["'self'", f"'nonce-{nonce}'"],
        "style-src-elem": ["'self'", f"'nonce-{nonce}'", "https://cdnjs.cloudflare.com/"],
        "style-src-attr": ["'self'"],
    },
    "Cache-Control": "max-age=10",
}
route_prefix = config.settings.route_prefix
if route_prefix and route_prefix.startswith("/"):
    route_prefix = route_prefix[1:]
if route_prefix and route_prefix.endswith("/"):
    route_prefix = route_prefix[:-1]

_LOGGER.info("Using route prefix: '%s'", route_prefix)
app.add_middleware(
    headers.ArmorHeaderMiddleware,
    headers_config={
        "http": {"headers": {"Strict-Transport-Security": None} if http else {}},
        "ui_index": {
            "path_match": rf"{route_prefix}/$",
            "headers": _ui_headers,
            "status_code": 200,
        },
        "ui_sources": {
            "path_match": rf"{route_prefix}/source/.*",
            "headers": _ui_headers,
            "status_code": 200,
        },
        "api": {
            "path_match": rf"{route_prefix}/1/.*",
            "headers": {
                "Cache-Control": "max-age=0, no-cache, no-store, must-revalidate",
            },
            "status_code": 200,
        },
    },
)

# Add Health Checks
health_checks.FACTORY.add(health_checks.Redis(tags=["liveness", "redis", "all"]))
health_checks.FACTORY.add(health_checks.Wrong(tags=["wrong", "all"]))

# Add Routers
app.mount(f"{config.settings.route_prefix}/1", api.app)
app.mount(f"{config.settings.route_prefix}/c2c", c2casgiutils.app)
app.mount(f"{config.settings.route_prefix}/", ui.app)

# Get Prometheus HTTP server port from environment variable 9000 by default
start_http_server(c2casgiutils.config.settings.prometheus.port)

instrumentator = Instrumentator(should_instrument_requests_inprogress=True)
instrumentator.instrument(app)
