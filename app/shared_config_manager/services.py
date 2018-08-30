from c2cwsgiutils import services
import logging
from pyramid.httpexceptions import HTTPServerError

from . import sources, slave_stats

refresh_service = services.create('refresh', '/1/refresh/{id}/{key}')
stats_service = services.create('stats', '/1/status')
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
        LOG.info("Ignoring webhook notif for a non-push event on %s")
        return {'status': 200, 'ignored': True, 'reason': 'Not a push'}

    ref = request.json.get('ref')
    if ref is None:
        raise HTTPServerError("Webhook for %s is missing the ref", id_)
    if ref != 'refs/heads/' + source.get_branch():
        LOG.info("Ignoring webhook notif for non-matching branch %s on %s", source.get_branch(), id_)
        return {'status': 200, 'ignored': True, 'reason': f'Not {source.get_branch()} branch'}

    return _refresh(request)


def _refresh(request):
    sources.refresh(id_=request.matchdict['id'], key=request.matchdict['key'])
    return {'status': 200}


@stats_service.get()
def stats(request):
    slaves = slave_stats.get_slave_stats()
    slaves = {slave['hostname']: _cleanup_slave_status(slave) for slave in slaves if slave is not None}
    return {
        'slaves': slaves
    }


def _cleanup_slave_status(status):
    result = dict(status)
    result.pop('hostname', None)
    result.pop('pid', None)
    return result
