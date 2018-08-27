from c2cwsgiutils import broadcast

from . import sources


@broadcast.decorator(expect_answers=True)
def get_slave_stats():
    return {'sources': sources.get_stats()}
