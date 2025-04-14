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

from typing import Mapping, Optional, Tuple

from frozendict import frozendict
from requests import Session

from ._api import HttpsConnectionParameters
from ._proxies import create_session


class HttpsConnection:
    """
    A class representing an HTTPS connection for an external system.
    """

    def __init__(
        self,
        connection_parameters: HttpsConnectionParameters,
        client_certificate: Optional[Tuple[str, str]] = None,
        proxy_uri_with_auth: Optional[str] = None,
        ca_bundle_path: Optional[str] = None,
    ):
        self._client_certificate = client_certificate
        self._headers = frozendict(connection_parameters.headers)
        self._url = connection_parameters.url
        self._query_params = frozendict(connection_parameters.query_params)
        self._proxies = frozendict({"https": proxy_uri_with_auth}) if proxy_uri_with_auth is not None else None
        self._ca_bundle_path = ca_bundle_path

    def get_client(self, timeout: int = 30) -> Session:
        """Get the HTTP client for this connection.
          This client must be used in order to reach the external system.
        Args:
            timeout (int, optional): The request timeout in seconds. Defaults to 30.
        Returns:
            requests.Session: A configured requests.Session object for communicating with the external system.
        """

        return create_session(
            cert=self._client_certificate,
            ca_bundle_path=self._ca_bundle_path,
            headers=self._headers,
            user_agent="external-systems",
            proxies=self._proxies,
            timeout=timeout,
        )

    @property
    def headers(self) -> Mapping[str, str]:
        return self._headers

    @property
    def query_params(self) -> Mapping[str, str]:
        return self._query_params

    @property
    def url(self) -> str:
        return self._url
