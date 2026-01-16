import os
import subprocess
import tempfile
from pathlib import Path

import pytest

from shared_config_manager.sources import base, registry

TEMP_DIR = tempfile.gettempdir()


@pytest.fixture
def repo():
    repo_path = Path(TEMP_DIR) / "repo"
    subprocess.check_call(
        ["git", "config", "--global", "user.email", "you@example.com"],
        stderr=subprocess.STDOUT,
    )
    subprocess.check_call(
        ["git", "config", "--global", "user.name", "Your Name"],
        stderr=subprocess.STDOUT,
    )
    subprocess.check_call(["git", "init", repo_path], stderr=subprocess.STDOUT)
    file_path = Path(repo_path) / "toto" / "test"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w") as file:
        file.write("Hello world")
    subprocess.check_call(["git", "add", file_path], cwd=repo_path, stderr=subprocess.STDOUT)
    subprocess.check_call(
        ["git", "commit", "-a", "-m", "Initial commit"],
        cwd=repo_path,
        stderr=subprocess.STDOUT,
    )

    yield repo_path

    subprocess.check_call(["rm", "-rf", repo_path], stderr=subprocess.STDOUT)


@pytest.mark.asyncio
async def test_git(repo: Path) -> None:
    await base.init()
    git = registry._create_source("test_git", {"type": "git", "repo": str(repo)})
    assert not git._do_sparse()
    await git.refresh()
    subprocess.check_call(["ls", "/config/test_git"])
    assert Path("/config/test_git/toto/test").is_file()
    assert not Path("/config/test_git/.git").is_file()
    with Path("/config/test_git/toto/test").open() as file:
        assert file.read() == "Hello world"

    repo_file_path = Path(repo) / "toto" / "test"
    with repo_file_path.open("w") as file:
        file.write("Good bye")
    subprocess.check_call(["git", "add", repo_file_path], cwd=repo, stderr=subprocess.STDOUT)
    subprocess.check_call(
        ["git", "commit", "-a", "-m", "Initial commit"],
        cwd=repo,
        stderr=subprocess.STDOUT,
    )

    await git.refresh()
    try:
        assert Path("/config/test_git/toto/test").is_file()
        with Path("/config/test_git/toto/test").open() as file:
            assert file.read() == "Good bye"
    finally:
        git.delete()


@pytest.mark.asyncio
async def test_git_sub_dir(repo) -> None:
    await base.init()
    git = registry._create_source("test_git", {"type": "git", "repo": repo, "sub_dir": "toto"})
    assert git._do_sparse()
    await git.refresh()
    subprocess.check_call(["ls", "/config/test_git"])
    assert Path("/config/test_git/test").is_file()
    assert not Path("/config/test_git/.git").is_file()
    with Path("/config/test_git/test").open() as file:
        assert file.read() == "Hello world"

    repo_file_path = Path(repo) / "toto" / "test"
    with repo_file_path.open("w") as file:
        file.write("Good bye")
    subprocess.check_call(["git", "add", repo_file_path], cwd=repo, stderr=subprocess.STDOUT)
    subprocess.check_call(
        ["git", "commit", "-a", "-m", "Initial commit"],
        cwd=repo,
        stderr=subprocess.STDOUT,
    )

    await git.refresh()
    try:
        assert Path("/config/test_git/test").is_file()
        with Path("/config/test_git/test").open() as file:
            assert file.read() == "Good bye"
    finally:
        git.delete()


@pytest.mark.asyncio
async def test_git_sub_dir_no_sparse(repo) -> None:
    await base.init()
    git = registry._create_source(
        "test_git",
        {"type": "git", "repo": str(repo), "sub_dir": "toto", "sparse": False},
    )
    assert not git._do_sparse()
    await git.refresh()
    subprocess.check_call(["ls", "/config/test_git"])
    assert Path("/config/test_git/test").is_file()
    assert not Path("/config/test_git/.git").is_file()
    with Path("/config/test_git/test").open() as file:
        assert file.read() == "Hello world"

    repo_file_path = Path(repo) / "toto" / "test"
    with repo_file_path.open("w") as file:
        file.write("Good bye")
    subprocess.check_call(["git", "add", repo_file_path], cwd=repo, stderr=subprocess.STDOUT)
    subprocess.check_call(
        ["git", "commit", "-a", "-m", "Initial commit"],
        cwd=repo,
        stderr=subprocess.STDOUT,
    )

    await git.refresh()
    try:
        assert Path("/config/test_git/test").is_file()
        with Path("/config/test_git/test").open() as file:
            assert file.read() == "Good bye"
    finally:
        git.delete()


@pytest.mark.skipif(os.environ.get("PRIVATE_SSH_KEY") is not None, reason="We needs to have the key")
@pytest.mark.asyncio
async def test_git_with_key() -> None:
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

    await git.refresh()
    assert Path("/config/test_key/README.md").is_file()
