# Shared Config Manager

Solves the problem of maintaining configuration volumes in the Docker world.


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

With this example, the config container will contain a `/config/test_git` directory that
is a clone of the `git@github.com:camptocamp/test_git.git` repository and is identified as `test_git`.

You can configure more than one source.

### Common source configuration parameters

* `type`: the type of source
* `key`: the secret key that will be used to trigger a refresh of the source
* `target_dir`: the location where the source will be copied (default to the value of `id` in `/config`)

### GIT source configuration parameters

* `type`: `git`
* `ssh_key`: the private SSH key to use as identity
* `repo`: the GIT repository URL
* `branch`: the GIT branch to use (defaults to `master`)
* `sub_dir`: if only a sub_directory of the repository needs to be copied (defaults to the root of the
  repository)


## Slave only mode

By default the image starts a WSGI server listening on port 8080. In big deployments a full WSGI server
could use a sizeable amount of RAM. So you could have only a couple of such containers and the rest running
as slaves. For that, change the command run by the container to ``


## Tunnings

A few environment variables can be used to tune the containers:

* C2C_REDIS_URL: Must point to a running Redis (typical: `redis://redis:6379`)
* MASTER_CONFIG: The master configuration (string containing the YAML config)
* ROUTE_PREFIX: The prefix to use for the HTTP API (defaults to `/scm`)

See [https://github.com/camptocamp/c2cwsgiutils] for other parameters.


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
    links:
      - redis
    labels:
      io.rancher.container.hostname_override: container_name
      lb.routing_key: scm-${ENVIRONMENT_NAME}
      lb.haproxy_backend.timeout_server: "timeout server 60s"
      lb.haproxy_backend.maxconn: default-server maxconn 1

  scm_slave:
    image: camptocamp/shared_config_manager:latest
    environment: *scm_env
    command: ['/app/shared_config_slave.py']
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


# API

## Refresh

* `GET {ROUTE_PREFIX}/1/refresh/{ID}/{KEY}`

Refresh the given source `{ID}`. Returns 200 in case of success and 500 in case of failure (with some details).

To refresh the master configuration (list of sources), use `master` as ID.

* `POST {ROUTE_PREFIX}/1/refresh/{ID}/{KEY}`

Same as the GET API, but to be used with a GutHub webhook for push events. Will ignore events for other branches.


## Status

* `GET {ROUTE_PREFIX}/1/status`

Returns something like that:

```yaml
{
  "slaves":{
    "scm_api_1":{
      "hostname":"scm_api_1",
      "pid":11,
      "sources":{
        "master":{
          "hash":"9845a1f5a6218915592a8689685a3d4179720f13",
          "id":"master",
          "repo":"/repos/master",
          "type":"git"
        },
        "test_git":{
          "hash":"0af8f099bbbcf6a0ed41333136658b60627e36bd",
          "repo":"/repos/test_git",
          "type":"git"
        }
      }
    }
  }
}
```
