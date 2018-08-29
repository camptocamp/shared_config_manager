import os
import pytest
import subprocess


@pytest.yield_fixture()
def git_source(app_connection, test_repos):
    with open(os.path.join(test_repos, 'master', 'shared_config_manager.yaml'), 'a') as config:
        config.write("""\
  other:
    type: git
    repo: /repos/other
    key: changeme
""")

    subprocess.check_call(f"""
    set -e
    cd {test_repos}

    cd master
    git commit -a -m "Added other"
    cd ..

    git init other
    cd other
    echo -n "content1" > config.txt
    git add config.txt
    git commit -a -m "Initial commit"
    """, shell=True)

    app_connection.get_json('1/refresh/master/changeme')

    yield os.path.join(test_repos, 'other')

    subprocess.check_call(f"""
    set -e
    cd {test_repos}
    rm -rf other

    cd master
    git reset --hard HEAD~1
    """, shell=True)

    app_connection.get_json('1/refresh/master/changeme')

    for slave in ('api', 'slave'):
        assert not os.path.exists(os.path.join('/tmp/slaves', slave, 'other'))


def test_workflow(app_connection, git_source):
    subprocess.check_call("ls -R /tmp/slaves", shell=True)
    for slave in ('api', 'slave'):
        with open(os.path.join('/tmp/slaves', slave, 'other', 'config.txt')) as config:
            assert config.read() == 'content1'

    subprocess.check_call(f"""
    set -e
    cd {git_source}
    echo -n "content2" > config.txt
    git commit -a -m "Second commit"
    """, shell=True)

    app_connection.get_json('1/refresh/other/changeme')

    for slave in ('api', 'slave'):
        with open(os.path.join('/tmp/slaves', slave, 'other', 'config.txt')) as config:
            assert config.read() == 'content2'
