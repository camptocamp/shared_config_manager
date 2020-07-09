import subprocess

from c2cwsgiutils.acceptance import utils

BASE_URL = "http://" + utils.DOCKER_GATEWAY + ":8080/scm/"
PROJECT_NAME = "scm"


def wait_sync(app_connection, name, hash_):
    def what():
        status = app_connection.get_json("1/status/changeme")
        for _, slave in status["slaves"].items():
            if hash_ is None:
                if name in slave["sources"]:
                    raise RuntimeError(f"{name} still found in sources")
            else:
                if slave["sources"][name]["hash"] != hash_:
                    raise RuntimeError(f"wrong hash for {name}: {slave['sources'][name]['hash']} != {hash_}")
        return True

    utils.retry_timeout(what, interval=1)


def get_hash(dir):
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=dir).decode("utf-8").strip()
