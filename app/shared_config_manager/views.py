import logging
import math
import os.path
import subprocess
from typing import Any, Dict, List, Tuple, Union, cast

import pyramid.request
import pyramid.response
from pyramid.httpexceptions import HTTPNotFound
from pyramid.security import Allowed
from pyramid.view import view_config

from shared_config_manager import slave_status
from shared_config_manager.configuration import SourceStatus
from shared_config_manager.sources import registry

_LOG = logging.getLogger(__name__)


@view_config(route_name="ui_index", renderer="./templates/index.html.mako")  # type: ignore
def _ui_index(request: pyramid.request.Request) -> Dict[str, Any]:
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

    return {"sources": sources_list}


@view_config(route_name="ui_source", renderer="./templates/source.html.mako")  # type: ignore
def _ui_source(request: pyramid.request.Request) -> Dict[str, Any]:
    def key_format(key: str) -> str:
        return key[0].upper() + key[1:].replace("_", " ")

    permission = request.has_permission("all", {})
    is_admin = isinstance(permission, Allowed)

    id_ = request.matchdict["id"]
    source, filtered = registry.check_id_key(id_=id_)
    if source is None:
        raise HTTPNotFound(f"Unknown id {id_} or forbidden")
    if not is_admin:
        permission = request.has_permission(id_, source.get_config())
        if not isinstance(permission, Allowed):
            raise HTTPNotFound(f"Unknown id {id_} or forbidden")

    slaves = slave_status.get_source_status(id_=id_)
    assert slaves is not None
    statuses: List[SourceStatus] = []
    for slave in slaves:
        if slave is None or slave.get("filtered", False):
            continue
        if slave not in statuses:
            statuses.append(slave)

    attributes: List[Tuple[str, Union[str, bool]]] = []
    if source.is_master():
        attributes.append(("ID", f"{source.get_id()} (Master)"))
    else:
        attributes.append(("ID", source.get_id()))
    attributes.append(("Loaded", source.is_loaded()))
    attributes.append(("Filtered", filtered))

    for key, value in source.get_config().items():
        if key == "tags":
            attributes.append(("Tags", ", ".join(cast(List[str], value))))
        elif key == "template_engines":
            continue
        else:
            attributes.append((key_format(key), str(value)))

    attributes4: List[Tuple[str, Union[str, bool], str, Union[str, bool]]] = []
    attributes4_height = math.ceil(len(attributes) / 2)
    for index in range(attributes4_height):
        if index + attributes4_height < len(attributes):
            attributes4.append(
                (
                    attributes[index][0],
                    attributes[index][1],
                    attributes[attributes4_height + index][0],
                    attributes[attributes4_height + index][1],
                )
            )
        else:
            attributes4.append((attributes[index][0], attributes[index][1], "", ""))

    _slave_status: List[Tuple[SourceStatus, List[str]]] = []
    for slave in statuses:
        try:
            _slave_status.append(
                (
                    slave,
                    (
                        subprocess.run(
                            ["git", "show", "--quiet", slave["hash"]],
                            cwd=os.path.join("/repos", source.get_id()),
                            check=True,
                            stdout=subprocess.PIPE,
                        )
                        .stdout.decode("utf-8")
                        .split("\n")
                    ),
                )
            )
        except Exception:
            _LOG.warning("Unable to get the commit status for %s", slave.get("hash"), exc_info=True)
            _slave_status.append((slave, []))

    return {
        "key_format": key_format,
        "source": source,
        "attributes": attributes4,
        "slave_status": _slave_status,
    }
