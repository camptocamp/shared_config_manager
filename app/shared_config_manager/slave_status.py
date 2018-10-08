from c2cwsgiutils import broadcast

from . import sources


@broadcast.decorator(expect_answers=True)
def get_slaves_status():
    return {'sources': sources.get_stats()}


@broadcast.decorator(expect_answers=True)
def get_source_status(id_):
    source = sources.get_source(id_)
    if source is None:
        return {
            'filtered': id_ in sources.filtered_sources
        }
    else:
        return source.get_stats()
