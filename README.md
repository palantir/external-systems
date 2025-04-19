# External Systems

![PyPI - Python Version](https://img.shields.io/pypi/pyversions/external-systems)
[![PyPI](https://img.shields.io/pypi/v/external-systems)](https://pypi.org/project/external-systems/)
[![License](https://img.shields.io/badge/License-Apache%202.0-lightgrey.svg)](https://opensource.org/licenses/Apache-2.0)
<a href="https://autorelease.general.dmz.palantir.tech/palantir/external-systems"><img src="https://img.shields.io/badge/Perform%20an-Autorelease-success.svg" alt="Autorelease"></a>

> [!WARNING]
> This SDK is incubating and subject to change.

## About Foundry Sources

The External Systems library is Python SDK built as an interface to reference [Foundry Sources](https://www.palantir.com/docs/foundry/data-connection/set-up-source) from code.

## Installation

You can install the Python package using `pip`:

```sh
pip install external-systems
```

## Basic Source Usage

### HTTP Client

For REST based sources, a preconfigured HTTP client is provided built on top of the Python requests library. For on-prem systems using [Agent Proxy](https://www.palantir.com/docs/foundry/data-connection/agent-proxy-runtime) the client will be pre-configured with the corresponding proxy

```python
from external_systems.sources import Source, HttpsConnection
from requests import Session

my_source: Source = ...

https_connection: HttpsConnection = my_source.get_https_connection()

source_url: str = https_connection.url
http_client: Session = https_connection.get_client()

response = http_client.get(source_url + "/api/v1/example/", timeout=10)
```

### Secrets

Source secrets can be referenced using `get_secret("<secret_name>")` on the source.

```python
from external_systems.sources import Source

my_source: Source = ...

some_secret: str = my_source.get_secret("SECRET_NAME")
```

For sources using session credentials we support credentials generation and refresh management. Currently on an S3 source you can access session credentials using `get_aws_credentials()`. This method will throw if the source is not pre-configured with `AwsCredentials`

_Session credentials may not be available in all Foundry runtime environments_

```python
from external_systems.sources import Source, Refreshable, AwsCredentials

s3_source: Source = ...

refreshable_credentials: Refreshable[AwsCredentials] = s3_source.get_aws_credentials()

session_credentials: AwsCredentials = refreshable_credentials.get()
```

## On-prem Connectivity with [Foundry Agent Proxy](https://www.palantir.com/docs/foundry/data-connection/agent-proxy-runtime)

### Socket

For non-HTTP connections to external systems that require connections through Foundry's agent proxy, a pre-configured socket is provided.

#### On-Prem SFTP Server Example

For this example we'll be using the [fabric](https://docs.fabfile.org/en/latest/) library

```python
import fabric

from external_systems.sources import Source
from socket import socket

SFTP_HOST = <sftp_host>
SFTP_PORT = <sftp_port>

on_prem_proxied_source: Source = ...

username: str = on_prem_sftp_server.get_secret("username")
password: str = on_prem_sftp_server.get_secret("password")

proxy_socket: socket = source.create_socket(SFTP_HOST, SFTP_PORT)

with fabric.Connection(
    SFTP_HOST,
    user=username,
    port=SFTP_PORT,
    connect_kwargs={
        "password": password,
        "sock": proxy_socket,
    },
) as conn:
    sftp = conn.sftp()
    file_list = sftp.listdir(".")
```

### Authenticated Proxy URI

For more granular use cases a pre-authenticated proxy URI is provided to allow connections to on-prem external systems.

#### Example

We'll be using the [httpx](https://www.python-httpx.org/) library.

```python
import httpx

from external_systems.sources import Source

on_prem_system: Source = ...

authenticated_proxy_uri: str = on_prem_system.get_https_proxy_uri()

with httpx.Client(proxy=authenticated_proxy_uri) as client:
    ...
```
