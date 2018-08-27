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
master_config = None
source_configs = {}


def _create_source(config, is_master=False):
    type_ = config['type']
    return SOURCES[type_](config, is_master)


def init():
    global master_config
    content = yaml.load(os.environ['MASTER_CONFIG'])
    master_config = _create_source(content, is_master=True)
    reload_master_config()


def reload_master_config():
    global source_configs, master_config
    LOG.info("Reloading the master config")
    master_config.refresh()
    with open(os.path.join(master_config.get_path(), 'shared_config_manager.yaml')) as config_file:
        config = yaml.load(config_file)
        to_deletes = set(source_configs.keys()) - {source['id'] for source in config['sources']}
        for to_delete in to_deletes:
            # TODO: test
            _delete_source(to_delete)
        for source in config['sources']:
            id_ = source['id']
            if id_ not in source_configs:
                LOG.info("New source detected: %s", id_)
            elif source_configs[id_].get_config() == source:
                LOG.debug("Source %s didn't change, not reloading it", id_)
                continue
            else:
                LOG.info("Change detected in source %s, reloading it", id_)

            try:
                source_configs[id_] = _create_source(source)
                source_configs[id_].refresh()
            except Exception:
                LOG.error("Cannot load the %s config", id_, exc_info=True)


def _delete_source(id_):
    global source_configs
    source_configs[id_].delete_target_dir()
    del source_configs[id_]


@broadcast.decorator(expect_answers=True)
def refresh(id_, key):
    config = _get_config(id_, key)
    if config.is_master():
        reload_master_config()
    else:
        config.refresh()
    return True


def check_id_key(id_, key):
    _get_config(id_, key)


def _get_config(id_, key):
    global master_config, source_configs
    if master_config.get_id() == id_:
        config = master_config
    else:
        config = source_configs.get(id_)
    if config is None:
        raise HTTPNotFound(f"Unknown id {id_}")
    config.validate_key(key)
    return config


def get_stats():
    return {
        id_: source.get_stats()
        for id_, source in {**source_configs, master_config.get_id(): master_config}.items()
    }
