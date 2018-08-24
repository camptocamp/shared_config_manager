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
    LOG.info("Conf path: %s", os.path.join(master_config.get_path(), 'shared_config_manager.yaml'))
    with open(os.path.join(master_config.get_path(), 'shared_config_manager.yaml')) as config_file:
        config = yaml.load(config_file)
        source_configs = {}
        for source in config['sources']:
            try:
                source_configs[source['id']] = _create_source(source)
            except Exception:
                LOG.error("Cannot load the %s config", source['id'], exc_info=True)


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
