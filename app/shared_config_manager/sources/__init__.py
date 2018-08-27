from c2cwsgiutils import broadcast
import logging
import os
from pyramid.httpexceptions import HTTPNotFound
import yaml

from . import git

SOURCES = {
    'git': git.GitSource
}
LOG = logging.getLogger(__name__)
master_source = None
sources = {}


def _create_source(config, is_master=False):
    type_ = config['type']
    return SOURCES[type_](config, is_master)


def init():
    global master_source
    content = yaml.load(os.environ['MASTER_CONFIG'])
    master_source = _create_source(content, is_master=True)
    reload_master_config()


def reload_master_config():
    global sources, master_source
    LOG.info("Reloading the master config")
    master_source.refresh()
    with open(os.path.join(master_source.get_path(), 'shared_config_manager.yaml')) as config_file:
        config = yaml.load(config_file)
        to_deletes = set(sources.keys()) - {source['id'] for source in config['sources']}
        for to_delete in to_deletes:
            # TODO: test
            _delete_source(to_delete)
        for source in config['sources']:
            id_ = source['id']
            if id_ not in sources:
                # TODO: test
                LOG.info("New source detected: %s", id_)
            elif sources[id_].get_config() == source:
                LOG.debug("Source %s didn't change, not reloading it", id_)
                continue
            else:
                # TODO: test
                LOG.info("Change detected in source %s, reloading it", id_)

            try:
                sources[id_] = _create_source(source)
                sources[id_].refresh()
            except Exception:
                LOG.error("Cannot load the %s config", id_, exc_info=True)


def _delete_source(id_):
    global sources
    sources[id_].delete_target_dir()
    del sources[id_]


@broadcast.decorator(expect_answers=True)
def refresh(id_, key):
    config = _get_source(id_, key)
    if config.is_master():
        reload_master_config()
    else:
        config.refresh()
    return True


def check_id_key(id_, key):
    return _get_source(id_, key)


def _get_source(id_, key):
    global master_source, sources
    if master_source.get_id() == id_:
        config = master_source
    else:
        config = sources.get(id_)
    if config is None:
        raise HTTPNotFound(f"Unknown id {id_}")
    config.validate_key(key)
    return config


def get_stats():
    return {
        id_: source.get_stats()
        for id_, source in {**sources, master_source.get_id(): master_source}.items()
    }
