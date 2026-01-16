import asyncio
import logging
import re
import shlex
import subprocess  # nosec
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Annotated, Literal, cast

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from shared_config_manager import broadcast_status, configuration, slave_status
from shared_config_manager.security import User, get_identity
from shared_config_manager.sources import registry

if TYPE_CHECKING:
    from shared_config_manager.sources import git

app = FastAPI()

_LOG = logging.getLogger(__name__)
__BRANCH_NAME_SANITIZER = re.compile(r"[^0-9a-zA-Z-_]")


class SourceRefPayload(BaseModel):
    """GitHub webhook payload model."""

    ref: str | None = None


class RefreshResponse(BaseModel):
    """Response model for refresh endpoints."""

    status: int
    ignored: bool | None = None
    reason: str | None = None


class RefreshAllResponse(BaseModel):
    """Response model for refresh all endpoints."""

    status: int
    nb_refresh: int = 0
    ignored: bool | None = None
    reason: str | None = None


class Auth(BaseModel):
    """Authentication model."""

    github_access_type: str | None = None
    github_repository: str | None = None


class SourceStatus(BaseModel):
    """Source status model."""

    filtered: bool | None = None
    template_engines: list[configuration.TemplateEnginesStatus] = []
    hash: str | None = None
    auth: Auth | None = None
    branch: str | None = None
    repo: str | None = None
    sub_dir: str | None = None
    tags: list[str] = []
    type: Literal["git", "rsync", "rclone"] | None = None


class SlaveStatus(BaseModel):
    """Slave status model."""

    sources: dict[str, SourceStatus]


class StatusResponse(BaseModel):
    """Response model for status endpoint."""

    slaves: dict[str, SlaveStatus]


class SourceStatusResponse(BaseModel):
    """Response model for source status endpoint."""

    statuses: list[SourceStatus]


async def startup(app: FastAPI) -> None:
    """Startup event handler."""
    # Here you can add any startup logic for the api
    del app


@app.get("/refresh/{source_id}", response_model_exclude_none=True)
async def _refresh_view(
    request: Request,
    source_id: str,
    identity: Annotated[User | None, Depends(get_identity)],
) -> RefreshResponse:
    source, _ = await registry.get_source_check_auth(source_id=source_id, identity=identity, request=request)
    if source is None:
        message = f"Unknown id {source_id}"
        raise HTTPException(status_code=404, detail=message)
    return await _refresh(source_id, identity, request)


@app.post("/refresh/{source_id}", response_model_exclude_none=True)
async def _refresh_webhook(
    request: Request,
    source_id: str,
    payload: SourceRefPayload,
    identity: Annotated[User | None, Depends(get_identity)],
    x_github_event: Annotated[str | None, Header()] = None,
) -> RefreshResponse:
    source, _ = await registry.get_source_check_auth(source_id=source_id, identity=identity, request=request)
    if source is None:
        message = f"Unknown id {source_id}"
        raise HTTPException(status_code=404, detail=message)

    if source.get_type() != "git":
        message = f"Non GIT source {source_id} cannot be refreshed by a webhook"
        raise HTTPException(status_code=500, detail=message)

    source_git = cast("git.GitSource", source)

    if x_github_event != "push":
        _LOG.info("Ignoring webhook notif for a non-push event on %s", source_id)
        return RefreshResponse(status=200, ignored=True, reason="Not a push")

    ref = payload.ref
    if ref is None:
        message = f"Webhook for {source_id} is missing the ref"
        raise HTTPException(status_code=500, detail=message)
    if ref != "refs/heads/" + source_git.get_branch():
        _LOG.info(
            "Ignoring webhook notif for non-matching branch %s on %s",
            source_git.get_branch(),
            source_id,
        )
        branch = __BRANCH_NAME_SANITIZER.sub("", source_git.get_branch())
        return RefreshResponse(status=200, ignored=True, reason=f"Not {branch} branch")

    return await _refresh(source_id, identity, request)


async def _refresh(source_id: str, identity: User | None, request: Request) -> RefreshResponse:
    await registry.refresh(source_id=source_id, identity=identity, request=request)
    return RefreshResponse(status=200)


@app.get("/refresh", response_model_exclude_none=True)
async def _refresh_all(
    request: Request,
    identity: Annotated[User | None, Depends(get_identity)],
) -> RefreshAllResponse:
    if not registry.MASTER_SOURCE:
        message = "Master source not initialized"
        raise HTTPException(status_code=500, detail=message)
    await registry.MASTER_SOURCE.validate_auth(identity=identity, request=request)
    nb_refresh = 0
    for source_id in registry.get_sources():
        await registry.refresh(source_id=source_id, identity=identity, request=request)
        nb_refresh += 1
    return RefreshAllResponse(status=200, nb_refresh=nb_refresh)


@app.post("/refresh", response_model_exclude_none=True)
async def _refresh_all_webhook(
    request: Request,
    payload: SourceRefPayload,
    identity: Annotated[User | None, Depends(get_identity)],
    x_github_event: Annotated[str | None, Header()] = None,
) -> RefreshAllResponse:
    if not registry.MASTER_SOURCE:
        message = "Master source not initialized"
        raise HTTPException(status_code=500, detail=message)
    await registry.MASTER_SOURCE.validate_auth(identity=identity, request=request)

    if x_github_event != "push":
        _LOG.info("Ignoring webhook notif for a non-push event")
        return RefreshAllResponse(status=200, ignored=True, reason="Not a push")

    ref = payload.ref
    if ref is None:
        message = "Webhook is missing the ref"
        raise HTTPException(status_code=500, detail=message)

    nb_refresh = 0
    for source_id, source in registry.get_sources().items():
        if not source or source.get_type() != "git":
            continue

        source_git = cast("git.GitSource", source)

        if ref != "refs/heads/" + source_git.get_branch():
            _LOG.info(
                "Ignoring webhook notif for non-matching branch %s!=refs/heads/%s on %s",
                ref,
                source_git.get_branch(),
                source_id,
            )
            continue
        await registry.refresh(source_id=source_id, identity=identity, request=request)
        nb_refresh += 1

    return RefreshAllResponse(status=200, nb_refresh=nb_refresh)


def _source_status_from_dict(data: broadcast_status.SourceStatus) -> SourceStatus:
    return SourceStatus(**{k: v for k, v in data.items() if k not in {"hostname"}})  # type: ignore[arg-type]


@app.get("/status", response_model_exclude_none=True)
async def _stats(request: Request, identity: Annotated[User | None, Depends(get_identity)]) -> StatusResponse:
    if not registry.MASTER_SOURCE:
        return StatusResponse(slaves={})
    await registry.MASTER_SOURCE.validate_auth(identity=identity, request=request)
    slaves_status = await slave_status.get_slaves_status()
    assert slaves_status is not None
    return StatusResponse(
        slaves={
            slave["hostname"]: SlaveStatus(
                sources={
                    key: _source_status_from_dict(source) for key, source in slave.get("sources", {}).items()
                },
            )
            for slave in slaves_status
            if slave is not None
        },
    )


@app.get("/status/{source_id}", response_model_exclude_none=True)
async def _source_stats(
    request: Request,
    source_id: str,
    identity: Annotated[User | None, Depends(get_identity)],
) -> SourceStatusResponse:
    source, _ = await registry.get_source_check_auth(source_id=source_id, identity=identity, request=request)
    if source is None:
        message = f"Unknown id {source_id}"
        raise HTTPException(status_code=404, detail=message)
    slaves: list[broadcast_status.SourceStatus] | None = await slave_status.get_source_status(
        source_id=source_id
    )
    assert slaves is not None
    statuses: list[SourceStatus] = []
    for slave in slaves:
        if slave is None or slave.get("filtered", False):
            continue
        new_status = _source_status_from_dict(slave)
        if new_status not in statuses:
            statuses.append(new_status)

    return SourceStatusResponse(statuses=statuses)


@app.get("/tarball/{source_id}")
async def _tarball(
    request: Request,
    source_id: str,
    identity: Annotated[User | None, Depends(get_identity)],
) -> StreamingResponse:
    source, filtered = await registry.get_source_check_auth(
        source_id=source_id,
        identity=identity,
        request=request,
    )
    if source is None:
        message = f"Unknown id {source_id}"
        raise HTTPException(status_code=404, detail=message)
    if not source.is_loaded():
        message = "Not loaded yet"
        raise HTTPException(status_code=404, detail=message)
    assert not filtered
    path = source.get_path()

    if not path.is_dir():
        _LOG.error("The path %s does not exists or is not a path, for the source %s.", path, source.get_id())
        message = "Not loaded yet: path didn't exists"
        raise HTTPException(status_code=404, detail=message)

    files = [file.name for file in path.iterdir()]
    gitstats_filename = ".gitstats"
    if gitstats_filename in files:
        # put .gitstats at the end, that way, it is updated last at the destination
        files.remove(gitstats_filename)
        files.append(gitstats_filename)

    async def tarball_generator() -> AsyncGenerator[bytes, None]:
        args = [
            "tar",
            "--create",
            "--gzip",
            *files,
        ]
        proc = await asyncio.create_subprocess_exec(  # pylint: disable=consider-using-with # nosec
            *args,
            cwd=str(path),
            stdout=subprocess.PIPE,
        )
        if proc.stdout:
            while True:
                block = await proc.stdout.read(4096)
                if not block:
                    break
                yield block
        if await proc.wait() != 0:
            _LOG.error(
                "Error building the tarball with '%s'",
                shlex.join(args),
            )
            message = "Error building the tarball"
            raise HTTPException(status_code=500, detail=message)

    return StreamingResponse(tarball_generator(), media_type="application/x-gtar")
