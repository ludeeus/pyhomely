"""pyhomely custom types."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal, TypedDict


class SubscriptionStatus(StrEnum):
    """Model for the subscription status."""

    CONNECTED = "connected"
    CONNECTING = "connecting"
    DISCONNECTED = "disconnected"
    ERROR = "error"


class OauthToken(TypedDict):
    """Oauth token."""

    access_token: str
    expires_in: int
    refresh_expires_in: int
    refresh_token: str
    token_type: str
    session_state: str
    scope: str
    updated_at: int


class HomelyLocation(TypedDict):
    """Homely location."""

    name: str
    role: Literal["OWNER", "USER"]
    userId: str
    locationId: str
    gatewaySerial: str
    partnerCode: str


class HomelyEvent(TypedDict):
    """Homely event."""

    type: Literal["alarm-state-changed", "device-state-changed"]
    data: dict[str, Any]
