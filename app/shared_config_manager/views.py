import logging
import math
import os.path
import re
import subprocess  # nosec
from pathlib import Path
from typing import Any, cast

import pyramid.request
import pyramid.response
import requests
from pyramid.httpexceptions import HTTPNotFound
from pyramid.security import Allowed
from pyramid.view import view_config

from shared_config_manager import slave_status
from shared_config_manager.configuration import SourceStatus
from shared_config_manager.sources import registry
from shared_config_manager.sources.base import BaseSource

_LOG = logging.getLogger(__name__)


def _is_valid(source: BaseSource) -> bool:
    if source is None:
        return False

    if source.is_master():
        return True

    slaves = slave_status.get_source_status(id_=source.get_id())
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


@view_config(route_name="ui_index", renderer="./templates/index.html.mako")  # type: ignore[misc]
def _ui_index(request: pyramid.request.Request) -> dict[str, Any]:
    permission = request.has_permission("all", {})
    is_admin = isinstance(permission, Allowed)

    sources_list = []

    if is_admin and registry.MASTER_SOURCE:
        sources_list.append(registry.MASTER_SOURCE)
        sources_list.extend(registry.get_sources().values())
    else:
        for key, source in registry.get_sources().items():
            permission = request.has_permission(key, source.get_config())
            if isinstance(permission, Allowed):
                sources_list.append(source)

    return {"sources": sources_list, "is_valid": _is_valid}


@view_config(route_name="ui_source", renderer="./templates/source.html.mako")  # type: ignore[misc]
def _ui_source(request: pyramid.request.Request) -> dict[str, Any]:
    def key_format(key: str) -> str:
        return key[0].upper() + key[1:].replace("_", " ")

    permission = request.has_permission("all", {})
    is_admin = isinstance(permission, Allowed)

    id_ = request.matchdict["id"]
    source, filtered = registry.get_source_check_auth(id_=id_, request=request)
    if source is None:
        message = f"Unknown id {id_} or forbidden"
        raise HTTPNotFound(message)
    if not is_admin:
        permission = request.has_permission(id_, source.get_config())
        if not isinstance(permission, Allowed):
            message = f"Unknown id {id_} or forbidden"
            raise HTTPNotFound(message)

    slaves = slave_status.get_source_status(id_=id_)
    assert slaves is not None
    statuses: list[SourceStatus] = []
    for slave in slaves:
        if slave is None or slave.get("filtered", False):
            continue
        if slave not in statuses:
            statuses.append(slave)

    attributes: list[tuple[str, str | bool]] = []
    if source.is_master():
        attributes.append(("ID", f"{source.get_id()} (Master)"))
    else:
        attributes.append(("ID", source.get_id()))
    attributes.append(("Loaded", source.is_loaded()))
    attributes.append(("Filtered", filtered))

    for key, value in source.get_config().items():
        if key == "tags":
            attributes.append(("Tags", ", ".join(cast(list[str], value))))
        elif key == "template_engines":
            continue
        else:
            attributes.append((key_format(key), str(value)))

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

    _slave_status: list[tuple[SourceStatus, list[str | tuple[str, str]]]] = []
    _repo_re = re.compile(r"^git@github.com:(.*).git$")
    for slave in statuses:
        try:
            match = _repo_re.match(source.get_config().get("repo", ""))
            commit_details: list[str | tuple[str, str]] = []
            if match is not None:
                headers = {"Accept": "application/vnd.github+json"}
                if "GITHUB_TOKEN" in os.environ:
                    headers["Authorization"] = f"token {os.environ['GITHUB_TOKEN']}"

                if "hash" not in slave:
                    _slave_status.append((slave, ["No provided hash"]))
                else:
                    commit_response = requests.get(
                        f"https://api.github.com/repos/{match.group(1)}/commits/{slave['hash']}",
                        headers=headers,
                    )
                    if not commit_response.ok:
                        _slave_status.append(
                            (slave, [f"Unable to get the commit status: {commit_response.reason}"]),
                        )
                    else:
                        commit_json = commit_response.json()
                        commit_details = [
                            (commit_json["html_url"], commit_json["sha"]),
                            f"Author: {commit_json['commit']['author']['name']}",
                            f"Date: {commit_json['commit']['author']['date']}",
                            f"Message: {commit_json['commit']['message']}",
                        ]

            else:
                commit_details = (
                    subprocess.run(  # type: ignore[assignment] # nosec
                        ["git", "show", "--quiet", slave["hash"]],
                        cwd=str(Path("/repos") / source.get_id()),
                        check=True,
                        stdout=subprocess.PIPE,
                    )
                    .stdout.decode("utf-8")
                    .split("\n")
                )
            _slave_status.append((slave, commit_details))
        except Exception:  # pylint: disable=broad-exception-caught # noqa: PERF203
            _LOG.warning("Unable to get the commit status for %s", slave.get("hash"), exc_info=True)
            _slave_status.append((slave, []))

    def _get_sort_key(elem: tuple[SourceStatus, list[str]]) -> str:
        return elem[0].get("hostname", "")

    return {
        "key_format": key_format,
        "source": source,
        "attributes": attributes4,
        "slave_status": sorted(_slave_status, key=_get_sort_key),
    }
