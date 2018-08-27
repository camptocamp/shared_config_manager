from c2cwsgiutils import services
import logging

from . import sources, slave_stats

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


# TODO: support github webhook


@stats_service.get()
def stats(request):
    slaves = slave_stats.get_slave_stats()
    slaves = {slave['hostname']: slave for slave in slaves}
    return {
        'slaves': slaves,
        'nb_heads': len(slaves)
    }
