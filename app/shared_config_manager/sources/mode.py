import os

API_BASE_URL = None


def init(slave: bool) -> None:
    global API_BASE_URL
    if slave:
        API_BASE_URL = os.environ["API_BASE_URL"]
        if API_BASE_URL is not None and not API_BASE_URL.endswith('/'):
            API_BASE_URL += '/'


def is_master() -> bool:
    global API_BASE_URL
    return API_BASE_URL is None


def get_fetch_url(id_, key):
    return f"{API_BASE_URL}1/tarball/{id_}/{key}"
