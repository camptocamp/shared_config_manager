from c2cwsgiutils import services
import logging
from pyramid.httpexceptions import HTTPServerError
from pyramid.response import Response
import subprocess

from . import sources, slave_status

refresh_service = services.create('refresh', '/1/refresh/{id}/{key}')
refresh_all_service = services.create('refresh_all', '/1/refresh/{key}')
stats_service = services.create('stats', '/1/status/{key}')
source_stats_service = services.create('service_stats', '/1/status/{id}/{key}')
tarball_service = services.create('tarball', '/1/tarball/{id}/{key}')
LOG = logging.getLogger(__name__)


@refresh_service.get()
def refresh(request):
    sources.check_id_key(id_=request.matchdict['id'], key=request.matchdict['key'])
    return _refresh(request)


@refresh_service.post()
def refresh_webhook(request):
    id_ = request.matchdict['id']
    source, filtered = sources.check_id_key(id_=id_, key=request.matchdict['key'])

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


@refresh_all_service.get()
def refresh_all(request):
    key = request.matchdict['key']
    sources.master_source.validate_key(key)
    nb_refresh = 0
    for id_ in sources.get_sources().keys():
        sources.refresh(id_=id_, key=key)
        nb_refresh += 1
    return {'status': 200, 'nb_refresh': nb_refresh}


@refresh_all_service.post()
def refresh_all_webhook(request):
    key = request.matchdict['key']
    sources.master_source.validate_key(key)

    if request.headers.get('X-GitHub-Event') != 'push':
        LOG.info("Ignoring webhook notif for a non-push event on %s")
        return {'status': 200, 'ignored': True, 'reason': 'Not a push'}

    ref = request.json.get('ref')
    if ref is None:
        raise HTTPServerError("Webhook is missing the ref")

    nb_refresh = 0
    for id_, source in sources.get_sources().items():
        if source.get_type() != 'git':
            continue

        if ref != 'refs/heads/' + source.get_branch():
            LOG.info("Ignoring webhook notif for non-matching branch %s on %s", source.get_branch(), id_)
            continue
        sources.refresh(id_=id_, key=key)
        nb_refresh += 1

    return {'status': 200, 'nb_refresh': nb_refresh}


@stats_service.get()
def stats(request):
    sources.master_source.validate_key(request.matchdict['key'])
    slaves = slave_status.get_slaves_status()
    slaves = {slave['hostname']: _cleanup_slave_status(slave) for slave in slaves if slave is not None}
    return {
        'slaves': slaves
    }


@source_stats_service.get()
def source_stats(request):
    id_ = request.matchdict['id']
    sources.check_id_key(id_=id_, key=request.matchdict['key'])
    slaves = slave_status.get_source_status(id_=id_)
    statuses = []
    for slave in slaves:
        if slave is None or slave.get('filtered', False):
            continue
        status = _cleanup_slave_status(slave)
        if status not in statuses:
            statuses.append(status)

    return {
        'statuses': statuses
    }


def _cleanup_slave_status(status):
    result = dict(status)
    result.pop('hostname', None)
    result.pop('pid', None)
    return result


@tarball_service.get()
def tarball(request):
    source, filtered = sources.check_id_key(id_=request.matchdict['id'], key=request.matchdict['key'])
    assert not filtered
    path = source.get_path()

    response: Response = request.response
    proc = subprocess.Popen(['tar', '--create', '--gzip', '.'], cwd=path, bufsize=4096,
                            stdout=subprocess.PIPE)
    response.content_type = 'application/x-gtar'
    response.app_iter = _proc_iter(proc)
    return response


def _proc_iter(proc: subprocess.Popen):
    while True:
        block = proc.stdout.read(4096)
        if not block:
            break
        yield block
    if proc.wait() != 0:
        raise HTTPServerError("Error building the tarball")
