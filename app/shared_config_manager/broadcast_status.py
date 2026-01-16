from typing import TypedDict

from c2casgiutils.auth import AuthConfig

from shared_config_manager import configuration


class BroadcastObject(TypedDict, total=False):
    """Base class for broadcasted objects."""

    hostname: str
    pid: int


class SourceStatus(configuration.SourceBase, BroadcastObject, total=False):
    """Source status."""

    filtered: bool
    template_engines: list[configuration.TemplateEnginesStatus]
    hash: str
    auth: AuthConfig


class SlaveStatus(BroadcastObject, total=False):
    """Slave status."""

    sources: dict[str, SourceStatus]
