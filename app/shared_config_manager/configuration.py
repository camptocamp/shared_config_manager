from typing import Literal, TypedDict

from c2casgiutils.auth import AuthConfig


class SourceBase(TypedDict, total=False):
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


class SourceConfig(SourceBase, total=False):
    """Source configuration."""

    name: str
    auth: AuthConfig
    template_engines: list[TemplateEnginesConfig]


class TemplateEnginesStatus(TypedDict, total=False):
    """Template engine status."""

    type: str
    environment_variables: dict[str, str]
    data: dict[str, str]


class Config(TypedDict, total=False):
    """Overall configuration."""

    sources: dict[str, SourceConfig]
    standalone: bool
