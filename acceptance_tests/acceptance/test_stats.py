from pprint import pprint


def test_ok(app_connection):
    stats = app_connection.get_json('1/stats')
    print(f'stats={pprint(stats)}')
    assert len(stats['slaves']) == 2
    assert stats['slaves']['api']['sources'] == stats['slaves']['slave']['sources']
