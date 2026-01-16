import logging
from typing import Protocol

from c2casgiutils import broadcast

from shared_config_manager import broadcast_status
from shared_config_manager.sources import registry

_LOG = logging.getLogger(__name__)


class GetSlavesStatusProto(Protocol):
    """Protocol for get_slaves_status function."""

    async def __call__(self) -> list[broadcast_status.SlaveStatus] | None: ...


get_slaves_status: GetSlavesStatusProto = None  # type: ignore[assignment]


async def _get_slaves_status() -> broadcast_status.SlaveStatus:
    """Get the status of all the slaves."""
    return broadcast_status.SlaveStatus(sources=registry.get_stats())


class GetSourceStatusProto(Protocol):
    """Protocol for get_source_status function."""

    async def __call__(self, *, source_id: str) -> list[broadcast_status.SourceStatus] | None: ...


get_source_status: GetSourceStatusProto = None  # type: ignore[assignment]


async def _get_source_status(*, source_id: str) -> broadcast_status.SourceStatus:
    """Get the status of a source."""
    source = registry.get_source(source_id)
    if source is None:
        return broadcast_status.SourceStatus(filtered=source_id in registry.FILTERED_SOURCES)
    return source.get_stats()


async def init() -> None:
    """Initialize the slave status manager."""

    global get_slaves_status, get_source_status  # noqa: PLW0603
    get_slaves_status = await broadcast.decorate(_get_slaves_status, expect_answers=True)
    get_source_status = await broadcast.decorate(_get_source_status, expect_answers=True)
