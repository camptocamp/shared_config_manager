import subprocess

from c2cwsgiutils.acceptance import utils


def wait_sync(app_connection, name, hash_) -> None:
    """Wait for the sync to be done."""

    def what() -> bool:
        status = app_connection.get_json("1/status", headers={"X-Scm-Secret": "changeme"})
        for slave_name, slave in status["slaves"].items():
            if slave_name == "api_test_user":
                continue
            if hash_ is None:
                if name in slave["sources"]:
                    message = f"{name} still found in sources"
                    print(message)
                    raise RuntimeError(message)
                print(f"Name '{name}' still found in sources")
            else:
                if name not in slave["sources"]:
                    message = f"In slave {slave_name}, {name} not in {slave['sources'].keys()}"
                    print(message)
                    raise RuntimeError(message)
                if "hash" not in slave["sources"][name]:
                    message = f"No hash in slave {slave_name}, source {name}"
                    print(message)
                    raise RuntimeError(message)
                if slave["sources"][name]["hash"] != hash_:
                    print(
                        f"Wrong hash for slave {slave_name}, source {name}: "
                        f"{slave['sources'][name]['hash']} != {hash_}",
                    )
                    message = (
                        f"Wrong hash for slave {slave_name}, source {name}: "
                        f"{slave['sources'][name]['hash']} != {hash_}"
                    )
                    raise RuntimeError(message)
                print(f"Name '{name}' and hash found in sources")
        return True

    utils.retry_timeout(what, timeout=10, interval=1)


def get_hash(cwd: str) -> str:
    """Get the hash of the current git repository."""
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=cwd).decode("utf-8").strip()
