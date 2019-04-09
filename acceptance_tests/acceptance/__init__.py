import subprocess

from c2cwsgiutils.acceptance import utils

BASE_URL = 'http://' + utils.DOCKER_GATEWAY + ':8080/scm/'
PROJECT_NAME = 'scm'


def wait_sync(app_connection, name, hash):
    def what():
        status = app_connection.get_json('1/status/changeme')
        for _, slave in status['slaves'].items():
            if hash is None:
                if name in slave['sources']:
                    return False
            else:
                if slave['sources'][name]['hash'] != hash:
                    return False
        return True

    utils.retry_timeout(what)


def get_hash(dir):
    return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=dir). \
        decode("utf-8").strip()
