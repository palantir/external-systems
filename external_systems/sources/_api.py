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

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional, Union


@dataclass(frozen=True)
class ClientCertificate:
    """
    A class representing a client certificate presentable to an external system for authentication
    Attributes:
      pem_certificate (str): PEM certificate contents
      pem_private_key (str): PEM private key contents
    """

    pem_certificate: str
    pem_private_key: str


@dataclass(frozen=True)
class ClientCertificateFilePaths:
    """
    A class holding the paths of the Source's client certificate
    Attributes:
      certificate_file_path (str): Path to the certificate file
      private_key_file_path (str): Path to the private key file
    """

    certificate_file_path: str
    private_key_file_path: str


@dataclass(frozen=True)
class HttpsConnectionParameters:
    """
    A class representing HTTPS connection parameters for an external system.
    Attributes:
      url (str): The base URL of the external system.
      headers (Dict[str, str]): A dictionary containing the auth headers for the connection.
      query_params (Dict[str, str]): A dictionary containing the auth query parameters for the connection.
    """

    url: str
    headers: dict[str, str]
    query_params: dict[str, str]


@dataclass(frozen=True)
class AwsCredentials:
    access_key_id: str
    secret_access_key: str
    session_token: Optional[str] = None
    expiration: Optional[datetime] = None


# Each new credential type must include an expiration field
SourceCredentials = Union[AwsCredentials]


@dataclass(frozen=True)
class SourceParameters:
    """
    A class representing source parameters for an external system.
    Attributes:
      secrets (Dict[str, str]): A dictionary containing the secrets contained on the source.
      proxy_token (Optional[str]): The token for authenticating with the on-prem-proxy service.
      https_connections (Dict[str, HttpsConnection]): A dictionary containing the https connections on the Source.
      server_certificates (Dict[str, str]): A dictionary containing the server certificates for the source.
      client_certificate Optional[ClientCertificate]: The client certificate configured on the source.
      resolved_source_credentials (Optional[SourceCredentials]): If session credentials are used, this field will contain the resolved credentials.
    """

    secrets: Dict[str, str]
    proxy_token: Optional[str]
    https_connections: Dict[str, HttpsConnectionParameters]
    server_certificates: Dict[str, str]
    client_certificate: Optional[ClientCertificate]
    resolved_source_credentials: Optional[SourceCredentials]
