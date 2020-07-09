import os
import pytest
import subprocess
import tempfile

from shared_config_manager import sources

TEMP_DIR = tempfile.gettempdir()


@pytest.yield_fixture()
def repo():
    repo_path = os.path.join(TEMP_DIR, "repo")
    subprocess.check_call(
        ["git", "config", "--global", "user.email", "you@example.com"], stderr=subprocess.STDOUT
    )
    subprocess.check_call(["git", "config", "--global", "user.name", "Your Name"], stderr=subprocess.STDOUT)
    subprocess.check_call(["git", "init", repo_path], stderr=subprocess.STDOUT)
    file_path = os.path.join(repo_path, "toto", "test")
    os.makedirs(os.path.dirname(file_path))
    with open(file_path, "w") as file:
        file.write("Hello world")
    subprocess.check_call(["git", "add", file_path], cwd=repo_path, stderr=subprocess.STDOUT)
    subprocess.check_call(
        ["git", "commit", "-a", "-m", "Initial commit"], cwd=repo_path, stderr=subprocess.STDOUT
    )

    yield repo_path

    subprocess.check_call(["rm", "-rf", repo_path], stderr=subprocess.STDOUT)


def test_git(repo):
    git = sources._create_source("test_git", {"type": "git", "key": "changeme", "repo": repo})
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
    subprocess.check_call(["git", "commit", "-a", "-m", "Initial commit"], cwd=repo, stderr=subprocess.STDOUT)

    git.refresh()
    try:
        assert os.path.isfile("/config/test_git/toto/test")
        with open("/config/test_git/toto/test") as file:
            assert file.read() == "Good bye"
    finally:
        git.delete()


def test_git_sub_dir(repo):
    git = sources._create_source(
        "test_git", {"type": "git", "key": "changeme", "repo": repo, "sub_dir": "toto"}
    )
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
    subprocess.check_call(["git", "commit", "-a", "-m", "Initial commit"], cwd=repo, stderr=subprocess.STDOUT)

    git.refresh()
    try:
        assert os.path.isfile("/config/test_git/test")
        with open("/config/test_git/test") as file:
            assert file.read() == "Good bye"
    finally:
        git.delete()


def test_git_sub_dir_no_sparse(repo):
    git = sources._create_source(
        "test_git", {"type": "git", "key": "changeme", "repo": repo, "sub_dir": "toto", "sparse": False}
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
    subprocess.check_call(["git", "commit", "-a", "-m", "Initial commit"], cwd=repo, stderr=subprocess.STDOUT)

    git.refresh()
    try:
        assert os.path.isfile("/config/test_git/test")
        with open("/config/test_git/test") as file:
            assert file.read() == "Good bye"
    finally:
        git.delete()


def test_git_with_key():
    git = sources._create_source(
        "test_key",
        {
            "type": "git",
            "repo": "git@github.com:camptocamp/private-geo-charts.git",
            "key": "changeme",
            "ssh_key": """\
-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA5D6HY+8e5wRMMh99TbWfAUC57vMtb0alhRvE0gqoi4gJ8Nmc
uAVciuoMd/bWoeMxoameZvr6+SuzD3eVLg3KcKjTUyQiQmcXdfYJ1UPWbXyTE/mE
GCK3dFWyHOnzBaJxPat7LqMboj9VKWYTQHaJcI1dKjgqWJ42WnUZrU4WYzFuclNQ
VeLYRimuF0gC9D3nx/EzSklYUaY6ZbSy6iyTAYv/p1JVm5rYNqhno+i+Dr+42cje
j7nIjN9u9J2AcBOYb/gR/nUDCeLnH4adTjVQ+F0yPU8vc7RuJh/V4ShwK9grliFL
EKwuBDLK1aSFLUc4iTbwVSV1YjtgX2zkTqqEbwIDAQABAoIBAHhdZUbVNmW7xXb1
Vj4h1m1xtdwGT+KLzgQJJd1ik4mpvxxNljERWsFDNjoZaQzMZEMN0SQbnTjDy9UP
ShOUYDrTPUZuGscL2LpzerIF6VGpzWJORlP4Euj9vEU1Nty00qUkBn0MtSj13zJK
y0JGgKpjUktOfT5oiN9hO55CPNonmwGubl0L8dpLcINr7+EeRg12GeAjgbXL/w67
N/brUn67+CVL/oXLrqGgb6YjUoZZty/LpoxF9s9BcOB3Z49H+ezhEmeruanacH2r
jUFyXgnWU1y8h2f4/6yciCeO2t991Y4laK/KOQgAw3Iq50FIyh1irsMCGb8b7K26
3cZzN9ECgYEA/jq56db4jp5llULkh1SuD6inOd9KBPKZn5ZNR/XdQ4aKByQhSgSV
d21d4beFC+9pERAB/ZPbpCUe9fZw5lp9hMkrMhJvLwO3Y7pvTnQ0I+Y0XBQGRZYc
Rn1kD6BpCiSV85uArYkThYn0P7BTCg6MKg5aEpkYNGhx97/Clg3hzXkCgYEA5dV5
D2uw9O//sHS2xkmSFlwDEfTKYVL+FI6LZ3jQoSyMGdmrZgxR3nY71wzVSZ/I7BYM
yQ8m++LlAuaSpKgeZ5Vi0P+Vjg8Sma6sfUtw7qQ/t0XXIW4/FgaFl7DNuIq7Kbhm
Y34q6hqD6JhuTn2FLHaEKBFrsoTfwfyTuY0jLycCgYEA2+MXYjXZDiHaYttUpeiM
FGcfHGMQtm7OiMWLWi5BjmITiFGrqUWFsaIajVwZ61TLX0KlNhpo4vRobv0UcWjb
H7qPbeOb3uIsAEoEc6r2XgaCSxHWyuEm26EgppNrxqYWPHnHNlFVXS8Q3vU3HX+v
o8B+D4/y64Fa8ZoeR4MCRqECgYB5YcjR8BpBAg+T7dAp4OkajfXBIftQczhlOvM8
7n2g4ZoMfP0cpB0I1IC+DrUGcTD4Hp0aArqgBTDV21hPRcrpAehyYMlngWZda/cF
JTa7kltkO6pmqYb/5unfNy0u7XXzjsPkf9nCUcagrQB0y63t0ZnyX2D1o19ZYD/U
m0mduQKBgQDzimNC4zuxs4dOx75nz070QTo4JrtYH8O7USqeHMi7YC4lc6qqG1s4
DutzRjGaeMLbvz82oGrKkI8phn0ACLHIYYE9BN93VN4CZNBue+lpAbXKw5Yq8VZI
9s4K9Ev2GhE19eObUJxyO/rJ62FKpFoqOctMc/aGPDK06Ldf4gldNg==
-----END RSA PRIVATE KEY-----
""",
        },
    )

    git.refresh()
    assert os.path.isfile("/config/test_key/README.md")
