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

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from external_systems.sources import AwsCredentials, SourceCredentials
from external_systems.sources._refreshable import DefaultSessionCredentialsManager, RefreshHandler


class MockRefreshHandler(RefreshHandler[SourceCredentials]):
    def __init__(self, resolved_source_credentials: SourceCredentials):
        self._resolved_source_credentials = resolved_source_credentials

    def refresh(self) -> SourceCredentials:
        return self._resolved_source_credentials


@pytest.fixture
def valid_expiration_datetime() -> datetime:
    valid_expiration = datetime.now() + timedelta(minutes=1)
    return valid_expiration.replace(microsecond=0)


@pytest.fixture
def refreshed_expiration_datetime(valid_expiration_datetime: datetime) -> datetime:
    return valid_expiration_datetime + timedelta(seconds=300)


@pytest.fixture
def expired_datetime() -> datetime:
    expired_datetime = datetime.now() - timedelta(minutes=1)
    return expired_datetime.replace(microsecond=0)


@pytest.fixture
def source_credentials(valid_expiration_datetime: datetime) -> SourceCredentials:
    return AwsCredentials(
        access_key_id="access-key",
        secret_access_key="secret",
        session_token="session_token",
        expiration=valid_expiration_datetime,
    )


@pytest.fixture
def refreshed_source_credentials(refreshed_expiration_datetime: datetime) -> SourceCredentials:
    return AwsCredentials(
        access_key_id="access-key",
        secret_access_key="secret",
        session_token="session_token",
        expiration=refreshed_expiration_datetime,
    )


@pytest.fixture
def expired_source_credentials(expired_datetime: datetime) -> SourceCredentials:
    return AwsCredentials(
        access_key_id="access-key",
        secret_access_key="secret",
        session_token="session_token",
        expiration=expired_datetime,
    )


@pytest.fixture
def resolved_source_credentials(valid_expiration_datetime: datetime) -> SourceCredentials:
    return AwsCredentials(
        access_key_id="access-key",
        secret_access_key="secret",
        session_token="session_token",
        expiration=valid_expiration_datetime,
    )


@pytest.fixture
def refreshed_resolved_source_credentials(refreshed_expiration_datetime: datetime) -> SourceCredentials:
    return AwsCredentials(
        access_key_id="access-key",
        secret_access_key="secret",
        session_token="session_token",
        expiration=refreshed_expiration_datetime,
    )


@pytest.fixture
def expired_resolved_source_credentials(expired_datetime: datetime) -> SourceCredentials:
    return AwsCredentials(
        access_key_id="access-key",
        secret_access_key="secret",
        session_token="session_token",
        expiration=expired_datetime,
    )


def test_get_credentials_returns_creds_if_valid(
    resolved_source_credentials: SourceCredentials,
    source_credentials: SourceCredentials,
    refreshed_resolved_source_credentials: SourceCredentials,
) -> None:
    manager = DefaultSessionCredentialsManager(
        resolved_source_credentials, MockRefreshHandler(refreshed_resolved_source_credentials)
    )
    assert manager.get() == source_credentials


def test_maybe_refresh_credentials_does_not_refresh_when_valid(
    resolved_source_credentials: SourceCredentials,
    refreshed_resolved_source_credentials: SourceCredentials,
) -> None:
    manager = DefaultSessionCredentialsManager(
        resolved_source_credentials, MockRefreshHandler(refreshed_resolved_source_credentials)
    )
    with patch.object(manager, "_refresh_credentials") as mock_refresh:
        manager._maybe_refresh_credentials()
        mock_refresh.assert_not_called()


def test_maybe_refresh_credentials_attempts_refresh_when_expired(
    expired_resolved_source_credentials: SourceCredentials,
    refreshed_resolved_source_credentials: SourceCredentials,
) -> None:
    manager = DefaultSessionCredentialsManager(
        expired_resolved_source_credentials, MockRefreshHandler(refreshed_resolved_source_credentials)
    )
    with patch.object(manager, "_refresh_credentials") as mock_refresh:
        manager._maybe_refresh_credentials()
        mock_refresh.assert_called_once()


def test_get_credentials_with_refresh_handler(
    expired_resolved_source_credentials: SourceCredentials,
    refreshed_source_credentials: SourceCredentials,
    refreshed_resolved_source_credentials: SourceCredentials,
) -> None:
    manager = DefaultSessionCredentialsManager(
        expired_resolved_source_credentials, MockRefreshHandler(refreshed_resolved_source_credentials)
    )
    assert manager.get() == refreshed_source_credentials


def test_refresh_credentials_raises_error_on_refresh_failure(
    resolved_source_credentials: SourceCredentials,
) -> None:
    mock_refresh_handler = MagicMock(spec=RefreshHandler)
    mock_refresh_handler.refresh.return_value = None
    manager = DefaultSessionCredentialsManager(resolved_source_credentials, mock_refresh_handler)
    with pytest.raises(ValueError, match="Refresh failed for source"):
        manager._refresh_credentials()


def test_get_credentials_returns_original_creds_if_no_refresh_handler(
    expired_resolved_source_credentials: SourceCredentials,
    expired_source_credentials: SourceCredentials,
) -> None:
    manager = DefaultSessionCredentialsManager(expired_resolved_source_credentials, None)
    assert manager.get() == expired_source_credentials
