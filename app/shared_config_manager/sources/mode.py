import os

API_BASE_URL = None


def init(slave: bool) -> None:
    """Initialize the mode."""
    global API_BASE_URL  # pylint: disable=global-statement
    if slave:
        API_BASE_URL = os.environ["API_BASE_URL"]
        if API_BASE_URL is not None and not API_BASE_URL.endswith("/"):
            API_BASE_URL += "/"


def is_master() -> bool:
    """Is the master."""
    return API_BASE_URL is None


def is_master_with_slaves() -> bool:
    """Is the master with slaves."""
    return is_master() and os.environ.get("API_MASTER") is not None


def get_fetch_url(id_: str) -> str:
    """Get the URL to fetch the tarball."""
    return f"{API_BASE_URL}1/tarball/{id_}"
