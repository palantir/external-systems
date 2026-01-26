# `external-systems` dev README

[![Autorelease](https://img.shields.io/badge/Perform%20an-Autorelease-success.svg)](https://autorelease.general.dmz.palantir.tech/palantir/external-systems)

## Requirements

* python >= 3.10
* [poetry](https://python-poetry.org/docs/)

## Commands

### Install packages + scripts

This command will install all deps specified in `pyproject.toml` and make the scripts specified in `pyproject.toml` available in your python environment.

```sh
poetry install
```

### Run tests
```sh
poetry run poe test
```

### Run `mypy` checks
```sh
poetry run poe check_mypy
```

### Run linter checks (black, ruff, isort)
This will run the same checks as those that are run during CI checks - meaning it will raise any issues found, but not fix them.

```sh
poetry run poe check_format
```

### Run formatter (black, ruff, isort)
This will actually modify source files to fix any issues identified
```sh
poetry run poe format
```

### Build the library locally

```sh
poetry build
```

This will produce a `tar.gz` and a `whl` file in the `./dist` directory.

### Locally testing proxy behavior

1. Download `envoy` proxy (`brew install envoy` on MacOS)
2. Configure as an HTTP CONNECT proxy
```yaml
# envoy.yaml
static_resources:
  listeners:
  - name: listener_0
    address:
      socket_address:
        address: 0.0.0.0
        port_value: 8080
    filter_chains:
    - filters:
      - name: envoy.filters.network.http_connection_manager
        typed_config:
          "@type": type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager
          stat_prefix: ingress_http
          access_log:
          - name: envoy.access_loggers.stdout
            typed_config:
              "@type": type.googleapis.com/envoy.extensions.access_loggers.stream.v3.StdoutAccessLog
          http_filters:
          - name: envoy.filters.http.dynamic_forward_proxy
            typed_config:
              "@type": type.googleapis.com/envoy.extensions.filters.http.dynamic_forward_proxy.v3.FilterConfig
              dns_cache_config:
                name: dynamic_forward_proxy_cache_config
                dns_lookup_family: V4_ONLY
          - name: envoy.filters.http.router
            typed_config:
              "@type": type.googleapis.com/envoy.extensions.filters.http.router.v3.Router
          route_config:
            name: local_route
            virtual_hosts:
            - name: all
              domains: ["*"]
              routes:
              - match:
                  connect_matcher: {}
                route:
                  cluster: dynamic_forward_proxy_cluster
                  upgrade_configs:
                  - upgrade_type: CONNECT
                    connect_config: {}
              - match:
                  prefix: "/"
                route:
                  cluster: dynamic_forward_proxy_cluster

  clusters:
  - name: dynamic_forward_proxy_cluster
    connect_timeout: 5s
    lb_policy: CLUSTER_PROVIDED
    cluster_type:
      name: envoy.clusters.dynamic_forward_proxy
      typed_config:
        "@type": type.googleapis.com/envoy.extensions.clusters.dynamic_forward_proxy.v3.ClusterConfig
        dns_cache_config:
          name: dynamic_forward_proxy_cache_config
          dns_lookup_family: V4_ONLY

admin:
  address:
    socket_address:
      address: 127.0.0.1
      port_value: 9901
```
3. Run the proxy `envoy -c envoy.yaml --log-level debug`
4. Initialize a source with the proxy
```python
#!/usr/bin/env python3
"""
Test script to initialize a Source with Envoy Connect proxy as egress proxy.
"""

from external_systems.sources._api import HttpsConnectionParameters, SourceParameters
from external_systems.sources._sources import Source

https_connection = HttpsConnectionParameters(
    url="https://httpbin.org",
    headers={"X-Test-Header": "test-value"},
    query_params={},
)

source_params = SourceParameters(
    secrets={"api_key": "test-secret"},
    proxy_token=None,
    https_connections={"default": https_connection},
    server_certificates={},
    client_certificate=None,
    resolved_source_credentials=None,
)

source = Source(
    source_parameters=source_params,
    on_prem_proxy_service_uris=[],
    egress_proxy_service_uris=["http://localhost:8080"],  # Envoy proxy
    egress_proxy_token="dummy-token",
    source_configuration=None,
)
```
