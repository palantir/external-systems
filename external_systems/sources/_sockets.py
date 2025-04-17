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

import base64
import logging
import os
import re
import socket
import ssl
import time
from typing import Optional

import urllib3

log = logging.getLogger(__name__)


STATUS_LINE_PATTERN = re.compile(r"^HTTP/\d\.\d (\d{3}) .*$")
NUM_RETRIES = 10
RETRYABLE_RESPONSE_CODES = {503, 429}


def create_socket(
    https_proxy_uri: str, target_host: str, target_port: int, custom_ca_bundle_path: Optional[str] = None
) -> socket.socket:
    """
    Establishes a socket connection through an HTTPS proxy to a target host and port.

    Args:
        https_proxy_uri (str): The URI of the HTTPS proxy, must include auth if required.
        target_host (str): The hostname of the target server to connect to.
        target_port (int): The port number of the target server to connect to.

    Returns:
        socket.socket: A connected SSL socket to the target host and port through the proxy.

    Raises:
        ValueError: If the proxy URI does not specify a hostname or port, or if the connection fails after retrying, with an invalid response code.
        RuntimeError: If there is an exception during the socket creation process.
    """

    parsed_proxy_uri = urllib3.util.parse_url(https_proxy_uri)

    if parsed_proxy_uri.hostname is None:
        raise ValueError("proxy uri has no hostname specified")

    if parsed_proxy_uri.port is None:
        raise ValueError("proxy uri has no port specified")

    last_response_code = -1
    for _ in range(NUM_RETRIES):
        try:
            proxy_socket = _create_ssl_socket(parsed_proxy_uri.hostname, parsed_proxy_uri.port, custom_ca_bundle_path)
            proxy_socket.sendall(f"CONNECT {target_host}:{target_port} HTTP/1.1\r\n".encode())
            proxy_socket.sendall(f"Host: {target_host}:{target_port}\r\n".encode())

            if parsed_proxy_uri.auth is not None:
                basic_auth_payload = base64.b64encode(parsed_proxy_uri.auth.encode()).decode()
                proxy_socket.sendall(f"Proxy-Authorization: Basic {basic_auth_payload}\r\n".encode())

            proxy_socket.sendall(b"\r\n")
            response_line = proxy_socket.recv(4096).decode().split("\r\n")[0]

            match = STATUS_LINE_PATTERN.match(response_line)

            if match is None:
                raise ValueError("status line pattern did not match")

            response_code = int(match.group(1))

            if response_code == 200:
                return proxy_socket

            last_response_code = response_code
            if response_code in RETRYABLE_RESPONSE_CODES:
                log.info("Received retryable response code from proxy, retrying after 0.5 seconds: %s", response_code)
                time.sleep(0.5)
            else:
                break
        except Exception as e:
            raise RuntimeError("Failed to create socket") from e

    raise ValueError(f"Failed to establish tunnel, invalid response code: {last_response_code}")


def _create_ssl_socket(proxy_host: str, proxy_port: int, custom_ca_bundle_path: Optional[str] = None) -> socket.socket:
    ca_bundle_path = (
        custom_ca_bundle_path if custom_ca_bundle_path is not None else os.environ.get("REQUESTS_CA_BUNDLE")
    )
    if not ca_bundle_path or not os.path.isfile(ca_bundle_path):
        log.warning("The CA_BUNDLE environment variable does not exist or is not a file.")
        raise ValueError("CA_BUNDLE does not exist")
    if not os.access(ca_bundle_path, os.R_OK):
        log.warning("The CA_BUNDLE file is not readable.")
        raise ValueError("CA_BUNDLE is not readable")
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.load_verify_locations(ca_bundle_path)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    wrapped_sock = context.wrap_socket(sock, server_hostname=proxy_host)
    wrapped_sock.connect((proxy_host, proxy_port))
    return wrapped_sock
