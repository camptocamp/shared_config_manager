from c2cwsgiutils import stats
import copy
import logging
import os
from pyramid.httpexceptions import HTTPForbidden
import requests
import shutil
import subprocess
import time

from shared_config_manager import template_engines
from . import mode

LOG = logging.getLogger(__name__)
TARGET = os.environ.get("TARGET", "/config")
MASTER_TARGET = os.environ.get("MASTER_TARGET", "/master_config")


class BaseSource(object):
    def __init__(self, id_, config, is_master):
        self._id = id_
        self._config = config
        self._is_master = is_master
        self._is_loaded = False
        self._template_engines = [
            template_engines.create_engine(engine_conf)
            for engine_conf in config.get('template_engines', [])
        ]

    def refresh_or_fetch(self):
        if mode.is_master():
            self.refresh()
        else:
            self.fetch()

    def refresh(self):
        LOG.info("Doing a refresh of %s", self._id)
        try:
            self._is_loaded = False
            with stats.timer_context(['source', self.get_id(), 'refresh']):
                self._do_refresh()
            self._eval_templates()
        except Exception:
            stats.increment_counter(['source', self._id, 'error'])
            raise
        finally:
            self._is_loaded = True

    def _eval_templates(self):
        for engine in self._template_engines:
            with stats.timer_context(['source', self.get_id(), 'template', engine.get_type()]):
                engine.evaluate(self.get_path())

    def fetch(self):
        try:
            self._is_loaded = False
            with stats.timer_context(['source', self.get_id(), 'fetch']):
                self._do_fetch()
            self._eval_templates()
        except Exception:
            stats.increment_counter(['source', self._id, 'error'])
            raise
        finally:
            self._is_loaded = True

    def _do_refresh(self):
        pass

    def _do_fetch(self):
        path = self.get_path()
        os.makedirs(path, exist_ok=True)
        url = mode.get_fetch_url(self._id, self._config['key'])
        while True:
            try:
                LOG.info("Doing a fetch of %s", self._id)
                r = requests.get(url, stream=True)
                r.raise_for_status()
                tar = subprocess.Popen(['tar', '--extract', '--gzip', '--no-same-owner',
                                        '--no-same-permissions', '--touch', '--no-overwrite-dir'],
                                       cwd=path, stdin=subprocess.PIPE)
                shutil.copyfileobj(r.raw, tar.stdin)
                tar.stdin.close()
                assert tar.wait() == 0
                return
            except Exception as e:
                stats.increment_counter(['source', self._id, 'fetch_error'])
                LOG.info("Error fetching the source %s from the master (will retry in 1s): %s",
                         self._id, str(e))
                time.sleep(1)

    def _copy(self, source, excludes=None):
        os.makedirs(self.get_path(), exist_ok=True)
        cmd = ['rsync', '--recursive', '--links', '--devices', '--specials', '--delete',
               '--verbose', '--checksum']
        if excludes is not None:
            cmd += ['--exclude=' + exclude for exclude in excludes]
        if 'excludes' in self._config:
            cmd += ['--exclude=' + exclude for exclude in self._config['excludes']]
        cmd += [source + '/', self.get_path()]
        with stats.timer_context(['source', self.get_id(), 'copy']):
            self._exec(*cmd)

    def delete_target_dir(self):
        dest = self.get_path()
        LOG.info("Deleting target dir %s", dest)
        if os.path.isdir(dest):
            shutil.rmtree(dest)

    def get_path(self) -> str:
        if 'target_dir' in self._config:
            target_dir = self._config['target_dir']
            if target_dir.startswith('/'):
                return target_dir
            else:
                return os.path.join(MASTER_TARGET if self._is_master else TARGET, target_dir)
        else:
            return os.path.join(MASTER_TARGET if self._is_master else TARGET, self.get_id())

    def get_id(self):
        return self._id

    def validate_key(self, key):
        if key != self._config['key']:
            raise HTTPForbidden("Invalid key")

    def is_master(self):
        return self._is_master

    def get_stats(self):
        stats_ = copy.deepcopy(self._config)
        del stats_['key']
        for template_stats, template_engine in zip(stats_.get('template_engines', []),
                                                   self._template_engines):
            template_engine.get_stats(template_stats)
        return stats_

    def get_config(self):
        return self._config

    def get_type(self):
        return self._config['type']

    def delete(self):
        self.delete_target_dir()

    def _exec(self, *args, **kwargs):
        try:
            args = list(map(str, args))
            LOG.debug("Running: " + ' '.join(args))
            output = subprocess.check_output(args, stderr=subprocess.STDOUT, env=dict(os.environ), **kwargs)
            output = output.decode("utf-8").strip()
            if output:
                LOG.debug(output)
            return output
        except subprocess.CalledProcessError as e:
            LOG.error(e.output.decode("utf-8").strip())
            raise

    def is_loaded(self):
        return self._is_loaded
