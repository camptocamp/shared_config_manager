"""The configuration environment variables."""

import logging
from typing import Annotated

from anyio import Path
from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from pydantic.functional_validators import BeforeValidator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_LOGGER = logging.getLogger(__name__)


def _to_path(v: object) -> Path:
    if isinstance(v, Path):
        return v
    return Path(str(v))


_AnyioPath = Annotated[Path, BeforeValidator(_to_path)]


class SlaveSettings(BaseModel):
    """Slave related settings."""

    model_config = ConfigDict(validate_assignment=True, arbitrary_types_allowed=True)

    enabled: bool = False
    """Whether this instance is a slave (non-master) node. Defaults to False."""
    target: _AnyioPath = Path("/config")
    """Target directory where configuration is deployed on slave nodes."""
    retry_number: int = 3
    """Number of retry attempts when fetching configuration from the master."""
    retry_delay: int = 1
    """Delay in seconds between retry attempts when fetching configuration."""
    init_sources_concurrency: int = 4
    """Maximum number of sources to load concurrently at startup/reload."""
    api_base_url: str | None = None
    """Base URL for the shared config manager API (with trailing slash)."""
    tag_filter: str | None = None
    """Filter sources by tag on slave nodes. Only sources with this tag will be synced."""
    requests_timeout: float = 30
    """Timeout in seconds for HTTP requests made by the shared config manager."""

    @field_validator("api_base_url")
    @classmethod
    def validate_api_base_url(cls, value: str | None) -> str | None:
        if value is not None and not value.endswith("/"):
            value += "/"
        return value

    @field_validator("init_sources_concurrency")
    @classmethod
    def validate_init_sources_concurrency(cls, value: int) -> int:
        if value < 1:
            return 1
        return value

    @model_validator(mode="after")
    def validate_enabled_requires_api_base_url(self) -> "SlaveSettings":
        if self.enabled and self.api_base_url is None:
            msg = "SCM__SLAVE__API_BASE_URL is required when SCM__SLAVE__ENABLED is true"
            raise ValueError(msg)
        return self


class Settings(BaseSettings, extra="ignore"):
    """The configuration settings."""

    slave: SlaveSettings = SlaveSettings()
    """Group containing all slave related configuration."""
    secret: str | None = None
    """Shared secret for internal authentication between master and slave nodes."""
    master_target: _AnyioPath = Path("/master_config")
    """Target directory where configuration is deployed on the master node."""
    watch_source_interval: int = 600
    """Interval in seconds to check and refresh source configurations."""
    api_master: bool = False
    """
    Whether this instance exposes the shared config manager API as the master node.
    When this is True and slave nodes are present, templates will not be rendered
    on the master node (they are rendered only on slave nodes).
    """
    master_config: str | None = None
    """Master configuration YAML content as a string (used instead of loading from file)."""
    master_dispatch: bool = True
    """Whether to dispatch configuration updates from master to slaves."""
    env_prefixes: Annotated[list[str], NoDecode] = ["MUTUALIZED_"]
    """Environment variable prefixes to expose in templates (e.g., MUTUALIZED_)."""
    private_ssh_key: str | None = None
    """Private SSH key for accessing git repositories."""
    github_token: str | None = None
    """GitHub API token for accessing GitHub commit information."""
    github_secret: str | None = None
    """GitHub webhook secret for validating incoming webhook signatures."""
    model_config = SettingsConfigDict(env_prefix="SCM__", env_nested_delimiter="__")

    @field_validator("env_prefixes", mode="before")
    @classmethod
    def validate_env_prefixes(cls, value: str | list[str] | None) -> list[str]:
        if value is None:
            return ["MUTUALIZED_"]
        if isinstance(value, str):
            # Parse colon-separated string
            return [v.strip() for v in value.split(":") if v.strip()]
        return value


settings = Settings()
