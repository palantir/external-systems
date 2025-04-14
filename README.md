# External Systems
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/external-systems)
[![PyPI](https://img.shields.io/pypi/v/external-systems)](https://pypi.org/project/external-systems/)
[![License](https://img.shields.io/badge/License-Apache%202.0-lightgrey.svg)](https://opensource.org/licenses/Apache-2.0)
<a href="https://autorelease.general.dmz.palantir.tech/palantir/external-systems"><img src="https://img.shields.io/badge/Perform%20an-Autorelease-success.svg" alt="Autorelease"></a>

> [!WARNING]
> This SDK is incubating and subject to change.


## About Foundry Sources

The External Systems library is Python SDK built as an interface to reference [Foundry Sources](https://www.palantir.com/docs/foundry/data-connection/set-up-source) from code.

<a id="installation"></a>
## Installation
You can install the Python package using `pip`:

```sh
pip install external-systems
```

<a id="basic-usage"></a>
## Basic Source Usage

### Credentials

Long lived credentials can be referenced using `get_secret()` on the source.

```python
my_source: Source = ...

some_secret = my_source.get_secret("SECRET_NAME")
```

For sources using session credentials we support credentials generation and refresh management. Currently on an S3 source you can access session credentials using `get_aws_credentials()`.

```python
s3_source: Source = ...

refreshable_credentials: Refreshable[AwsCredentials] = s3_source.get_aws_credentials()

session_credentials: AwsCredentials = refreshable_credentials.get()
```

### HTTP Client
For REST based sources, a preconfigured HTTP client is provided built on top of the Python requests library.

```python
source_url = my_source.get_https_connection().url
http_client = my_source.get_https_connection().get_client()

response = http_client.get(source_url + "/api/v1/example/", timeout=10)
```
