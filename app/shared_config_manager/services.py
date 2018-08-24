from c2cwsgiutils import services
import logging

from . import sources

refresh_service = services.create('refresh', '/1/refresh/{id}/{key}')
LOG = logging.getLogger(__name__)


@refresh_service.get()
def refresh(request):
    sources.check_id_key(id_=request.matchdict['id'], key=request.matchdict['key'])
    answers = sources.refresh(id_=request.matchdict['id'], key=request.matchdict['key'])
    return answers
