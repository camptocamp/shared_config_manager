import os
import pytest
import subprocess
import tempfile

from shared_config_manager import sources

TEMP_DIR = tempfile.gettempdir()


@pytest.yield_fixture()
def repo():
    repo_path = os.path.join(TEMP_DIR, 'repo')
    subprocess.check_call(['git', 'config', '--global', 'user.email', 'you@example.com'],
                          stderr=subprocess.STDOUT)
    subprocess.check_call(['git', 'config', '--global', 'user.name', 'Your Name'],
                          stderr=subprocess.STDOUT)
    subprocess.check_call(['git', 'init', repo_path], stderr=subprocess.STDOUT)
    file_path = os.path.join(repo_path, 'test')
    with open(file_path, 'w') as file:
        file.write('Hello world')
    subprocess.check_call(['git', 'add', file_path], cwd=repo_path, stderr=subprocess.STDOUT)
    subprocess.check_call(['git', 'commit', '-a', '-m', 'Initial commit'], cwd=repo_path,
                          stderr=subprocess.STDOUT)

    yield repo_path

    subprocess.check_call(['rm', '-rf', repo_path], stderr=subprocess.STDOUT)


def test_git(repo):
    git = sources._create_source('test_git', {
        'type': 'git',
        'key': 'changeme',
        'repo': repo
    })

    git.refresh()
    assert os.path.isfile('/config/test_git/test')
    with open('/config/test_git/test') as file:
        assert file.read() == 'Hello world'

    repo_file_path = os.path.join(repo, 'test')
    with open(repo_file_path, 'w') as file:
        file.write('Good bye')
    subprocess.check_call(['git', 'add', repo_file_path], cwd=repo, stderr=subprocess.STDOUT)
    subprocess.check_call(['git', 'commit', '-a', '-m', 'Initial commit'],
                          cwd=repo, stderr=subprocess.STDOUT)

    git.refresh()
    try:
        assert os.path.isfile('/config/test_git/test')
        with open('/config/test_git/test') as file:
            assert file.read() == 'Good bye'
    finally:
        git.delete()


def test_git_with_key():
    git = sources._create_source('test_key', {
        'type': 'git',
        'repo': 'git@github.com:camptocamp/private-geo-charts.git',
        'key': 'changeme',
        'ssh_key': """\
-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEAqHmkARUeQJEtAJTEUx0AHhUmU2bl3EeWQA0fCbSB6wURTZQE
P64O3uH+uA662mw0k/GFQl2FzgJN0WUherpQyAqTahk+iqfxkP69g092OJZPqcwd
8mGxBtGB1iYIFk2VGZIu6mr0ij1n99qm59sVUG2V/q7uY+z2jQBL940MeHZ6PSQ+
 C3eb+3d9+pfweNkndog0Pam/Y8CObof7JkeV1SXnm2++3qQPd3RkFBSbExeOKWq6
L5wj2v5De5u1VgO5QOn+GFnYUJsZqGsrrG9dG5lREM+H9v+fpuJ1d2CryuXycYSA
+Nxh8mtXY6QJrHFTF9sYBckRlEGIpW5b93QvHQIDAQABAoIBAEEFOSuFx/gpT1Hz
GFXvUlVJ2lHD26CJLE6qAbmQJbfba9Mh9gXRmkGgvNqyLKERs7UJOGHlkDdyoi/X
NPWVpImfs0b2WTHQISXReriL2Vd7g2FHuqMJ2vWDs/U/Fk3tQUbuKRclkh0sF80L
YPEIl5BDyujRAIYmNP00CR2QHSj8CFfIxNndwAyaKCsG/FT4s1P9dKclOmwPmNSe
jSPGMSsSjp77GcnBT3nq0ZNkPf+bkp2jLCC+uUVZdwzOpqJIyQqxw3ao8th0HjYf
JzTrJ042EfPkIlLSonKic1YcRG4IvKS5g55DXWtnDWXW/gqXx5+5Tt4gR1X8RDXb
OciFwWECgYEA1F0tG53H/Y4JOo/CugnCl1yssv6MYJyruM03pxxj/GI4qhuGx0T3
6sa1y8iy28Je69SarTaw7bdLHWF+UvbFbpc4FrSKGiXY2g9JoDHwLoJofP3uLaG/
f5ngYK3qhVwgY3pFDskNGzY62xCT1ikubnv3tZCv0qRf8vkozuytD4UCgYEAyxfQ
YigGTJeyDG0O2alta+j7xoLbujN9w4+wSAgIkslQwbhJ9nKp5N9xCjfzXBENTqp2
QZWHQ0GKUK4NRtUaPwIgnCIW1yR74Lz6LfI1dKUPLuxy00N/fg4xgAmazeXg3oPh
/ey8SB0tgxD/Ql1whJpCZeoe2TG8IjJn6BOJmLkCgYEAo/m+VtCiF9qQrbNLvLLE
mnNotl1urzrKLcvn6RU27y44asEOdNeARrxgq5Ww5ZdUC+0B8jWEsEkTqwAYtp7t
G9OP75g/+qi2pMmhJBzrRD5VyA2a14lJgJGke4JOz+Ku76D9qcj8YcKh93z5aigq
Pg1i28N4v8FEhSx2ojCGALECgYEAvqdtbSfrue1SLQ4YOccuvHWsHg/sW+FIt9Rl
BUndWob4c9MgQ+YijYQg5xndMFmlp2qotyq7Hy0gvlqWhh85k1rY6BmsXW2XiUN+
jLFq80Sce01nAeLEhb6nQ25Az/d0YQ9nkOuzWPNjLT5AkrmLDkCOAoSFTxm8ZlHx
b1EgA6kCgYAjXUPJmG7fEmombN+3IoQoahOnr74R3JuvFJAFtry86EkTUkjctdGF
5iTh+IcbiNVj/fSjtMg3sEi8UstRw4GSVwMspkY4Z2k5zbZPmRBik7RyXyxzMunc
23mcb1FD8H5eiDmWXHAG1Zq3OYaydThdHYfVtiX9dtD6VUM7vYLjIQ==
-----END RSA PRIVATE KEY-----
"""
    })

    git.refresh()
    assert os.path.isfile('/config/test_key/README.md')
