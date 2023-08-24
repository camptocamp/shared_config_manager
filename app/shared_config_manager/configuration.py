from typing import TypedDict

from c2cwsgiutils.auth import AuthConfig


class _SourceBase(TypedDict, total=False):
    type: str
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
    type: str
    dest_sub_dir: str
    environment_variables: bool
    data: dict[str, str]


class SourceConfig(_SourceBase, total=False):
    name: str
    auth: AuthConfig
    template_engines: list[TemplateEnginesConfig]


class TemplateEnginesStatus(TypedDict, total=False):
    type: str
    environment_variables: dict[str, str]
    data: dict[str, str]


class BroadcastObject(TypedDict, total=False):
    hostname: str
    pid: int


class SourceStatus(_SourceBase, BroadcastObject, total=False):
    filtered: bool
    template_engines: list[TemplateEnginesStatus]
    hash: str


class SlaveStatus(BroadcastObject, total=False):
    sources: dict[str, SourceStatus]


class Config(TypedDict, total=False):
    sources: dict[str, SourceConfig]
