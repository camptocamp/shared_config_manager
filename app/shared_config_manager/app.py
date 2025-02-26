import logging
import os
import time
from threading import Thread
from typing import Any

import c2cwsgiutils.pyramid
import pyramid.request
import pyramid.response
from c2cwsgiutils.health_check import HealthCheck
from pyramid.config import Configurator

import shared_config_manager.security
import shared_config_manager.views
from shared_config_manager import slave_status
from shared_config_manager.sources import registry

_LOG = logging.getLogger(__name__)


def forbidden(request: pyramid.request.Request) -> pyramid.response.Response:
    """Redirect to the login page if the user is not authenticated."""
    is_auth = c2cwsgiutils.auth.is_auth(request)

    if is_auth:
        return pyramid.httpexceptions.HTTPForbidden(request.exception.message)
    return pyramid.httpexceptions.HTTPFound(
        location=request.route_url(
            "c2c_github_login",
            _query={"came_from": request.current_route_url()},
        )
    )


def _watch_source():
    """Watch the source."""
    while True:
        try:
            for key, source in registry.get_sources().items():
                try:
                    if source.is_master():
                        continue

                    slaves = slave_status.get_source_status(id_=key)
                    need_refresh = False
                    hash_ = ""
                    for slave in slaves:
                        if slave is None or slave.get("filtered", False):
                            continue

                        if "hash" not in slave:
                            need_refresh = True
                            _LOG.warning(
                                "No hash in the slave '%s' status for source '%s' -> refresh.",
                                slave.get("hostname"),
                                key,
                            )

                        if hash_:
                            if slave.get("hash") != hash_:
                                need_refresh = True
                                _LOG.warning(
                                    "The hash in the slave '%s' status for source '%s' is different -> refresh.",
                                    slave.get("hostname"),
                                    key,
                                )
                        else:
                            hash_ = slave.get("hash")

                    if need_refresh:
                        source.refresh()
                except Exception:  # pylint: disable=broad-exception-caught
                    _LOG.exception("Error while watching the source %s", key)
        except Exception:  # pylint: disable=broad-exception-caught
            _LOG.exception("Error while watching the sources")
        time.sleep(int(os.environ.get("WATCH_SOURCE_INTERVAL", "600")))


def main(_: Any, **settings: Any) -> Any:
    """Get the WSGI application."""
    config = Configurator(settings=settings, route_prefix=os.environ.get("ROUTE_PREFIX", "/scm"))

    Thread(target=_watch_source, daemon=True).start()

    config.include(c2cwsgiutils.pyramid.includeme)
    config.include("pyramid_mako")
    config.set_security_policy(shared_config_manager.security.SecurityPolicy())
    config.add_forbidden_view(forbidden)

    config.add_route("ui_index", "/", request_method="GET")
    config.add_route("ui_source", "/source/{id}", request_method="GET")

    config.add_static_view(name="static", path="/app/shared_config_manager/static")

    config.scan("shared_config_manager.services")
    config.scan("shared_config_manager.views")
    HealthCheck(config)

    if os.environ.get("IS_SLAVE", "false").lower() == "false":
        registry.init(slave=False)
    return config.make_wsgi_app()
