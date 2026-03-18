from typing import Literal

from c2casgiutils.auth import AuthConfig
from pydantic import BaseModel

from shared_config_manager import configuration


class SourceStatus(BaseModel):
    """Source status."""

    filtered: bool = False
    template_engines: list[configuration.TemplateEnginesStatus] = []
    hash: str | None = None
    auth: AuthConfig | None = None

    # from configuration.SourceBase
    type: Literal["git", "rsync", "rclone"] | None = None
    target_dir: str | None = None
    excludes: list[str] = []
    tags: list[str] = []
    # git
    branch: str | None = None
    repo: str | None = None
    sub_dir: str | None = None
    sparse: bool | None = None
    ssh_key: str | None = None
    # rsync
    source: str | None = None
    # rclone
    config: str | None = None


class SlaveStatus(BaseModel):
    """Slave status."""

    sources: dict[str, SourceStatus]
