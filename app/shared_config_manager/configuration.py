from typing import Literal, TypedDict

from c2casgiutils.auth import AuthConfig


class _SourceBase(TypedDict, total=False):
    type: Literal["git", "rsync", "rclone"]
    target_dir: str
    excludes: list[str]
    tags: list[str]
    # git
    branch: str
    repo: str
    sub_dir: str
    sparse: bool
    ssh_key: str
    # rsync
    source: str
    # rclone
    config: str


class TemplateEnginesConfig(TypedDict, total=False):
    """Template engine configuration."""

    type: str
    dest_sub_dir: str
    environment_variables: bool
    data: dict[str, str]


class SourceConfig(_SourceBase, total=False):
    """Source configuration."""

    name: str
    auth: AuthConfig
    template_engines: list[TemplateEnginesConfig]


class TemplateEnginesStatus(TypedDict, total=False):
    """Template engine status."""

    type: str
    environment_variables: dict[str, str]
    data: dict[str, str]


class BroadcastObject(TypedDict, total=False):
    """Base class for broadcasted objects."""

    hostname: str
    pid: int


class AuthConfig(TypedDict, total=False):
    """Authentication configuration."""

    github_access_type: str
    github_repository: str


class SourceStatus(_SourceBase, BroadcastObject, total=False):
    """Source status."""

    filtered: bool
    template_engines: list[TemplateEnginesStatus]
    hash: str
    auth: AuthConfig
    branch: str
    repo: str
    sub_dir: str
    tags: list[str]
    type: Literal["git", "rsync", "rclone"]


class SlaveStatus(BroadcastObject, total=False):
    """Slave status."""

    sources: dict[str, SourceStatus]


class Config(TypedDict, total=False):
    """Overall configuration."""

    sources: dict[str, SourceConfig]
