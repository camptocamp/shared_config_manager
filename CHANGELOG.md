# Changelog

All notable changes to this project will be documented in this file.

## Unreleased

### Changed

- Grouped slave configuration under `SCM__SLAVE__*` environment variables.

### Fixed

- The source directory on slaves is no longer emptied or partially updated while fetching
  it from the master: the source is fetched and the templates are evaluated in a temporary
  directory, which is then moved atomically in place. Fetches and refreshes of a source are
  also serialized to avoid concurrent corruptions of the source directory.

### Breaking changes

- Renamed environment variables for slave settings:
  - `SCM__API_BASE_URL` -> `SCM__SLAVE__API_BASE_URL`
  - `SCM__TAG_FILTER` -> `SCM__SLAVE__TAG_FILTER`
  - `SCM__TARGET` -> `SCM__SLAVE__TARGET`
  - `SCM__RETRY_NUMBER` -> `SCM__SLAVE__RETRY_NUMBER`
  - `SCM__RETRY_DELAY` -> `SCM__SLAVE__RETRY_DELAY`
  - `SCM__REQUESTS_TIMEOUT` -> `SCM__SLAVE__REQUESTS_TIMEOUT`
  - `SCM__INIT_SOURCES_CONCURRENCY` -> `SCM__SLAVE__INIT_SOURCES_CONCURRENCY`
  - `SCM__IS_SLAVE` -> `SCM__SLAVE__ENABLED`
