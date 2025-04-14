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
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Generic, Optional, TypeVar

from external_systems.sources._api import SourceCredentials
from external_systems.sources._utils import has_expiration_property

log = logging.getLogger(__name__)

T = TypeVar("T")

# Time before expiration to refresh the credentials
REFRESH_TIME_OFFSET_SECONDS = 5


class RefreshHandler(ABC, Generic[T]):
    """
    This manages how and where to retrieve the new refreshed resource from
    """

    @abstractmethod
    def refresh(self) -> Optional[T]:
        """
        Returns:
            T: The refreshed resource.
        """
        raise NotImplementedError("refresh() method not implemented")


class Refreshable(ABC, Generic[T]):
    """
    This manages the lifecycle of a resource that can be refreshed.
    """

    @abstractmethod
    def get(self) -> T:
        """
        Retrieve the current value of the resource.

        Returns:
            T: The current value of the resource.
        """
        raise NotImplementedError("get() method not implemented")


class DefaultSessionCredentialsManager(Refreshable[SourceCredentials]):
    """
    Client for refreshing resolved source credentials.
    Will return credentials if they are not expired.
    Otherwise will attempt to lazily refresh the credentials on `get()` calls.

    :param source_credentials: SourceCredentials object returned by API representing the source credentials.
    :param refresh_handler: A provider responsible for performing the refresh.
    :param refresh_offset_seconds: Represents how many seconds before the credentials expire should we refresh them.
    """

    def __init__(
        self,
        resolved_source_credentials: SourceCredentials,
        refresh_handler: Optional[RefreshHandler[SourceCredentials]] = None,
    ) -> None:
        self._credentials: SourceCredentials = resolved_source_credentials
        self._refresh_handler = refresh_handler

    def get(self) -> SourceCredentials:
        """
        Returns the source's credentials.

        This method automatically refreshes the credentials if they are expired.

        Returns
            SourceCredentials: The current source credentials.

        Raises
            ValueError: If the credentials have not been set.
        """
        self._maybe_refresh_credentials()
        if self._credentials is None:
            raise ValueError("Credentials have not been set")
        return self._credentials

    def _maybe_refresh_credentials(self) -> None:
        """
        Checks if the credentials are expired and delegates the refresh to `_refresh_credentials` if needed.
        """

        # Don't refresh if expiration time is not set
        if (
            self._credentials is None
            or not has_expiration_property(self._credentials)
            or self._credentials.expiration is None
        ):
            return

        # If the credentials are valid for more than specified seconds, don't refresh
        time_until_creds_expire = self._credentials.expiration - datetime.now()
        time_until_creds_expire_with_offset = time_until_creds_expire - timedelta(seconds=REFRESH_TIME_OFFSET_SECONDS)
        needs_refresh = time_until_creds_expire_with_offset.total_seconds() <= 0

        if not needs_refresh:
            return

        self._refresh_credentials()

    def _refresh_credentials(self) -> None:
        if self._refresh_handler is None:
            # Refresh handler is not set, nothing to refresh
            return

        maybe_resolved_credentials = self._refresh_handler.refresh()

        if maybe_resolved_credentials is None:
            raise ValueError("Refresh failed for source")

        self._credentials = maybe_resolved_credentials
