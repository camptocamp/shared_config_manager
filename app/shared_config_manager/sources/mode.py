from shared_config_manager import config

_SLAVE = None


def init(slave: bool) -> None:
    """Initialize the mode."""
    global _SLAVE  # noqa: PLW0603
    _SLAVE = slave


def is_master() -> bool:
    """Is the master."""
    return not _SLAVE or config.settings.api_base_url is None


def is_master_with_slaves() -> bool:
    """Is the master with slaves."""
    return is_master() and config.settings.api_master


def get_fetch_url(id_: str) -> str:
    """Get the URL to fetch the tarball."""
    return f"{config.settings.api_base_url}1/tarball/{id_}"
