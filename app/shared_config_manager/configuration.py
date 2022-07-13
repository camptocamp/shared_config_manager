from typing import Dict, List, TypedDict


class _SourceBase(TypedDict, total=False):
    type: str
    target_dir: str
    excludes: List[str]
    tags: List[str]
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
    data: Dict[str, str]


class SourceConfig(_SourceBase, total=False):
    key: str
    template_engines: List[TemplateEnginesConfig]


class TemplateEnginesStatus(TypedDict, total=False):
    type: str
    environment_variables: Dict[str, str]
    data: Dict[str, str]


class BroadcastObject(TypedDict, total=False):
    hostname: str
    pid: int


class SourceStatus(_SourceBase, BroadcastObject, total=False):
    filtered: bool
    template_engines: List[TemplateEnginesStatus]


class SlaveStatus(BroadcastObject, total=False):
    sources: Dict[str, SourceStatus]


class Config(TypedDict, total=False):
    key: str
    sources: Dict[str, SourceConfig]
