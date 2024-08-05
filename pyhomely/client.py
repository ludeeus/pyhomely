"""pyhomely client."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Awaitable, cast

import aiohttp
import socketio

from .const import API_HOST
from .exceptions import (
    HomelyAuthenticationError,
    HomelyConnectionError,
    HomelyError,
)
from .types import HomelyEvent, HomelyLocation, OauthToken, SubscriptionStatus

if TYPE_CHECKING:
    from collections.abc import Callable


class ApiClient:
    """Class for interacting with the Homely API."""

    def __init__(
        self,
        *,
        username: str,
        password: str,
        client_session: aiohttp.ClientSession,
        **_: Any,
    ) -> None:
        """Initialize the API client."""
        self._client_session = client_session
        self._subscription_status = SubscriptionStatus.DISCONNECTED
        self._username = username
        self._password = password
        self._oauth_token: OauthToken | None = None

    @property
    def subscription_status(self) -> SubscriptionStatus:
        """Return the current subscription status."""
        return self._subscription_status

    async def _get_access_token(self) -> str:
        """Get the access token."""
        now = datetime.now(tz=timezone.utc).timestamp()
        token = self._oauth_token

        if token is None:
            self._oauth_token = token = await self._get_oauth_token()

        elif (token["updated_at"] + token["expires_in"] + 300) > now:
            # Still valid
            return token["access_token"]
        elif (token["updated_at"] + token["refresh_expires_in"] + 300) > now:
            # Refresh token is still valid
            self._oauth_token = token = await self._oauth_refresh_token(
                token["refresh_token"]
            )
        else:
            # Need to reauthenticate
            self._oauth_token = token = await self._get_oauth_token()
        return token["access_token"]

    async def _call_api(
        self,
        endpoint: str,
        method: str = "GET",
        *,
        params: list[tuple[str, str | int]] | None = None,
        headers: dict[str, str] | None = None,
        data: Any | None = None,
        timeout: float = 10.0,
        force_new_token: bool = False,
        **_: Any,
    ) -> Any:
        """Call the API endpoint and return the response."""
        access_token = None if force_new_token else await self._get_access_token()
        try:
            async with self._client_session.request(
                method=method,
                url=f"https://{API_HOST}/homely/{endpoint}",
                params=params,
                json=data,
                headers={
                    aiohttp.hdrs.CONTENT_TYPE: "application/json",
                    aiohttp.hdrs.ACCEPT: "application/json",
                    **(
                        {aiohttp.hdrs.AUTHORIZATION: f"Bearer {access_token}"}
                        if access_token
                        else {}
                    ),
                    **(headers or {}),
                },
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as response:
                json_response: Any = None
                error_message: str = ""

                try:
                    json_response = await response.json()
                    if isinstance(json_response, dict):
                        error_message = json_response.get("message", "")
                except TypeError as exception:
                    raise HomelyError(
                        f"Invalid response from Homely ({response.reason})"
                    ) from exception

                if response.status == 401:
                    raise HomelyAuthenticationError(f"Unauthorized ({error_message})")

                if json_response and response.status in (200, 201):
                    return json_response

                raise HomelyError(
                    f"{response.status}: {response.reason} ({error_message})"
                )
        except (HomelyAuthenticationError, HomelyError):
            raise
        except asyncio.TimeoutError as exception:
            raise HomelyConnectionError(
                "Timeouterror connecting to Homely"
            ) from exception
        except (aiohttp.ClientError, asyncio.CancelledError) as exception:
            raise HomelyConnectionError(
                f"Could not communicate with Homely - {exception}"
            ) from exception
        except Exception as exception:  # pylint: disable=broad-except
            raise HomelyError(f"Unexpected error - {exception}") from exception

    async def _get_oauth_token(self) -> OauthToken:
        """Get server information."""
        response: dict[str, Any] = await self._call_api(
            "oauth/token",
            method="POST",
            data={"username": self._username, "password": self._password},
            force_new_token=True,
        )
        self._oauth_token = token = cast(
            OauthToken,
            {**response, "updated_at": datetime.now(tz=timezone.utc).timestamp()},
        )
        return token

    async def _oauth_refresh_token(self, refresh_token: str) -> OauthToken:
        """Get server information."""
        response: dict[str, Any] = await self._call_api(
            "oauth/refresh-token",
            method="POST",
            force_new_token=True,
            data={"grant_type": "refresh_token", "refresh_token": refresh_token},
        )
        self._oauth_token = token = cast(
            OauthToken,
            {
                **response,
                "updated_at": datetime.now(tz=timezone.utc).timestamp(),
            },
        )
        return token

    async def locations(self) -> list[HomelyLocation]:
        """Get all locations from the Homely API."""
        response: list[HomelyLocation] = await self._call_api("locations")
        return response

    async def home(self, location_id: str) -> dict[str, Any]:
        """Get all home data for a location ID from the Homely API."""
        response: dict[str, Any] = await self._call_api(f"home/{location_id}")
        return response

    async def subscribe(
        self,
        location_id: str,
        callback: Callable[[HomelyEvent], Awaitable[None]],
    ) -> None:
        """Subscribe to events."""
        access_token = await self._get_access_token()
        try:
            async with socketio.AsyncSimpleClient() as sio:
                await sio.connect(
                    f"wss://{API_HOST}/?locationId={location_id}&token=Bearer%20{access_token}",
                    transports=["websocket"],
                )
                while sio.connected:
                    event = await sio.receive()
                    await callback(event[1])
        except asyncio.CancelledError:
            self._subscription_status = SubscriptionStatus.DISCONNECTED
        except HomelyConnectionError:
            self._subscription_status = SubscriptionStatus.ERROR
            raise
        except (asyncio.TimeoutError, socketio.exceptions.TimeoutError) as exception:
            self._subscription_status = SubscriptionStatus.ERROR
            raise HomelyConnectionError(
                "Timeout error connecting to Homely"
            ) from exception
        except socketio.exceptions.SocketIOError as exception:
            self._subscription_status = SubscriptionStatus.ERROR
            raise HomelyConnectionError(
                f"Could not communicate with Homely - {exception}"
            ) from exception
        except Exception as exception:  # pylint: disable=broad-except
            self._subscription_status = SubscriptionStatus.ERROR
            raise HomelyError(f"Unexpected error - {exception}") from exception
