from c2cwsgiutils import broadcast

from shared_config_manager.configuration import SlaveStatus, SourceStatus
from shared_config_manager.sources import registry


@broadcast.decorator(expect_answers=True)  # type: ignore[misc]
def get_slaves_status() -> SlaveStatus:
    """Get the status of all the slaves."""
    return {"sources": registry.get_stats()}


@broadcast.decorator(expect_answers=True)  # type: ignore[misc]
def get_source_status(id_: str) -> SourceStatus:
    """Get the status of a source."""
    source = registry.get_source(id_)
    if source is None:
        return {"filtered": id_ in registry.FILTERED_SOURCES}
    else:
        return source.get_stats()
