"""Typed result models for the overlay.social read API.

These mirror @overlay-social/sdk (TypeScript) one-to-one. Each dataclass reads
the EXACT keys the live overlay returns — note the API itself mixes camelCase
(``displayName``, ``avatarRef``, ``stateRoot``) and snake_case (``minted_at``);
the ``from_dict`` helpers preserve that verbatim rather than silently
normalizing a real contract difference. Open-ended rows (``PeckRow``) stay
plain dicts because the indexer rides extra MAP keys.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# A peck row (/v1/feed, /v1/post/:txid) is intentionally an open dict — the
# indexer carries arbitrary extra MAP keys, so we do not lock its shape.
PeckRow = dict[str, Any]


@dataclass(frozen=True)
class ResolvedIdentity:
    """One entry from POST /v1/identities/resolve, keyed by the exact input."""

    pubkey: str
    address: str
    handle: str | None = None
    display_name: str | None = None
    avatar_ref: str | None = None
    profile_outpoint: str | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ResolvedIdentity":
        return cls(
            pubkey=d.get("pubkey", ""),
            address=d.get("address", ""),
            handle=d.get("handle"),
            display_name=d.get("displayName"),
            avatar_ref=d.get("avatarRef"),
            profile_outpoint=d.get("profileOutpoint"),
        )


@dataclass(frozen=True)
class IdentityProfile:
    outpoint: str
    version: int
    display_name: str | None = None
    bio: str | None = None
    avatar_url: str | None = None  # NB: resolved https here, not raw uhrp ref

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "IdentityProfile":
        return cls(
            outpoint=d.get("outpoint", ""),
            version=int(d.get("version", 0)),
            display_name=d.get("displayName"),
            bio=d.get("bio"),
            avatar_url=d.get("avatarUrl"),
        )


@dataclass(frozen=True)
class IdentityBundle:
    """Full bundle from GET /identity/:pubkey (profile + handles + certs)."""

    pubkey: str
    profile: IdentityProfile | None = None
    handles: list[str] = field(default_factory=list)
    certs: list[Any] = field(default_factory=list)
    as_of: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "IdentityBundle":
        prof = d.get("profile")
        return cls(
            pubkey=d.get("pubkey", ""),
            profile=IdentityProfile.from_dict(prof) if prof else None,
            handles=list(d.get("handles") or []),
            certs=list(d.get("certs") or []),
            as_of=d.get("asOf"),
        )


@dataclass(frozen=True)
class HandleResolution:
    """GET /resolve/:handle — handle -> {pubkey, deepLinks}."""

    handle: str
    pubkey: str
    deep_links: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "HandleResolution":
        return cls(
            handle=d.get("handle", ""),
            pubkey=d.get("pubkey", ""),
            deep_links=dict(d.get("deepLinks") or {}),
        )


@dataclass(frozen=True)
class ProfileState:
    subject: str
    version: int
    display_name: str | None = None
    bio: str | None = None
    avatar_ref: str | None = None
    cert_refs: list[str] = field(default_factory=list)
    handle: str | None = None
    nickname: str | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ProfileState":
        return cls(
            subject=d.get("subject", ""),
            version=int(d.get("version", 0)),
            display_name=d.get("displayName"),
            bio=d.get("bio"),
            avatar_ref=d.get("avatarRef"),
            cert_refs=list(d.get("certRefs") or []),
            handle=d.get("handle"),
            nickname=d.get("nickname"),
        )


@dataclass(frozen=True)
class ProfileRow:
    """One canonical ProfileToken row from GET /v1/bio/profile."""

    outpoint: str
    txid: str
    vout: int
    subject: str
    owner: str
    version: int
    state: ProfileState
    minted_at: int | None = None
    updated_at: int | None = None
    canonical: bool = False
    spent: bool = False

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ProfileRow":
        return cls(
            outpoint=d.get("outpoint", ""),
            txid=d.get("txid", ""),
            vout=int(d.get("vout", 0)),
            subject=d.get("subject", ""),
            owner=d.get("owner", ""),
            version=int(d.get("version", 0)),
            state=ProfileState.from_dict(d.get("state") or {}),
            minted_at=d.get("minted_at"),
            updated_at=d.get("updated_at"),
            canonical=bool(d.get("canonical", False)),
            spent=bool(d.get("spent", False)),
        )


@dataclass(frozen=True)
class TopicState:
    topic: str
    count: int
    state_root: str
    source: str

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "TopicState":
        return cls(
            topic=d.get("topic", ""),
            count=int(d.get("count", 0)),
            state_root=d.get("stateRoot", ""),
            source=d.get("source", ""),
        )


@dataclass(frozen=True)
class OverlayState:
    """GET /state — overlay topic state-roots + counts."""

    status: str
    service: str
    domain: str
    network: str
    managers: list[str] = field(default_factory=list)
    topics: list[TopicState] = field(default_factory=list)
    computed_at: str | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "OverlayState":
        return cls(
            status=d.get("status", ""),
            service=d.get("service", ""),
            domain=d.get("domain", ""),
            network=d.get("network", ""),
            managers=list(d.get("managers") or []),
            topics=[TopicState.from_dict(t) for t in (d.get("topics") or [])],
            computed_at=d.get("computedAt"),
        )


@dataclass(frozen=True)
class FeedResponse:
    status: str
    total: int
    offset: int
    limit: int
    count: int
    data: list[PeckRow] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "FeedResponse":
        return cls(
            status=d.get("status", ""),
            total=int(d.get("total", 0)),
            offset=int(d.get("offset", 0)),
            limit=int(d.get("limit", 0)),
            count=int(d.get("count", 0)),
            data=list(d.get("data") or []),
        )


@dataclass(frozen=True)
class ThreadResponse:
    post: PeckRow | None = None
    replies: list[PeckRow] = field(default_factory=list)
