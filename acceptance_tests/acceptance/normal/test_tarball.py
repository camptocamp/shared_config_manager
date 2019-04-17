import subprocess
import tempfile

from c2cwsgiutils.acceptance.connection import Connection


def test_ok(app_connection: Connection) -> None:
    r = app_connection.get_raw('1/tarball/test_git/changeme')
    assert r.headers['Content-Type'] == 'application/x-gtar'
    with tempfile.NamedTemporaryFile() as temp:
        temp.write(r.content)
        temp.flush()
        subprocess.check_call(['tar', '--test-label', '--verbose', '--file', temp.name])


def test_bad_key(app_connection):
    app_connection.get_json('1/tarball/test_git/bad', expected_status=403)


def test_bad_id(app_connection):
    app_connection.get_json('1/tarball/unknown/changeme', expected_status=404)
