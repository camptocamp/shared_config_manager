import os
import subprocess
import tempfile

import pytest

from shared_config_manager.sources import registry

TEMP_DIR = tempfile.gettempdir()


@pytest.fixture
def repo():
    repo_path = os.path.join(TEMP_DIR, "repo")
    subprocess.check_call(
        ["git", "config", "--global", "user.email", "you@example.com"],
        stderr=subprocess.STDOUT,
    )
    subprocess.check_call(
        ["git", "config", "--global", "user.name", "Your Name"],
        stderr=subprocess.STDOUT,
    )
    subprocess.check_call(["git", "init", repo_path], stderr=subprocess.STDOUT)
    file_path = os.path.join(repo_path, "toto", "test")
    os.makedirs(os.path.dirname(file_path))
    with open(file_path, "w") as file:
        file.write("Hello world")
    subprocess.check_call(["git", "add", file_path], cwd=repo_path, stderr=subprocess.STDOUT)
    subprocess.check_call(
        ["git", "commit", "-a", "-m", "Initial commit"],
        cwd=repo_path,
        stderr=subprocess.STDOUT,
    )

    yield repo_path

    subprocess.check_call(["rm", "-rf", repo_path], stderr=subprocess.STDOUT)


def test_git(repo) -> None:
    git = registry._create_source("test_git", {"type": "git", "repo": repo})
    assert not git._do_sparse()
    git.refresh()
    subprocess.check_call(["ls", "/config/test_git"])
    assert os.path.isfile("/config/test_git/toto/test")
    assert not os.path.isfile("/config/test_git/.git")
    with open("/config/test_git/toto/test") as file:
        assert file.read() == "Hello world"

    repo_file_path = os.path.join(repo, "toto", "test")
    with open(repo_file_path, "w") as file:
        file.write("Good bye")
    subprocess.check_call(["git", "add", repo_file_path], cwd=repo, stderr=subprocess.STDOUT)
    subprocess.check_call(
        ["git", "commit", "-a", "-m", "Initial commit"],
        cwd=repo,
        stderr=subprocess.STDOUT,
    )

    git.refresh()
    try:
        assert os.path.isfile("/config/test_git/toto/test")
        with open("/config/test_git/toto/test") as file:
            assert file.read() == "Good bye"
    finally:
        git.delete()


def test_git_sub_dir(repo) -> None:
    git = registry._create_source("test_git", {"type": "git", "repo": repo, "sub_dir": "toto"})
    assert git._do_sparse()
    git.refresh()
    subprocess.check_call(["ls", "/config/test_git"])
    assert os.path.isfile("/config/test_git/test")
    assert not os.path.isfile("/config/test_git/.git")
    with open("/config/test_git/test") as file:
        assert file.read() == "Hello world"

    repo_file_path = os.path.join(repo, "toto", "test")
    with open(repo_file_path, "w") as file:
        file.write("Good bye")
    subprocess.check_call(["git", "add", repo_file_path], cwd=repo, stderr=subprocess.STDOUT)
    subprocess.check_call(
        ["git", "commit", "-a", "-m", "Initial commit"],
        cwd=repo,
        stderr=subprocess.STDOUT,
    )

    git.refresh()
    try:
        assert os.path.isfile("/config/test_git/test")
        with open("/config/test_git/test") as file:
            assert file.read() == "Good bye"
    finally:
        git.delete()


def test_git_sub_dir_no_sparse(repo) -> None:
    git = registry._create_source(
        "test_git",
        {"type": "git", "repo": repo, "sub_dir": "toto", "sparse": False},
    )
    assert not git._do_sparse()
    git.refresh()
    subprocess.check_call(["ls", "/config/test_git"])
    assert os.path.isfile("/config/test_git/test")
    assert not os.path.isfile("/config/test_git/.git")
    with open("/config/test_git/test") as file:
        assert file.read() == "Hello world"

    repo_file_path = os.path.join(repo, "toto", "test")
    with open(repo_file_path, "w") as file:
        file.write("Good bye")
    subprocess.check_call(["git", "add", repo_file_path], cwd=repo, stderr=subprocess.STDOUT)
    subprocess.check_call(
        ["git", "commit", "-a", "-m", "Initial commit"],
        cwd=repo,
        stderr=subprocess.STDOUT,
    )

    git.refresh()
    try:
        assert os.path.isfile("/config/test_git/test")
        with open("/config/test_git/test") as file:
            assert file.read() == "Good bye"
    finally:
        git.delete()


@pytest.mark.skipif(os.environ.get("PRIVATE_SSH_KEY") is not None, reason="We needs to have the key")
def test_git_with_key() -> None:
    ssh_key = os.environ["PRIVATE_SSH_KEY"].split(" ")
    ssh_key = ["-----BEGIN RSA PRIVATE KEY-----"]
    ssh_key += os.environ["PRIVATE_SSH_KEY"].split(" ")[4:-4]
    ssh_key += ["-----END RSA PRIVATE KEY-----"]
    ssh_key = [k for k in ssh_key if k != ""]

    git = registry._create_source(
        "test_key",
        {
            "type": "git",
            "repo": "git@github.com:camptocamp/private-geo-charts.git",
            "ssh_key": "\n".join(ssh_key),
        },
    )

    git.refresh()
    assert os.path.isfile("/config/test_key/README.md")
