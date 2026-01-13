import asyncio
import logging
import math
import re
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Annotated, cast

import aiohttp
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from shared_config_manager import config, nonce, slave_status
from shared_config_manager.configuration import SourceStatus
from shared_config_manager.security import Allowed, User, get_identity, permits
from shared_config_manager.sources import registry
from shared_config_manager.sources.base import BaseSource

_LOG = logging.getLogger(__name__)
_REPO_RE = re.compile(r"^git@github.com:(.*).git$")

# Create FastAPI app for UI
app = FastAPI(title="Shared Config Manager UI")

# Configure templates
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# Configure static files
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")


async def _is_valid(source: BaseSource) -> bool:
    if source is None:
        return False

    if source.is_master():
        return True

    slaves = await slave_status.get_source_status(source_id=source.get_id())
    if slaves is None:
        return True
    hash_ = ""
    for slave in slaves:
        if slave is None or slave.get("filtered", False):
            continue
        slave_hash = slave.get("hash")
        if slave_hash is None:
            return False
        if hash_:
            if slave_hash != hash_:
                return False
        else:
            hash_ = slave_hash
    return True


async def check_admin_permission(
    identity: Annotated[User | None, Depends(get_identity)],
) -> bool:
    """FastAPI dependency to check if user has admin permission."""
    # Check if user has "all" permission
    permission = await permits(identity, None, "all")

    return isinstance(permission, Allowed)


@app.get("/", response_class=HTMLResponse)
async def ui_index(
    request: Request,
    is_admin: Annotated[bool, Depends(check_admin_permission)],
    identity: Annotated[User | None, Depends(get_identity)],
) -> HTMLResponse:
    """Render the index page with list of sources."""
    sources_list = []

    if is_admin and registry.MASTER_SOURCE:
        sources_list.append(registry.MASTER_SOURCE)
        sources_list.extend(registry.get_sources().values())
    else:
        for key, source in registry.get_sources().items():
            permission = await permits(identity, source.get_config(), key)

            if isinstance(permission, Allowed):
                sources_list.append(source)

    valid_sources = list(
        zip(await asyncio.gather(*[_is_valid(source) for source in sources_list]), sources_list, strict=True),
    )

    return templates.TemplateResponse(
        "index.html.jinja2",
        {
            "request": request,
            "identity": identity,
            "nonce": nonce,
            "valid_sources": valid_sources,
        },
    )


def _get_source_attributes(
    source: BaseSource, filtered: bool, key_format: Callable[[str], str]
) -> list[tuple[str, str | bool]]:
    """Get the source attributes for display."""
    attributes: list[tuple[str, str | bool]] = []
    if source.is_master():
        attributes.append(("ID", f"{source.get_id()} (Master)"))
    else:
        attributes.append(("ID", source.get_id()))
    attributes.append(("Loaded", source.is_loaded()))
    attributes.append(("Filtered", filtered))

    for key, value in source.get_config().items():
        if key == "tags":
            attributes.append(("Tags", ", ".join(cast("list[str]", value))))
        elif key == "template_engines":
            continue
        else:
            attributes.append((key_format(key), str(value)))
    return attributes


def _format_attributes_for_display(
    attributes: list[tuple[str, str | bool]],
) -> list[tuple[str, str | bool, str, str | bool]]:
    """Format attributes into a two-column layout for display."""
    attributes4: list[tuple[str, str | bool, str, str | bool]] = []
    attributes4_height = math.ceil(len(attributes) / 2)
    for index in range(attributes4_height):
        if index + attributes4_height < len(attributes):
            attributes4.append(
                (
                    attributes[index][0],
                    attributes[index][1],
                    attributes[attributes4_height + index][0],
                    attributes[attributes4_height + index][1],
                ),
            )
        else:
            attributes4.append((attributes[index][0], attributes[index][1], "", ""))
    return attributes4


async def _fetch_commit_details(
    source: BaseSource,
    slave: SourceStatus,
) -> tuple[SourceStatus, Sequence[str | tuple[str, str]]]:
    """Fetch commit details from GitHub or local git repository."""
    try:
        match = _REPO_RE.match(source.get_config().get("repo", ""))
        commit_details: Sequence[str | tuple[str, str]] = []
        if match is not None:
            headers = {"Accept": "application/vnd.github+json"}
            if config.settings.github_token:
                headers["Authorization"] = f"token {config.settings.github_token}"

            if "hash" not in slave:
                return (slave, ["No provided hash"])

            async with (
                aiohttp.ClientSession() as session,
                session.get(
                    f"https://api.github.com/repos/{match.group(1)}/commits/{slave['hash']}",
                    headers=headers,
                ) as commit_response,
            ):
                if not commit_response.ok:
                    return (
                        slave,
                        [f"Unable to get the commit status: {commit_response.reason}"],
                    )

                commit_json = await commit_response.json()
                commit_details = [
                    (commit_json["html_url"], commit_json["sha"]),
                    f"Author: {commit_json['commit']['author']['name']}",
                    f"Date: {commit_json['commit']['author']['date']}",
                    f"Message: {commit_json['commit']['message']}",
                ]
                return (slave, commit_details)

        else:
            process = await asyncio.create_subprocess_exec(  # nosec
                "git",
                "show",
                "--quiet",
                slave["hash"],
                cwd=str(Path("/repos") / source.get_id()),
                stdout=asyncio.subprocess.PIPE,
            )
            stdout, _ = await process.communicate()
            commit_details = stdout.decode("utf-8").split("\n")
            return (slave, commit_details)
    except Exception:  # noqa: BLE001
        _LOG.warning("Unable to get the commit status for %s", slave.get("hash"), exc_info=True)
        return (slave, [])


@app.get("/source/{source_id}", response_class=HTMLResponse)
async def ui_source(
    source_id: str,
    request: Request,
    is_admin: Annotated[bool, Depends(check_admin_permission)],
    identity: Annotated[User | None, Depends(get_identity)],
) -> HTMLResponse:
    """Render the source details page."""

    def key_format(key: str) -> str:
        return key[0].upper() + key[1:].replace("_", " ")

    source, filtered = await registry.get_source_check_auth(
        source_id=source_id,
        identity=identity,
        request=request,
    )
    if source is None:
        message = f"Unknown id {source_id} or forbidden"
        raise HTTPException(status_code=404, detail=message)

    if not is_admin:
        permission = await permits(identity, source.get_config(), source_id)
        if not isinstance(permission, Allowed):
            message = f"Unknown id {source_id} or forbidden"
            raise HTTPException(status_code=404, detail=message)

    slaves = await slave_status.get_source_status(source_id=source_id)
    assert slaves is not None
    statuses: list[SourceStatus] = []
    for slave in slaves:
        if slave is None or slave.get("filtered", False):
            continue
        if slave not in statuses:
            statuses.append(slave)

    attributes = _get_source_attributes(source, filtered, key_format)
    attributes4 = _format_attributes_for_display(attributes)

    _slave_status = await asyncio.gather(*[_fetch_commit_details(source, slave) for slave in statuses])

    def _get_sort_key(elem: tuple[SourceStatus, Sequence[str | tuple[str, str]]]) -> str:
        return elem[0].get("hostname", "")

    return templates.TemplateResponse(
        "source.html.jinja2",
        {
            "request": request,
            "identity": identity,
            "nonce": nonce,
            "key_format": key_format,
            "source": source,
            "attributes": attributes4,
            "slave_status": sorted(_slave_status, key=_get_sort_key),
        },
    )
