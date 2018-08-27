# Shared Config Manager

Solves the problem of maintaining configuration volumes in the Docker world.


## Configuration

First you need to configure the source for the master configuration using the
`MASTER_CONFIG` environment variable with something like:

```yaml
env:
    MASTER_CONFIG: |
      type: git
      id: master
      key: changeme
      repo: git@github.com:camptocamp/master_config.git
```

That will use the `shared_config_manager.yaml` file at the root of the repository
to configure all the sources. This configuration file looks like that:

```yaml
sources:
  - id: test_git
    type: git
    repo: git@github.com:camptocamp/test_git.git
    key: changeme
    target_dir: /usr/local/tomcat/webapps/ROOT/print-apps
```

With this example, the config container will contain a `/config/test_git` directory that
is a clone of the `git@github.com:camptocamp/test_git.git` repository.

You can configure more than one source.

### Common source configuration parameters

* `type`: the type of source
* `id`: the id of the source, must be unique
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


## Example docker-compose for Rancher

docker-compose.yaml:

```yaml
version: '2'
services:
  scm_api:
    image: camptocamp/shared_config_manager:latest
    environment: &scm_env
      C2C_REDIS_URL: redis://redis:6379
      C2C_BROADCAST_PREFIX: &broadcast_prefix broadcast_api_
      MASTER_CONFIG: &master_config |
        type: git
        id: master
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
