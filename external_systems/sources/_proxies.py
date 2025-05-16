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

import os
from functools import cache
from typing import Any, Mapping, Optional, Union

from requests import PreparedRequest, Response, Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class CustomCaBundleSession(Session):
    """
    A wrapper for requests.Session to override 'verify' property, ignoring REQUESTS_CA_BUNDLE environment variable.

    This is a workaround for https://github.com/psf/requests/issues/3829 (will be fixed in requests 3.0.0)
    """

    def merge_environment_settings(self, url, proxies, stream, verify, *args, **kwargs):  # type: ignore[no-untyped-def]
        if isinstance(self.verify, str) and os.path.exists(self.verify):
            verify = self.verify

        return super(CustomCaBundleSession, self).merge_environment_settings(
            url, proxies, stream, verify, *args, **kwargs
        )


class RetryingTimeoutHttpAdapter(HTTPAdapter):
    def __init__(
        self,
        *args: Any,
        timeout: Optional[Union[float, tuple[float, float], tuple[float, None]]] = None,
        retries: Optional[Union[Retry, int]] = None,
        **kwargs: Any,
    ):
        self._timeout = timeout
        retries = retries or Retry(total=10, backoff_factor=0.1, status_forcelist=[503])
        super().__init__(*args, max_retries=retries, **kwargs)  # type: ignore[misc]

    def send(
        self,
        request: PreparedRequest,
        stream: bool = False,
        timeout: Optional[Union[float, tuple[float, float], tuple[float, None]]] = None,
        verify: Union[bool, str] = True,
        cert: Optional[Union[bytes, str, tuple[Union[bytes, str], Union[bytes, str]]]] = None,
        proxies: Optional[Mapping[str, str]] = None,
    ) -> Response:
        if timeout is None:
            timeout = self._timeout
        return super().send(request, stream=stream, timeout=timeout, verify=verify, cert=cert, proxies=proxies)

    def __getstate__(self) -> Any:
        state: dict[str, Any] = super().__getstate__()  # type: ignore
        # The HTTPAdapter superclass overrides the __getstate__ method to serialize only selective fields.
        # Any fields specific to this class must be added here so that these fields will be preserved after being
        # pickled/unpickled.
        state["_timeout"] = self._timeout
        return state


class ProxyAdapter(HTTPAdapter):
    def __init__(self, *args: Any, proxy_auth: dict[str, str], **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._proxy_auth = proxy_auth

    def proxy_headers(self, proxy: str) -> dict[str, str]:
        return {"Proxy-Authorization": self._proxy_auth[proxy]}

    def __getstate__(self) -> Any:
        state: dict[str, Any] = super().__getstate__()  # type: ignore
        # The HTTPAdapter superclass overrides the __getstate__ method to serialize only selective fields.
        # Any fields specific to this class must be added here so that these fields will be preserved after being
        # pickled/unpickled.
        state["_proxy_auth"] = self._proxy_auth
        return state


@cache
def create_proxy_session(proxy_url: str, proxy_token: str) -> Session:
    """
    Create a session with proxy authentication.
    Args:
        proxy_url (str): The URL of the proxy server.
        proxy_token (str): The token for authenticating with the proxy server.
    Returns:
        Session: A requests session with proxy authentication.
    """

    adapter = ProxyAdapter(proxy_auth={proxy_url: f"Bearer {proxy_token}"})
    session = CustomCaBundleSession()
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.proxies = {"all": proxy_url}
    return session


@cache
def create_session(
    cert: Optional[Union[str, tuple[str, str]]] = None,
    ca_bundle_path: Optional[str] = None,
    headers: Optional[dict[str, str]] = None,
    user_agent: Optional[str] = None,
    proxies: Optional[dict[str, str]] = None,
    timeout: Optional[Union[float, tuple[float, float], tuple[float, None]]] = None,
) -> Session:
    """
    Create a session with optional client certificate and CA bundle path.
    Args:
        cert (Optional[Union[str, tuple[str, str]]]): The client certificate to use for authentication.
        ca_bundle_path (Optional[str]): The path to the CA bundle file.
        headers (Optional[dict[str, str]]): Additional headers to include in the request.
        user_agent (Optional[str]): The User-Agent header value.
        proxies (Optional[dict[str, str]]): Proxies to use for the session.
        timeout (Optional[Union[float, tuple[float, float], tuple[float, None]]]): Timeout settings for the session.
    """

    session = CustomCaBundleSession()

    if cert:
        session.cert = cert

    if ca_bundle_path:
        session.verify = ca_bundle_path

    adapter = RetryingTimeoutHttpAdapter(timeout=timeout)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    if headers:
        session.headers.update(headers)

    if user_agent:
        session.headers["User-Agent"] = user_agent

    if proxies:
        session.proxies = proxies

    return session
