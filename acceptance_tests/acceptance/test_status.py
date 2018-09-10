from pprint import pprint


def test_all(app_connection):
    stats = app_connection.get_json('1/status/changeme')
    print(f'stats={pprint(stats)}')
    assert len(stats['slaves']) == 2
    assert stats['slaves']['api']['sources'] == stats['slaves']['slave']['sources']


def test_master(app_connection):
    stats = app_connection.get_json('1/status/master/changeme')
    print(f'stats={pprint(stats)}')
    assert len(stats['slaves']) == 2
    assert stats['slaves']['api'] == stats['slaves']['slave']


def test_other(app_connection):
    stats = app_connection.get_json('1/status/test_git/changeme')
    print(f'stats={pprint(stats)}')
    assert len(stats['slaves']) == 2
    assert stats['slaves']['api'] == stats['slaves']['slave']
    assert len(stats['slaves']['api']['template_engines']) == 1
    assert 'environment_variables' in stats['slaves']['api']['template_engines'][0]
    assert stats['slaves']['api']['template_engines'][0]['environment_variables']['TEST_ENV'] == '42'
