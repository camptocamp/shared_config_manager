from c2cwsgiutils import services
import logging
from pyramid.httpexceptions import HTTPServerError

from . import sources, slave_stats

refresh_service = services.create('refresh', '/1/refresh/{id}/{key}')
stats_service = services.create('stats', '/1/stats')
LOG = logging.getLogger(__name__)


@refresh_service.get()
def refresh(request):
    sources.check_id_key(id_=request.matchdict['id'], key=request.matchdict['key'])
    return _refresh(request)


@refresh_service.post()
def refresh_webhook(request):
    id_ = request.matchdict['id']
    source = sources.check_id_key(id_=id_, key=request.matchdict['key'])

    if source.get_type() != 'git':
        raise HTTPServerError("Non GIT source %s cannot be refreshed by a webhook", id_)

    if request.headers.get('X-GitHub-Event') != 'push':
        LOG.info("Ignoring webhook notif for a non-push event", source.get_branch(), id_)
        return {'status': 200, 'nb_completed': 0}

    ref = request.json.get('ref')
    if ref is None:
        raise HTTPServerError("Webhook for %s is missing the ref", id_)
    if ref != 'refs/heads/' + source.get_branch():
        LOG.info("Ignoring webhook notif for non-matching branch %s on %s", source.get_branch(), id_)
        return {'status': 200, 'nb_completed': 0}

    return _refresh(request)


def _refresh(request):
    answers = sources.refresh(id_=request.matchdict['id'], key=request.matchdict['key'])
    errors = list(filter(lambda i: i is not True, answers))
    if len(errors) > 0:
        request.response.status_code = 500
        return {'status': 500, 'errors': errors, 'nb_completed': len(answers) - len(errors)}
    else:
        return {'status': 200, 'nb_completed': len(answers) - len(errors)}


@stats_service.get()
def stats(request):
    slaves = slave_stats.get_slave_stats()
    slaves = {slave['hostname']: slave for slave in slaves}
    return {
        'slaves': slaves
    }
