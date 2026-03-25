from typing import Literal

from c2casgiutils.auth import AuthConfig
from pydantic import BaseModel

from shared_config_manager import configuration


class SourceStatus(BaseModel):
    """Source status model."""

    filtered: bool | None = None
    template_engines: list[configuration.TemplateEnginesStatus] = []
    hash: str | None = None
    auth: AuthConfig | None = None
    branch: str | None = None
    repo: str | None = None
    sub_dir: str | None = None
    tags: list[str] = []
    type: Literal["git", "rsync", "rclone"] | None = None
    # rclone
    config: str | None = None


class SlaveStatus(BaseModel):
    """Slave status model."""

    sources: dict[str, SourceStatus]
