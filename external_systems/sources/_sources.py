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

import logging
import os
import random
import socket
from functools import cached_property
from tempfile import NamedTemporaryFile
from typing import Any, Mapping, Optional, Tuple

import urllib3.util
from frozendict import frozendict
from requests import Session

from ._api import AwsCredentials, ClientCertificateFilePaths, SourceCredentials, SourceParameters
from ._connections import HttpsConnection
from ._proxies import create_proxy_session
from ._refreshable import DefaultSessionCredentialsManager, Refreshable, RefreshHandler
from ._sockets import create_socket
from ._utils import read_file

log = logging.getLogger(__name__)


class Source:
    """
    A class representing a Source for an external systems.
    """

    def __init__(
        self,
        source_parameters: SourceParameters,
        on_prem_proxy_service_uris: list[str],
        egress_proxy_service_uris: list[str],
        egress_proxy_token: Optional[str],
        source_configuration: Optional[Any],
        credentials_refresh_handler: Optional[RefreshHandler[SourceCredentials]] = None,
        ca_bundle_path: Optional[str] = None,
    ):
        self._source_parameters = source_parameters
        self._on_prem_proxy_service_uris = on_prem_proxy_service_uris
        self._egress_proxy_service_uris = egress_proxy_service_uris
        self._source_configuration = source_configuration
        self._egress_proxy_token = egress_proxy_token
        self._credentials_refresh_handler = credentials_refresh_handler
        self._custom_ca_bundle_path = ca_bundle_path

    @cached_property
    def secrets(self) -> Mapping[str, str]:
        """A dictionary containing plaintext secrets on the Source keyed by secret API name."""
        return frozendict(self._source_parameters.secrets)

    @property
    def client_certificate(self) -> Optional[ClientCertificateFilePaths]:
        """
        The client certificate file name and private key file name if present on the Source.
        Returns:
            Optional[ClientCertificateFilePaths]: If a client certificate is present on the source, otherwise None.
        """
        return ClientCertificateFilePaths(*self._client_certificate) if self._client_certificate is not None else None

    @cached_property
    def _https_connections(self) -> Mapping[str, HttpsConnection]:
        return frozendict(
            {
                key: HttpsConnection(params, self._client_certificate, self._https_proxy_url, self._ca_bundle_path)
                for key, params in self._source_parameters.https_connections.items()
            }
        )

    @cached_property
    def _ca_bundle_path(self) -> Optional[str]:
        if self._source_parameters.server_certificates is None:
            return None

        new_ca_contents = []

        # If a custom CA bundle path is provided, use it.
        # Otherwise, use the requests CA bundle path if it is set.
        ca_bundle_path = (
            self._custom_ca_bundle_path
            if self._custom_ca_bundle_path is not None
            else os.environ.get("REQUESTS_CA_BUNDLE")
        )

        # Copy the CA bundle contents to the new CA bundle file.
        if ca_bundle_path:
            new_ca_contents.append(read_file(ca_bundle_path))

        # Add all CAs for the source
        for required_ca in self._source_parameters.server_certificates.values():
            new_ca_contents.append(required_ca)

        with NamedTemporaryFile(delete=False, mode="w") as ca_bundle_file:
            ca_bundle_file.write(os.linesep.join(new_ca_contents) + os.linesep)
            return ca_bundle_file.name

    @cached_property
    def _client_certificate(self) -> Optional[Tuple[str, str]]:
        if self._source_parameters.client_certificate is None:
            return None

        cert_file = NamedTemporaryFile(delete=False, mode="w")  # pylint: disable=consider-using-with
        cert_file.write(self._source_parameters.client_certificate.pem_certificate)

        private_key_file = NamedTemporaryFile(delete=False, mode="w")  # pylint: disable=consider-using-with
        private_key_file.write(self._source_parameters.client_certificate.pem_private_key)

        return cert_file.name, private_key_file.name

    @cached_property
    def _proxy_session(self) -> Session:
        egress_proxy_configured = self._egress_proxy_token is not None
        on_prem_proxy_configured = self._source_parameters.proxy_token is not None

        if on_prem_proxy_configured:
            if egress_proxy_configured:
                log.warning(
                    "both egress proxy and on-prem proxy are configured for this source. preferring on-prem proxy"
                )
            if len(self._on_prem_proxy_service_uris) == 0:
                raise ValueError(
                    "on-prem proxy was configured for this source, but on-prem proxy URIs were not present"
                )
            return create_proxy_session(
                random.choice(self._on_prem_proxy_service_uris), self._source_parameters.proxy_token
            )
        elif egress_proxy_configured:
            # we checked this earlier, but assert again here to make mypy happy
            assert (
                self._egress_proxy_token is not None
            ), "no egress proxy parameters found while configuring egress proxy session"
            if len(self._egress_proxy_service_uris) == 0:
                raise ValueError("egress proxy was configured for this source, but egress proxy URIs were not present")
            return create_proxy_session(self._https_proxy_url, self._egress_proxy_token)
        else:
            raise ValueError(
                "neither egress proxy nor on-prem proxy were configured. unable to construct a proxy session"
            )

    @cached_property
    def _https_proxy_url(self) -> Optional[str]:
        if self._source_parameters.proxy_token is not None:
            parsed = urllib3.util.parse_url(random.choice(self._on_prem_proxy_service_uris))
            parsed = parsed._replace(auth=f"user:{self._source_parameters.proxy_token}")
            return parsed.url

        if self._egress_proxy_token is not None:
            parsed = urllib3.util.parse_url(random.choice(self._egress_proxy_service_uris))
            parsed = parsed._replace(auth=f"user:{self._egress_proxy_token}")
            return parsed.url

        return None

    @cached_property
    def _maybe_refreshable_resolved_source_credentials(self) -> Optional[Refreshable[SourceCredentials]]:
        if self._source_parameters.resolved_source_credentials is None:
            return None

        return DefaultSessionCredentialsManager(
            self._source_parameters.resolved_source_credentials, self._credentials_refresh_handler
        )

    @cached_property
    def source_configuration(self) -> Any:
        """
        Full configuration of the Source.
        Throws if source configuration is not supported by public API.
        """
        if self._source_configuration is None:
            raise ValueError("Source configuration is not available for this Source.")
        return self._source_configuration

    def get_aws_credentials(self) -> Refreshable[AwsCredentials]:
        """
        Get the AWS credentials from the Source.

        Supported Sources:
            - S3
        """
        if self._maybe_refreshable_resolved_source_credentials is None:
            raise ValueError("Resolved source credentials are not present on the Source.")
        if not isinstance(self._maybe_refreshable_resolved_source_credentials.get(), AwsCredentials):
            raise ValueError("Resolved source credentials are not of type AwsCredentials.")
        return self._maybe_refreshable_resolved_source_credentials

    def get_secret(self, key: str) -> str:
        """Get the plaintext value for the provided secret key, as configured in the Source secrets."""
        secret = self.secrets.get(key)
        if not secret:
            raise ValueError(f"Secret with name {key} not found on the Source.")
        return secret

    def get_https_connection(self) -> HttpsConnection:
        """Get the HTTPS Connection from the Source.
        Raises:
            ValueError: If there are multiple connections on the source.
        Returns:
            HttpsConnection: The requested HttpsConnection object.
        """

        if len(self._https_connections) != 1:
            raise ValueError("Only single connection sources are supported.")
        return next(iter(self._https_connections.values()))

    def get_https_proxy_uri(self) -> Optional[str]:
        """Get the HTTPS proxy URI that must be used to communicate with the external system
        when using an Agent Proxy source.
        The format of the proxy URI will be "https://user:password@proxy-server.com:443".
        If a proxy is not required, the function will return None.
        This is useful if you can't use the provided requests client and need to use a different HTTP client or an SDK.
        """
        return self._https_proxy_url

    def create_socket(self, target_host: str, target_port: int) -> socket.socket:  # pylint: disable=too-many-locals
        """
        Create a socket connection to the host and port in the HTTPS connection through the Agent Proxy.
        The socket returned by this method MUST be closed by the caller to avoid hanging connections in the proxy.
        It is recommended to use the `contextlib.closing` context manager to ensure the socket is closed:
            from contextlib import closing
            with closing(source.create_socket(target_host, target_port)) as sock:
                # Use the socket here
        Returns:
            socket.socket: A socket object connected to the target host and port through the HTTPS proxy.
        Raises:
            ValueError: If the configured proxy is not an HTTPS proxy or if the tunnel cannot be established.
            RuntimeError: If there is a failure during socket creation.
        """
        if not self._https_proxy_url:
            raise ValueError("Only usable with Agent Proxy Sources")

        return create_socket(self._https_proxy_url, target_host, target_port, self._custom_ca_bundle_path)
