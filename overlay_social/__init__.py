"""overlay-social — read-only Python client for the canonical peck social
overlay at overlay.peck.to.

A pure read lens: identity resolution, profiles, handles, feed, threads and
overlay topic-state. Sync and async. Mirrors @overlay-social/sdk (TypeScript).

    from overlay_social import create_overlay_client

    overlay = create_overlay_client()
    state = overlay.get_state()
    ids = overlay.resolve_identities(addresses=["<p2pkh-address>"])

Async:

    from overlay_social import create_async_overlay_client

    async with create_async_overlay_client() as overlay:
        state = await overlay.get_state()
"""

from .client import (
    DEFAULT_OVERLAY_URL,
    AsyncOverlayClient,
    OverlayClient,
    OverlayError,
    create_async_overlay_client,
    create_overlay_client,
)
from .models import (
    FeedResponse,
    FriendEntry,
    FriendsGraph,
    HandleResolution,
    IdentityBundle,
    IdentityProfile,
    NotificationItem,
    OverlayState,
    PeckRow,
    ProfileRow,
    ProfileState,
    ResolvedIdentity,
    SourceHandle,
    ThreadResponse,
    TopicAnchor,
    TopicState,
)

__version__ = "0.3.0"

__all__ = [
    "__version__",
    "DEFAULT_OVERLAY_URL",
    "OverlayClient",
    "AsyncOverlayClient",
    "OverlayError",
    "create_overlay_client",
    "create_async_overlay_client",
    "ResolvedIdentity",
    "IdentityBundle",
    "FriendEntry",
    "FriendsGraph",
    "NotificationItem",
    "IdentityProfile",
    "HandleResolution",
    "ProfileRow",
    "ProfileState",
    "OverlayState",
    "TopicState",
    "TopicAnchor",
    "FeedResponse",
    "ThreadResponse",
    "PeckRow",
    "SourceHandle",
]
