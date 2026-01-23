#!/usr/bin/env python3
"""
Test script to initialize a Source with Envoy Connect proxy as egress proxy.
"""

from external_systems.sources._api import HttpsConnectionParameters, SourceParameters
from external_systems.sources._sources import Source

# Configure the target external system connection to httpbin
https_connection = HttpsConnectionParameters(
    url="https://httpbin.org",
    headers={"X-Test-Header": "test-value"},
    query_params={},
)

# Create source parameters
source_params = SourceParameters(
    secrets={"api_key": "test-secret"},
    proxy_token=None,  # Not using on-prem proxy
    https_connections={"default": https_connection},
    server_certificates={},
    client_certificate=None,
    resolved_source_credentials=None,
)

# Initialize the source with Envoy proxy as egress proxy
source = Source(
    source_parameters=source_params,
    on_prem_proxy_service_uris=[],  # Not using on-prem proxy
    egress_proxy_service_uris=["http://localhost:8080"],  # Your Envoy proxy
    egress_proxy_token="dummy-token",  # Token for egress proxy authentication
    source_configuration=None,
)

# Get the HTTPS connection
connection = source.get_https_connection()

# Get the client (requests.Session) that's configured to use the egress proxy
client = connection.get_client()

# Print proxy configuration

# Make a test request to httpbin through the Envoy proxy
try:
    with client.get(f"{connection.url}/get") as response:
        print(f"\nResponse status: {response.status_code}")
except Exception as e:
    print(f"\nRequest failed: {e}")
    import traceback
    traceback.print_exc()

source2 = Source(
    source_parameters=source_params,
    on_prem_proxy_service_uris=[],  # Not using on-prem proxy
    egress_proxy_service_uris=["http://localhost:8080"],  # Your Envoy proxy
    egress_proxy_token="dummy-token",  # Token for egress proxy authentication
    source_configuration=None,
)

# Get the HTTPS connection
connection2 = source2.get_https_connection()

# Get the client (requests.Session) that's configured to use the egress proxy
client2 = connection2.get_client()

# Test another endpoint to verify headers are passed through
try:
    with client2.get(f"{connection.url}/headers") as response:
        print(f"\nResponse status: {response.status_code}")
    # client.close()
    # del response
except Exception as e:
    print(f"\nRequest failed: {e}")
    import traceback
    traceback.print_exc()

input("Press Enter to continue...")
