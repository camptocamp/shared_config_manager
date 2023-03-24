import os
from typing import Any

from c2cwsgiutils.health_check import HealthCheck
import c2cwsgiutils.pyramid
from pyramid.config import Configurator
import pyramid.request
import pyramid.response

import shared_config_manager.security
from shared_config_manager.sources import registry
import shared_config_manager.views


def forbidden(request: pyramid.request.Request) -> pyramid.response.Response:
    is_auth = c2cwsgiutils.auth.is_auth(request)

    if is_auth:
        return pyramid.httpexceptions.HTTPForbidden(request.exception.message)
    return pyramid.httpexceptions.HTTPFound(
        location=request.route_url(
            "c2c_github_login",
            _query={"came_from": request.current_route_url()},
        )
    )


def main(_: Any, **settings: Any) -> Any:
    config = Configurator(settings=settings, route_prefix=os.environ.get("ROUTE_PREFIX", "/scm"))

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
