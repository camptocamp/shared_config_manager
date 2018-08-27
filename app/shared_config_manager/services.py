from c2cwsgiutils import services, broadcast
import logging

from . import sources

refresh_service = services.create('refresh', '/1/refresh/{id}/{key}')
stats_service = services.create('stats', '/1/stats')
LOG = logging.getLogger(__name__)


@refresh_service.get()
def refresh(request):
    params = dict(id_=request.matchdict['id'], key=request.matchdict['key'])
    sources.check_id_key(**params)

    answers = sources.refresh(**params)

    errors = list(filter(lambda i: i is not True, answers))
    if len(errors) > 0:
        request.response.status_code = 500
        return {
            'status': 500,
            'errors': errors,
            'nb_completed': len(answers) - len(errors)
        }
    else:
        return {
            'status': 200,
            'nb_completed': len(answers) - len(errors)
        }


@stats_service.get()
def stats(request):
    slaves = _get_slave_stats()
    slaves = {slave['hostname']: slave for slave in slaves}
    return {
        'slaves': slaves,
        'nb_heads': len(slaves)
    }


@broadcast.decorator(expect_answers=True)
def _get_slave_stats():
    return {'sources': sources.get_stats()}
