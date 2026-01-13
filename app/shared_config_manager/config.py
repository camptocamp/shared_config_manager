"""The configuration environment variables."""

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings, extra="ignore"):
    """The configuration settings."""

    is_slave: bool = False
    """Whether this instance is a slave (non-master) node. Defaults to False."""
    secret: str | None = None
    """Shared secret for internal authentication between master and slave nodes."""
    target: Path = Path("/config")
    """Target directory where configuration is deployed on slave nodes."""
    master_target: Path = Path("/master_config")
    """Target directory where configuration is deployed on the master node."""
    retry_number: int = 3
    """Number of retry attempts when fetching configuration from the master."""
    retry_delay: int = 1
    """Delay in seconds between retry attempts when fetching configuration."""
    watch_source_interval: int = 600
    """Interval in seconds to check and refresh source configurations."""
    api_base_url: str | None = None
    """Base URL for the shared config manager API (with trailing slash)."""
    api_master: str | None = None
    """Master API endpoint URL for fetching configurations."""
    tag_filter: str | None = None
    """Filter sources by tag on slave nodes. Only sources with this tag will be synced."""
    master_config: str | None = None
    """Master configuration YAML content as a string (used instead of loading from file)."""
    master_dispatch: bool = True
    """Whether to dispatch configuration updates from master to slaves."""
    # env_prefixes: list[str] = ["MUTUALIZED_"]
    env_prefixes: str = "MUTUALIZED_"
    """Environment variable prefixes to expose in templates (e.g., MUTUALIZED_, SCM_)."""
    private_ssh_key: str | None = None
    """Private SSH key for accessing git repositories."""
    http: bool = False
    """Whether to run in HTTP mode (disables HTTPS redirect). Defaults to False."""
    github_token: str | None = None
    """GitHub API token for accessing GitHub commit information."""
    github_secret: str | None = None
    """GitHub webhook secret for validating incoming webhook signatures."""
    route_prefix: str = "/scm"
    """Route prefix for the shared config manager API."""

    model_config = SettingsConfigDict(env_prefix="SCM__", env_nested_delimiter="__")

    @field_validator("api_base_url")
    @classmethod
    def validate_api_base_url(cls, value: str | None) -> str | None:
        if value is not None and not value.endswith("/"):
            value += "/"
        return value

    # @field_validator("env_prefixes", mode="before")
    # @classmethod
    # def validate_env_prefixes(cls, value: str | list[str] | None) -> list[str]:
    #     if value is None:
    #         return ["MUTUALIZED_"]
    #     if isinstance(value, str):
    #         # Parse colon-separated string
    #         return [v.strip() for v in value.split(":") if v.strip()]
    #     return value


settings = Settings()
