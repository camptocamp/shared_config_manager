import os
from typing import Any

import c2cwsgiutils.pyramid
from c2cwsgiutils.health_check import HealthCheck
from pyramid.config import Configurator

from shared_config_manager.sources import registry


def main(_: Any, **settings: Any) -> Any:
    config = Configurator(settings=settings, route_prefix=os.environ.get("ROUTE_PREFIX", "/scm"))

    config.include(c2cwsgiutils.pyramid.includeme)
    config.scan("shared_config_manager.services")
    HealthCheck(config)

    if os.environ.get("IS_SLAVE", "false").lower() == "false":
        registry.init(slave=False)
    return config.make_wsgi_app()
