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

from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Optional

from ._api import IdToken
from ._refreshable import RefreshHandler

_REFRESH_OFFSET = timedelta(seconds=60)


class _OidcIdTokenManager:
    def __init__(self, refresh_handler: RefreshHandler[IdToken]) -> None:
        self._refresh_handler = refresh_handler
        self._token: Optional[IdToken] = None
        self._lock = Lock()

    def get(self) -> IdToken:
        with self._lock:
            if self._token is not None and self._token.expiration > datetime.now(timezone.utc) + _REFRESH_OFFSET:
                return self._token

            token = self._refresh_handler.refresh()
            if token is None or not token.token:
                raise ValueError("OIDC refresh handler returned no token or an empty token.")
            if token.expiration.utcoffset() is None:
                raise ValueError("OIDC token expiration must be timezone-aware.")
            if token.expiration <= datetime.now(timezone.utc):
                raise ValueError("OIDC refresh handler returned an expired token.")

            self._token = token
            return token
