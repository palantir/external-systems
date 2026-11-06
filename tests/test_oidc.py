#  Copyright 2026 Palantir Technologies, Inc.
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

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Optional
from unittest.mock import Mock, patch

import pytest

from external_systems.sources import AwsCredentials, IdToken, RefreshHandler, Source, SourceParameters

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
TOKEN = IdToken("test-identity-token", NOW + timedelta(hours=1))


@pytest.fixture
def handler() -> Mock:
    return Mock(spec=RefreshHandler, refresh=Mock(return_value=TOKEN))


def make_source(handler: Optional[RefreshHandler[IdToken]] = None) -> Source:
    return Source(
        SourceParameters({}, None, {}, {}, None, AwsCredentials("access", "secret")),
        [],
        [],
        None,
        None,
        oidc_token_refresh_handler=handler,
    )


def test_unsupported_runtime_preserves_other_source_operations() -> None:
    source = make_source()
    assert isinstance(source.get_session_credentials().get(), AwsCredentials)
    with pytest.raises(ValueError, match="OIDC token access is not available"):
        source.get_oidc_id_token()


def test_oidc_is_lazy_and_cached_independently_of_session_credentials(handler: Mock) -> None:
    source = make_source(handler)
    handler.refresh.assert_not_called()
    with patch("external_systems.sources._oidc.datetime") as clock:
        clock.now.return_value = NOW
        assert source.get_oidc_id_token() is TOKEN
        assert source.get_oidc_id_token() is TOKEN
    handler.refresh.assert_called_once_with()
    assert isinstance(source.get_session_credentials().get(), AwsCredentials)


def test_refresh_at_expiration_offset(handler: Mock) -> None:
    refreshed = IdToken("refreshed-token", NOW + timedelta(hours=2))
    handler.refresh.side_effect = [TOKEN, refreshed]
    source = make_source(handler)
    with patch("external_systems.sources._oidc.datetime") as clock:
        clock.now.return_value = NOW
        assert source.get_oidc_id_token() is TOKEN
        clock.now.return_value = TOKEN.expiration - timedelta(seconds=61)
        assert source.get_oidc_id_token() is TOKEN
        clock.now.return_value = TOKEN.expiration - timedelta(seconds=60)
        assert source.get_oidc_id_token() is refreshed
    assert handler.refresh.call_count == 2
    assert TOKEN.token == "test-identity-token"


def test_non_utc_expiration(handler: Mock) -> None:
    token = IdToken("offset-token", TOKEN.expiration.astimezone(timezone(timedelta(hours=5))))
    handler.refresh.return_value = token
    source = make_source(handler)
    with patch("external_systems.sources._oidc.datetime") as clock:
        clock.now.return_value = NOW
        assert source.get_oidc_id_token() is token
        assert source.get_oidc_id_token() is token
    handler.refresh.assert_called_once_with()


def test_missing_token_is_not_cached(handler: Mock) -> None:
    handler.refresh.side_effect = [None, TOKEN]
    source = make_source(handler)
    with patch("external_systems.sources._oidc.datetime") as clock:
        clock.now.return_value = NOW
        with pytest.raises(ValueError, match="no token"):
            source.get_oidc_id_token()
        assert source.get_oidc_id_token() is TOKEN


def test_empty_token_is_rejected(handler: Mock) -> None:
    handler.refresh.return_value = IdToken("", TOKEN.expiration)
    with pytest.raises(ValueError, match="empty token"):
        make_source(handler).get_oidc_id_token()


def test_naive_expiration_is_rejected(handler: Mock) -> None:
    handler.refresh.return_value = IdToken("token", NOW.replace(tzinfo=None))
    with pytest.raises(ValueError, match="timezone-aware"):
        make_source(handler).get_oidc_id_token()


def test_expired_token_is_rejected(handler: Mock) -> None:
    handler.refresh.return_value = IdToken("expired-token", NOW)
    with patch("external_systems.sources._oidc.datetime") as clock:
        clock.now.return_value = NOW
        with pytest.raises(ValueError, match="expired token"):
            make_source(handler).get_oidc_id_token()


def test_refresh_failure_propagates_and_next_call_retries(handler: Mock) -> None:
    error = PermissionError("Token acquisition denied")
    refreshed = IdToken("refreshed-token", NOW + timedelta(hours=2))
    handler.refresh.side_effect = [TOKEN, error, refreshed]
    source = make_source(handler)
    with patch("external_systems.sources._oidc.datetime") as clock:
        clock.now.return_value = NOW
        source.get_oidc_id_token()
        clock.now.return_value = TOKEN.expiration
        with pytest.raises(PermissionError) as raised:
            source.get_oidc_id_token()
        assert raised.value is error
        assert source.get_oidc_id_token() is refreshed


def test_concurrent_access_reuses_token(handler: Mock) -> None:
    source = make_source(handler)
    with patch("external_systems.sources._oidc.datetime") as clock:
        clock.now.return_value = NOW
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(lambda _: source.get_oidc_id_token(), range(8)))
    assert all(token is TOKEN for token in results)
    handler.refresh.assert_called_once_with()


def test_token_repr_excludes_jwt() -> None:
    assert TOKEN.token not in repr(TOKEN)
    assert "expiration=" in repr(TOKEN)
