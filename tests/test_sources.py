#  Copyright 2025 Palantir Technologies, Inc.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

from tempfile import NamedTemporaryFile
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from frozendict import frozendict

from external_systems.sources import (
    AwsCredentials,
    ClientCertificate,
    HttpsConnectionParameters,
    SourceCredentials,
    SourceParameters,
)
from external_systems.sources._refreshable import DefaultSessionCredentialsManager, RefreshHandler
from external_systems.sources._sources import Source


@pytest.fixture
def source_params() -> SourceParameters:
    return SourceParameters(
        secrets={"SecretApiName": "my-raw-secret-value"},
        https_connections={
            "default": HttpsConnectionParameters(
                url="https://example.com",
                headers={"header": "header_value"},
                query_params={"query_param": "query_param_value"},
            )
        },
        client_certificate=ClientCertificate(pem_certificate="cert", pem_private_key="key"),
        proxy_token="on-prem-proxy-token",
        server_certificates={"my_server_ca": "server_ca_value"},
        resolved_source_credentials=AwsCredentials(
            access_key_id="access-key",
            secret_access_key="secret",
        ),
    )


@pytest.fixture
def egress_proxy_token() -> str:
    return "egress-proxy-token"


@pytest.fixture
def egress_proxy_uris() -> list[str]:
    return ["https://palantirfoundry.com/egress-proxy/api"]


@pytest.fixture
def on_prem_proxy_uris() -> list[str]:
    return ["https://palantirfoundry.com/on-prem-proxy/api"]


@pytest.fixture
def source_configuration() -> Any:
    return {
        "type": "s3",
        "bucket_url": "bucket-url",
    }


@pytest.fixture
def mock_refresh_handler() -> RefreshHandler[SourceCredentials]:
    return MagicMock(spec=RefreshHandler)


@patch("external_systems.sources._sources.create_proxy_session")
def test_get_proxy_session_on_prem_proxy(
    mock_create_proxy_session: MagicMock, source_params: SourceParameters, on_prem_proxy_uris: list[str]
) -> None:
    source = Source(source_params, on_prem_proxy_uris, [], None, None)
    proxy_session = source._proxy_session
    mock_create_proxy_session.assert_called_once_with(
        "https://palantirfoundry.com/on-prem-proxy/api", "on-prem-proxy-token"
    )
    assert proxy_session is not None


@patch("external_systems.sources._sources.create_proxy_session")
def test_get_proxy_session_egress_proxy(
    mock_create_proxy_session: MagicMock,
    source_params: SourceParameters,
    egress_proxy_token: str,
    egress_proxy_uris: list[str],
) -> None:
    source_params_no_proxy_token = SourceParameters(
        secrets=source_params.secrets,
        https_connections=source_params.https_connections,
        client_certificate=source_params.client_certificate,
        proxy_token=None,
        server_certificates=source_params.server_certificates,
        resolved_source_credentials=source_params.resolved_source_credentials,
    )
    source = Source(source_params_no_proxy_token, [], egress_proxy_uris, egress_proxy_token, None)
    proxy_session = source._proxy_session
    mock_create_proxy_session.assert_called_once_with(
        "https://user:egress-proxy-token@palantirfoundry.com/egress-proxy/api", "egress-proxy-token"
    )
    assert proxy_session is not None


def test_get_proxy_session_no_proxy_configured(source_params: SourceParameters) -> None:
    source_params_no_proxy_token = SourceParameters(
        secrets=source_params.secrets,
        https_connections=source_params.https_connections,
        client_certificate=source_params.client_certificate,
        proxy_token=None,
        server_certificates=source_params.server_certificates,
        resolved_source_credentials=source_params.resolved_source_credentials,
    )
    source = Source(source_params_no_proxy_token, [], [], None, None)
    with pytest.raises(
        ValueError, match="neither egress proxy nor on-prem proxy were configured. unable to construct a proxy session"
    ):
        _ = source._proxy_session


def test_get_https_proxy_url_on_prem_proxy(source_params: SourceParameters, on_prem_proxy_uris: list[str]) -> None:
    source = Source(source_params, on_prem_proxy_uris, [], None, None)
    https_proxy_url = source._https_proxy_url
    assert https_proxy_url == "https://user:on-prem-proxy-token@palantirfoundry.com/on-prem-proxy/api"


def test_get_https_proxy_url_egress_proxy(
    source_params: SourceParameters, egress_proxy_token: str, egress_proxy_uris: list[str]
) -> None:
    source_params_no_proxy_token = SourceParameters(
        secrets=source_params.secrets,
        https_connections=source_params.https_connections,
        client_certificate=source_params.client_certificate,
        proxy_token=None,
        server_certificates=source_params.server_certificates,
        resolved_source_credentials=source_params.resolved_source_credentials,
    )
    source = Source(source_params_no_proxy_token, [], egress_proxy_uris, egress_proxy_token, None)
    https_proxy_url = source._https_proxy_url
    assert https_proxy_url == "https://user:egress-proxy-token@palantirfoundry.com/egress-proxy/api"


def test_get_https_proxy_url_no_proxy(source_params: SourceParameters) -> None:
    source_params_no_proxy_token = SourceParameters(
        secrets=source_params.secrets,
        https_connections=source_params.https_connections,
        client_certificate=source_params.client_certificate,
        proxy_token=None,
        server_certificates=source_params.server_certificates,
        resolved_source_credentials=source_params.resolved_source_credentials,
    )
    source = Source(source_params_no_proxy_token, [], [], None, None)
    https_proxy_url = source._https_proxy_url
    assert https_proxy_url is None


def test_ca_bundle_path_creation_for_server_certificates_with_default_ca_configured(
    source_params: SourceParameters, on_prem_proxy_uris: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    with NamedTemporaryFile(delete=False, mode="w") as default_ca:
        default_ca.write("default_ca_value")
        monkeypatch.setenv("REQUESTS_CA_BUNDLE", default_ca.name)

    source = Source(source_params, on_prem_proxy_uris, [], None, None)
    ca_bundle_path = source.server_certificates_path

    assert ca_bundle_path is not None
    with open(ca_bundle_path) as f:
        ca_contents = f.read()
        assert ca_contents == "default_ca_value\nserver_ca_value\n"


def test_ca_bundle_path_creation_for_server_certificates_with_no_default_ca_configured(
    source_params: SourceParameters, on_prem_proxy_uris: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)

    source = Source(source_params, on_prem_proxy_uris, [], None, None)
    ca_bundle_path = source.server_certificates_path

    assert ca_bundle_path is not None
    with open(ca_bundle_path) as f:
        ca_contents = f.read()
        assert ca_contents == "server_ca_value\n"


def test_ca_bundle_path_creation_for_server_certificates_uses_custom_ca_bundle_path(
    source_params: SourceParameters, on_prem_proxy_uris: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)
    with NamedTemporaryFile(delete=False, mode="w") as default_ca:
        default_ca.write("my_ca_value\n")

    source = Source(source_params, on_prem_proxy_uris, [], None, None, ca_bundle_path=default_ca.name)
    ca_bundle_path = source.server_certificates_path

    assert ca_bundle_path is not None
    with open(ca_bundle_path) as f:
        ca_contents = f.read()
        assert ca_contents == "my_ca_value\n\nserver_ca_value\n"


def test_ca_bundle_path_creation_does_not_use_requests_ca_bundle_if_custom_ca_bundle_configured(
    source_params: SourceParameters, on_prem_proxy_uris: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    with NamedTemporaryFile(delete=False, mode="w") as requests_ca_bundle:
        requests_ca_bundle.write("requests_ca_bundle_value\n")
        monkeypatch.setenv("REQUESTS_CA_BUNDLE", requests_ca_bundle.name)

    with NamedTemporaryFile(delete=False, mode="w") as default_ca:
        default_ca.write("default_ca_value\n")

    source = Source(source_params, on_prem_proxy_uris, [], None, None, ca_bundle_path=default_ca.name)
    ca_bundle_path = source.server_certificates_path

    assert ca_bundle_path is not None
    with open(ca_bundle_path) as f:
        ca_contents = f.read()
        assert ca_contents == "default_ca_value\n\nserver_ca_value\n"


@patch("external_systems.sources._sources.create_socket")
def test_create_socket(
    mock_create_socket: MagicMock,
    source_params: SourceParameters,
    on_prem_proxy_uris: list[str],
    egress_proxy_uris: list[str],
    egress_proxy_token: str,
) -> None:
    source = Source(source_params, on_prem_proxy_uris, egress_proxy_uris, egress_proxy_token, None)
    socket = source.create_socket("target-host", 443)
    mock_create_socket.assert_called_once_with(
        "https://user:on-prem-proxy-token@palantirfoundry.com/on-prem-proxy/api", "target-host", 443, None
    )
    assert socket is not None


@patch("external_systems.sources._sources.create_socket")
def test_create_socket_with_custom_ca_bundle_uses_custom_ca_bundle(
    mock_create_socket: MagicMock,
    source_params: SourceParameters,
    on_prem_proxy_uris: list[str],
    egress_proxy_uris: list[str],
    egress_proxy_token: str,
) -> None:
    source = Source(
        source_params,
        on_prem_proxy_uris,
        egress_proxy_uris,
        egress_proxy_token,
        None,
        ca_bundle_path="custom-ca-bundle-path",
    )
    socket = source.create_socket("target-host", 443)
    mock_create_socket.assert_called_once_with(
        "https://user:on-prem-proxy-token@palantirfoundry.com/on-prem-proxy/api",
        "target-host",
        443,
        "custom-ca-bundle-path",
    )
    assert socket is not None


def test_create_socket_no_proxy(source_params: SourceParameters) -> None:
    source_params_no_proxy_token = SourceParameters(
        secrets=source_params.secrets,
        https_connections=source_params.https_connections,
        client_certificate=source_params.client_certificate,
        proxy_token=None,
        server_certificates=source_params.server_certificates,
        resolved_source_credentials=source_params.resolved_source_credentials,
    )
    source = Source(source_params_no_proxy_token, [], [], None, None)
    with pytest.raises(ValueError, match="Only usable with Agent Proxy Sources"):
        _ = source.create_socket("target-host", 443)


def test_get_valid_secret(
    source_params: SourceParameters,
    on_prem_proxy_uris: list[str],
    egress_proxy_uris: list[str],
    egress_proxy_token: str,
) -> None:
    source = Source(source_params, on_prem_proxy_uris, egress_proxy_uris, egress_proxy_token, None)
    secret = source.get_secret("SecretApiName")
    assert secret == "my-raw-secret-value"


def test_get_invalid_secret(
    source_params: SourceParameters,
    on_prem_proxy_uris: list[str],
    egress_proxy_uris: list[str],
    egress_proxy_token: str,
) -> None:
    source = Source(source_params, on_prem_proxy_uris, egress_proxy_uris, egress_proxy_token, None)
    with pytest.raises(ValueError, match="Secret with name MadeUpSecret not found on the Source."):
        _ = source.get_secret("MadeUpSecret")


def test_single_https_connection_source_succeeds(
    source_params: SourceParameters,
    on_prem_proxy_uris: list[str],
    egress_proxy_uris: list[str],
    egress_proxy_token: str,
) -> None:
    source = Source(source_params, on_prem_proxy_uris, egress_proxy_uris, egress_proxy_token, None)
    https_connection = source.get_https_connection()
    assert https_connection is not None


def test_multiple_https_connections_source_fails(
    source_params: SourceParameters,
    on_prem_proxy_uris: list[str],
    egress_proxy_uris: list[str],
    egress_proxy_token: str,
) -> None:
    source_params_multiple_connections = SourceParameters(
        secrets=source_params.secrets,
        https_connections={
            "default": HttpsConnectionParameters(url="https://example.com", headers={}, query_params={}),
            "another": HttpsConnectionParameters(url="https://another.com", headers={}, query_params={}),
        },
        client_certificate=source_params.client_certificate,
        proxy_token=source_params.proxy_token,
        server_certificates=source_params.server_certificates,
        resolved_source_credentials=source_params.resolved_source_credentials,
    )
    source = Source(source_params_multiple_connections, on_prem_proxy_uris, egress_proxy_uris, egress_proxy_token, None)
    with pytest.raises(ValueError, match="Only single connection sources are supported."):
        _ = source.get_https_connection()


def test_maybe_refreshable_resolved_source_credentials_with_credentials(
    source_params: SourceParameters, mock_refresh_handler: RefreshHandler[SourceCredentials]
) -> None:
    source = Source(source_params, [], [], None, None, credentials_refresh_handler=mock_refresh_handler)

    with patch.object(DefaultSessionCredentialsManager, "__init__", return_value=None) as mock_init:
        result = source._maybe_refreshable_resolved_source_credentials
        mock_init.assert_called_once_with(source_params.resolved_source_credentials, mock_refresh_handler)
        assert isinstance(result, DefaultSessionCredentialsManager)


def test_maybe_refreshable_resolved_source_credentials_without_credentials(
    mock_refresh_handler: RefreshHandler[SourceCredentials],
) -> None:
    source_params_without_creds = SourceParameters(
        secrets={},
        https_connections={},
        client_certificate=None,
        proxy_token=None,
        server_certificates={},
        resolved_source_credentials=None,
    )

    source = Source(source_params_without_creds, [], [], None, None, credentials_refresh_handler=mock_refresh_handler)
    result = source._maybe_refreshable_resolved_source_credentials
    assert result is None


def test_get_aws_credentials_invokes_refreshable(
    source_params: SourceParameters,
    on_prem_proxy_uris: list[str],
    egress_proxy_uris: list[str],
    egress_proxy_token: str,
) -> None:
    source = Source(source_params, on_prem_proxy_uris, egress_proxy_uris, egress_proxy_token, None)
    aws_credentials = source.get_aws_credentials()
    assert aws_credentials is not None


def test_get_aws_credentials_no_resolved_source_credentials(
    source_params: SourceParameters,
    on_prem_proxy_uris: list[str],
    egress_proxy_uris: list[str],
    egress_proxy_token: str,
) -> None:
    source_params_no_credentials = SourceParameters(
        secrets=source_params.secrets,
        https_connections=source_params.https_connections,
        client_certificate=source_params.client_certificate,
        proxy_token=source_params.proxy_token,
        server_certificates=source_params.server_certificates,
        resolved_source_credentials=None,
    )
    source = Source(source_params_no_credentials, on_prem_proxy_uris, egress_proxy_uris, egress_proxy_token, None)
    with pytest.raises(ValueError, match="Resolved source credentials are not present on the Source."):
        _ = source.get_aws_credentials()


def test_get_source_url(
    source_params: SourceParameters,
    on_prem_proxy_uris: list[str],
    egress_proxy_uris: list[str],
    egress_proxy_token: str,
) -> None:
    source = Source(source_params, on_prem_proxy_uris, egress_proxy_uris, egress_proxy_token, None)
    url = source.get_https_connection().url
    assert url == "https://example.com"


def test_source_headers(
    source_params: SourceParameters,
    on_prem_proxy_uris: list[str],
    egress_proxy_uris: list[str],
    egress_proxy_token: str,
) -> None:
    source = Source(source_params, on_prem_proxy_uris, egress_proxy_uris, egress_proxy_token, None)
    headers = source.get_https_connection().headers
    assert headers == frozendict({"header": "header_value"})


def test_source_query_params(
    source_params: SourceParameters,
    on_prem_proxy_uris: list[str],
    egress_proxy_uris: list[str],
    egress_proxy_token: str,
) -> None:
    source = Source(source_params, on_prem_proxy_uris, egress_proxy_uris, egress_proxy_token, None)
    query_params = source.get_https_connection().query_params
    assert query_params == frozendict({"query_param": "query_param_value"})


def test_source_config_throws_on_invalid_client(source_params: SourceParameters) -> None:
    source = Source(source_params, [], [], None, None)
    with pytest.raises(ValueError, match="Source configuration is not available for this Source."):
        _ = source.source_configuration


def test_source_config_returns_expected_config_from_client(
    source_params: SourceParameters, source_configuration: Any
) -> None:
    source = Source(source_params, [], [], None, source_configuration)
    assert source.source_configuration == {
        "type": "s3",
        "bucket_url": "bucket-url",
    }


def test_client_certificate_correctly_persists_cert(source_params: SourceParameters) -> None:
    source = Source(source_params, [], [], None, None)

    assert source.client_certificate is not None
    with open(source.client_certificate.certificate_file_path, "r") as f:
        assert f.read() == "cert"
    with open(source.client_certificate.private_key_file_path, "r") as f:
        assert f.read() == "key"
