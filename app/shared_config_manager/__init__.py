import c2cwsgiutils.pyramid
from c2cwsgiutils.health_check import HealthCheck
import os
from pyramid.config import Configurator

from . import sources


def main(_, **settings):
    config = Configurator(settings=settings, route_prefix=os.environ.get('ROUTE_PREFIX', '/scm'))

    config.include(c2cwsgiutils.pyramid.includeme)
    config.scan("shared_config_manager.services")
    HealthCheck(config)
    sources.init()
    return config.make_wsgi_app()
