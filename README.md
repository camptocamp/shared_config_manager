# Shared Config Manager

Solves the problem of maintaining configuration volumes in the Docker world.

It allows to have a container (in the same POD for Kubernetes or as a sidekick in
Rancher) maintaining a few configuration/resource directories from different sources:

- A GIT repository
- A S3 bucket
- Another volume or server through rsync

A source can be refreshed through a webhook and the status of all the containers can be
queried through a simple API.

## Configuration

First you need to configure the source for the master configuration using the
`MASTER_CONFIG` environment variable with something like:

```yaml
env:
  MASTER_CONFIG: |
    type: git
    key: changeme
    repo: git@github.com:camptocamp/master_config.git
```

That will use the `shared_config_manager.yaml` file at the root of the repository
to configure all the sources. This configuration file looks like that:

```yaml
sources:
  test_git:
    type: git
    repo: git@github.com:camptocamp/test_git.git
    key: changeme
    target_dir: /usr/local/tomcat/webapps/ROOT/print-apps
```

With this example, the config container will contain a `/usr/local/tomcat/webapps/ROOT/print-apps`
directory that is a clone of the `git@github.com:camptocamp/test_git.git` repository and is identified as
`test_git`.

You can configure more than one source.

There is a standalone mode where you can configure only one source through the `MASTER_CONFIG`
environment variable. For that, set the `standalone` key to `true` in the `MASTER_CONFIG` and no
`shared_config_manager.yaml` will be searched.

There is also a mode where you can put directly the sources in the `MASTER_CONFIG`
by setting the `sources` section and setting a `key` string both directly at the root of the
`MASTER_CONFIG`.

### Tunnings

A few environment variables can be used to tune the containers:

- `C2C_REDIS_URL`: Must point to a running Redis (typical: `redis://redis:6379`) for being able to
  broadcast the refresh notifications
- `MASTER_CONFIG`: The master configuration (string containing the YAML config)
- `ROUTE_PREFIX`: The prefix to use for the HTTP API (defaults to `/scm`)
- `TAG_FILTER`: Load only the sources having the given tag (the master config is always loaded)
- `TARGET`: default base directory for the `target_dir` configuration (defaults to `/config`)
- `MASTER_TARGET`: where to store the master config (defaults to `/master_config`)
- `API_BASE_URL`: how to reach the master for slaves.
- `API_MASTER`: if defined, this is a master with slaves (no template evaluation)

See [https://github.com/camptocamp/c2cwsgiutils] for other parameters.

### Sources

#### Common source configuration parameters

- `type`: the type of source
- `key`: the secret key that will be used to trigger a refresh of the source. Uses the `key` specified at the root
  of the config by default.
- `target_dir`: the location where the source will be copied (default is the value of `id` in `/config`)
- `excludes`: the list of files/directories to exclude
- `template_engines`: a list of template engine configurations
- `tags`: an optional list of tags. Slaves having `TAG_FILTER` defined will load only sources having the matching tag.

#### GIT source configuration parameters

- `type`: `git`
- `ssh_key`: the private SSH key to use as identity (optional)
- `repo`: the GIT repository URL
- `branch`: the GIT branch to use (defaults to `master`)
- `sub_dir`: if only a sub_directory of the repository needs to be copied (defaults to the root of the
  repository)
- `sparse`: if true (the default) and `sub_dir` is defined, will use a sparse clone. Disable that if you have multiple
  sources using the same repository (will avoid cloning it for each sources).

#### Rsync source configuration parameters

- `type`: `rsync`
- `source`: the source for the rsync command
- `ssh_key`: the private SSH key to use as identity (optional)

#### Rclone source configuration parameters

- `type`: `rclone`
- `config`: The content of the rclone configuration section to use.
- `sub_dir`: An optional sub-directory inside the remote (bucket + path for the S3 remotes)

### Template engines

- `type`: can be `mako` or `shell`
- `data`: a dictionary of key/value to pass as a parameter to the template engine
- `environment_variables`: If `true`, take into account the process' environment variables
  if not found in `data`. Only variables starting with a prefix listed in `SCM_ENV_PREFIXES`
  (list separated by `:`) are allowed.
- `dest_sub_dir`: If specified, all the files, including the ones not evaluated as templates
  will be copied into the given sub directory.

## Slave only mode

By default the image starts a WSGI server listening on port 8080. In big deployments a full WSGI server
could use a sizeable amount of RAM. So you could have only a couple of such containers and the rest running
as slaves. For that, change the command run by the container to `shared-config-slave`.

## Example docker-compose for Rancher

docker-compose.yaml:

```yaml
version: '2'
services:
  scm_api:
    image: camptocamp/shared_config_manager:latest
    environment: &scm_env
      C2C_REDIS_URL: redis://redis:6379
      MASTER_CONFIG: &master_config |
        type: git
        key: changeme
        repo: git@github.com:camptocamp/master_config.git
      TAG_FILTER: master
    links:
      - redis
    labels:
      io.rancher.container.hostname_override: container_name
      lb.routing_key: scm-${ENVIRONMENT_NAME}
      lb.haproxy_backend.timeout_server: 'timeout server 120s'
      lb.haproxy_backend.maxconn: default-server maxconn 1

  scm_slave:
    image: camptocamp/shared_config_manager:latest
    environment: *scm_env
    command: ['shared-config-slave']
    volumes:
      - /usr/local/tomcat/webapps/ROOT/print-apps
    links:
      - redis
    labels:
      io.rancher.container.hostname_override: container_name
      io.rancher.scheduler.global: 'true'

  print:
    image: camptocamp/mapfish_print:3.14.1
    labels:
      io.rancher.container.hostname_override: container_name
      io.rancher.scheduler.global: 'true'
      io.rancher.sidekicks: scm_slave
    volumes_from:
      - scm_slave

  redis:
    labels:
      io.rancher.container.hostname_override: container_name
    image: redis:4
    mem_limit: 64m
    command: redis-server --save "" --appendonly no
    user: www-data
```

rancher-compose.yaml:

```yaml
version: '2'
services:
  scm_api:
    scale: 1
    health_check:
      port: 8080
      interval: 10000
      unhealthy_threshold: 3
      request_line: GET /scm/c2c/health_check HTTP/1.0
      healthy_threshold: 1
      response_timeout: 10000
      strategy: recreate

  scm_slave: {}

  redis:
    scale: 1
    health_check:
      port: 6379
      interval: 2000
      initializing_timeout: 60000
      unhealthy_threshold: 3
      strategy: recreate
      healthy_threshold: 1
      response_timeout: 3000
```

## Example OpenShift chart

Look there: [https://github.com/camptocamp/private-geo-charts/tree/master/mutualized-print]

# API

## Refresh

- `GET {ROUTE_PREFIX}/1/refresh/{ID}/{KEY}`

Refresh the given source `{ID}`. Returns 200 in case of success. The actual work is done asynchronously.

To refresh the master configuration (list of sources), use `master` as ID.

- `POST {ROUTE_PREFIX}/1/refresh/{ID}/{KEY}`

Same as the GET API, but to be used with a GutHub/GitLab webhook for push events. Will ignore events for other branches.

- `GET {ROUTE_PREFIX}/1/refresh/{KEY}`

Refresh all sources. Returns 200 in case of success. The actual work is done asynchronously.

The master configuration is not refreshed.

- `POST {ROUTE_PREFIX}/1/refresh/{KEY}`

Same as the GET API, but to be used with a GutHub/GitLab webhook for push events. Will ignore events for other branches.

## Status

- `GET {ROUTE_PREFIX}/1/status/{key}`

Returns the glable status, looking like that:

```json
{
  "slaves": {
    "api": {
      "sources": {
        "master": {
          "hash": "240930ea8580d8392544bc0f42bdd1720b772a46",
          "repo": "/repos/master",
          "type": "git"
        },
        "test_git": {
          "hash": "4e066840860d77b143cbecbb8d23db3b755980b2",
          "repo": "/repos/test_git",
          "template_engines": [
            {
              "environment_variables": { "TEST_ENV": "42" },
              "type": "shell"
            }
          ],
          "type": "git"
        }
      }
    },
    "slave": {
      "sources": {
        "master": {
          "hash": "240930ea8580d8392544bc0f42bdd1720b772a46",
          "repo": "/repos/master",
          "type": "git"
        },
        "test_git": {
          "hash": "4e066840860d77b143cbecbb8d23db3b755980b2",
          "repo": "/repos/test_git",
          "template_engines": [
            {
              "environment_variables": { "TEST_ENV": "42" },
              "type": "shell"
            }
          ],
          "type": "git"
        }
      }
    }
  }
}
```

- `GET {ROUTE_PREFIX}/1/status/{ID}/{KEY}`

Returns the status for the given source ID, looking like that:

```json
{
  "statuses": [
    {
      "hash": "4e066840860d77b143cbecbb8d23db3b755980b2",
      "repo": "/repos/test_git",
      "template_engines": [
        {
          "environment_variables": { "TEST_ENV": "42" },
          "type": "shell"
        }
      ],
      "type": "git"
    }
  ]
}
```

## tarball

- `GET {ROUTE_PREFIX}/1/tarball/{ID}/{KEY}`

Returns a `.tar.gz` containing the current content for the given source.
