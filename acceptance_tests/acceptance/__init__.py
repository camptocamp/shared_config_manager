import subprocess

from c2cwsgiutils.acceptance import utils


def wait_sync(app_connection, name, hash_):
    def what():
        status = app_connection.get_json("1/status/changeme")
        for _, slave in status["slaves"].items():
            if hash_ is None:
                if name in slave["sources"]:
                    raise RuntimeError(f"{name} still found in sources")
                print("Name '{}' still found in sources".format(name))
            else:
                if name not in slave["sources"]:
                    raise RuntimeError(f"{name} not in {slave['sources'].keys()}")
                if "hash" not in slave["sources"][name]:
                    raise RuntimeError(f"{name}, {slave['sources'][name]}")
                if slave["sources"][name]["hash"] != hash_:
                    raise RuntimeError(f"Wrong hash for {name}: {slave['sources'][name]['hash']} != {hash_}")
                print("Name '{}' and hash found in sources".format(name))
        return True

    utils.retry_timeout(what, interval=1)


def get_hash(cwd):
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=cwd).decode("utf-8").strip()
