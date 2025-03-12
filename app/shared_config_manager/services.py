import logging
import os.path
import re
import subprocess  # nosec
from collections.abc import Iterable
from typing import Any, cast

import pyramid.request
import pyramid.response
from c2cwsgiutils import services
from pyramid.httpexceptions import HTTPNotFound, HTTPServerError

from shared_config_manager import slave_status
from shared_config_manager.configuration import BroadcastObject, SourceStatus
from shared_config_manager.sources import git, registry

_refresh_service = services.create("refresh", "/1/refresh/{id}")
_refresh_all_service = services.create("refresh_all", "/1/refresh")
_status_service = services.create("stats", "/1/status")
_source_stats_service = services.create("service_stats", "/1/status/{id}")
_tarball_service = services.create("tarball", "/1/tarball/{id}")


_LOG = logging.getLogger(__name__)
__BRANCH_NAME_SANITIZER = re.compile(r"[^0-9a-zA-z-_]")


@_refresh_service.get()  # type: ignore
def _refresh_view(request: pyramid.request.Request) -> dict[str, Any]:
    id_ = request.matchdict["id"]
    source, _ = registry.get_source_check_auth(id_=id_, request=request)
    if source is None:
        raise HTTPNotFound(f"Unknown id {id_}")
    return _refresh(request)


@_refresh_service.post()  # type: ignore
def _refresh_webhook(request: pyramid.request.Request) -> dict[str, Any]:
    id_ = request.matchdict["id"]
    source, _ = registry.get_source_check_auth(id_=id_, request=request)
    if source is None:
        raise HTTPNotFound(f"Unknown id {id_}")

    if source.get_type() != "git":
        raise HTTPServerError(f"Non GIT source {id_} cannot be refreshed by a webhook")

    source_git = cast(git.GitSource, source)

    if request.headers.get("X-GitHub-Event") != "push":
        _LOG.info("Ignoring webhook notif for a non-push event on %s", id_)
        return {"status": 200, "ignored": True, "reason": "Not a push"}

    ref = request.json.get("ref")
    if ref is None:
        raise HTTPServerError(f"Webhook for {id_} is missing the ref")
    if ref != "refs/heads/" + source_git.get_branch():
        _LOG.info(
            "Ignoring webhook notif for non-matching branch %s on %s",
            source_git.get_branch(),
            id_,
        )
        branch = __BRANCH_NAME_SANITIZER.sub("", source_git.get_branch())
        return {"status": 200, "ignored": True, "reason": f"Not {branch} branch"}

    return _refresh(request)


def _refresh(request: pyramid.request.Request) -> dict[str, Any]:
    registry.refresh(id_=request.matchdict["id"], request=request)
    return {"status": 200}


@_refresh_all_service.get()  # type: ignore
def _refresh_all(request: pyramid.request.Request) -> dict[str, Any]:
    if not registry.MASTER_SOURCE:
        raise HTTPServerError("Master source not initialized")
    registry.MASTER_SOURCE.validate_auth(request)
    nb_refresh = 0
    for id_ in registry.get_sources():
        registry.refresh(id_=id_, request=request)
        nb_refresh += 1
    return {"status": 200, "nb_refresh": nb_refresh}


@_refresh_all_service.post()  # type: ignore
def _refresh_all_webhook(request: pyramid.request.Request) -> dict[str, Any]:
    if not registry.MASTER_SOURCE:
        raise HTTPServerError("Master source not initialized")
    registry.MASTER_SOURCE.validate_auth(request=request)

    if request.headers.get("X-GitHub-Event") != "push":
        _LOG.info("Ignoring webhook notif for a non-push event on %s")
        return {"status": 200, "ignored": True, "reason": "Not a push"}

    ref = request.json.get("ref")
    if ref is None:
        raise HTTPServerError("Webhook is missing the ref")

    nb_refresh = 0
    for id_, source in registry.get_sources().items():
        if not source or source.get_type() != "git":
            continue

        source_git = cast(git.GitSource, source)

        if ref != "refs/heads/" + source_git.get_branch():
            _LOG.info(
                "Ignoring webhook notif for non-matching branch %s!=refs/heads/%s on %s",
                ref,
                source_git.get_branch(),
                id_,
            )
            continue
        registry.refresh(id_=id_, request=request)
        nb_refresh += 1

    return {"status": 200, "nb_refresh": nb_refresh}


@_status_service.get()  # type: ignore
def _stats(request: pyramid.request.Request) -> dict[str, Any]:
    if not registry.MASTER_SOURCE:
        return {"slaves": {}}
    registry.MASTER_SOURCE.validate_auth(request=request)
    slaves_status = slave_status.get_slaves_status()
    assert slaves_status is not None
    slaves = {slave["hostname"]: _cleanup_slave_status(slave) for slave in slaves_status if slave is not None}
    return {"slaves": slaves}


@_source_stats_service.get()  # type: ignore
def _source_stats(request: pyramid.request.Request) -> dict[str, Any]:
    id_ = request.matchdict["id"]
    source, _ = registry.get_source_check_auth(id_=id_, request=request)
    if source is None:
        raise HTTPNotFound(f"Unknown id {id_}")
    slaves: list[SourceStatus] | None = slave_status.get_source_status(id_=id_)
    assert slaves is not None
    statuses: list[SourceStatus] = []
    for slave in slaves:
        if slave is None or slave.get("filtered", False):
            continue
        status = cast(SourceStatus, _cleanup_slave_status(slave))
        if status not in statuses:
            statuses.append(status)

    return {"statuses": statuses}


def _cleanup_slave_status(status: BroadcastObject) -> BroadcastObject:
    result = cast(BroadcastObject, dict(status))
    result.pop("hostname", None)
    result.pop("pid", None)
    return result


@_tarball_service.get()  # type: ignore
def _tarball(request: pyramid.request.Request) -> pyramid.response.Response:
    id_ = request.matchdict["id"]
    source, filtered = registry.get_source_check_auth(id_=id_, request=request)
    if source is None:
        raise HTTPNotFound(f"Unknown id {id_}")
    if not source.is_loaded():
        raise HTTPNotFound("Not loaded yet")
    assert not filtered
    path = source.get_path()

    if not os.path.isdir(path):
        _LOG.error("The path %s does not exists or is not a path, for the source %s.", path, source.get_id())
        raise HTTPNotFound("Not loaded yet: path didn't exists")

    response: pyramid.response.Response = request.response

    files = os.listdir(path)
    if ".gitstats" in files:
        # put .gitstats at the end, that way, it is updated last at the destination
        files.remove(".gitstats")
        files.append(".gitstats")

    proc = subprocess.Popen(  # pylint: disable=consider-using-with # noqa: S603
        ["tar", "--create", "--gzip"] + files, cwd=path, bufsize=4096, stdout=subprocess.PIPE
    )
    response.content_type = "application/x-gtar"
    response.app_iter = _proc_iter(proc)
    return response


def _proc_iter(proc: subprocess.Popen[bytes]) -> Iterable[bytes | Any]:
    while True:
        block = proc.stdout.read(4096)  # type: ignore
        if not block:
            break
        yield block
    if proc.wait() != 0:
        raise HTTPServerError("Error building the tarball")
