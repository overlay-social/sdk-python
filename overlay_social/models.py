"""Typed result models for the overlay.social read API.

These mirror @overlay-social/sdk (TypeScript) one-to-one. Each dataclass reads
the EXACT keys the live overlay returns — note the API itself mixes camelCase
(``displayName``, ``avatarRef``, ``stateRoot``) and snake_case (``minted_at``);
the ``from_dict`` helpers preserve that verbatim rather than silently
normalizing a real contract difference. Open-ended rows (``PeckRow``) stay
plain dicts because the indexer rides extra MAP keys — the one typed
exception is ``SourceHandle``, documented separately below because it is a
nested value worth a real shape, not a top-level response.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, TypedDict

# A peck row (/v1/feed, /v1/post/:txid) is intentionally an open dict — the
# indexer carries arbitrary extra MAP keys, so we do not lock its shape.
PeckRow = dict[str, Any]


class _SourceHandleRequired(TypedDict):
    namespace: Literal["zanaadu"]
    value: str
    number: int
    kind: Literal["user_number"]
    membership_proof: Literal["none"]


class SourceHandle(_SourceHandleRequired, total=False):
    """Feed shape of one foreign-namespace alias (mirrors `SourceHandle` in
    ``@overlay-social/sdk`` one-to-one).

    May appear at ``PeckRow["source_handle"]``. Today the only source is
    Zanaadu: it sells on-chain "user numbers" (an on-chain collectibles
    registry), and rows with ``app == "zanaadu"`` carry the holder's number
    here. See ``peck-overlay-schema/ZANAADU_POSTANCHOR_FORMAT.md`` §13 for
    the full derivation and its proof gap.

    ``namespace`` is mandatory and comes first so the value can never be
    shown bare and mistaken for a peck handle — render it qualified, e.g.
    ``@14 · zanaadu``.

    Rules (normative):

    - Comes IN ADDITION TO ``author`` (the key). Never replaces it.
    - Omitted from the row entirely (never ``None``, never ``""``) when the
      author has no alias at the source — absence is a valid, measured
      state there, not a gap to fill with a guess.
    - ``membership_proof: "none"`` means the value was READ from the
      source's own state (here: a registry counter, cross-checked 7/7
      against Zanaadu's own UI) but the source's stronger commitment
      (their sparse Merkle tree) is NOT verified by us — the root is
      legible, not reproducible. It is not a claim that the number itself
      is unreliable.
    - ``numbers`` (all numbers this key owns at the source, ascending) is
      only present when there is more than one; ``value``/``number`` are
      then the lowest. Tie-break for "which number is primary" when a key
      owns several is NOT proven on-chain (§13.7) — lowest was chosen for
      stability over time, not because it is confirmed canonical.
    """

    numbers: list[int]


@dataclass(frozen=True)
class ResolvedIdentity:
    """One entry from POST /v1/identities/resolve, keyed by the exact input."""

    pubkey: str
    address: str
    handle: str | None = None
    display_name: str | None = None
    avatar_ref: str | None = None
    profile_outpoint: str | None = None
    minted_at: str | None = None  # set by GET /v1/identities (discovery); None from resolve

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ResolvedIdentity":
        return cls(
            pubkey=d.get("pubkey", ""),
            address=d.get("address", ""),
            handle=d.get("handle"),
            display_name=d.get("displayName"),
            avatar_ref=d.get("avatarRef"),
            profile_outpoint=d.get("profileOutpoint"),
            minted_at=d.get("mintedAt"),
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
class TopicAnchor:
    """Latest on-chain anchor for a topic's state-root (when present in /state).
    `matches_live` is True when the served state_root equals the anchored root."""

    root: str
    txid: str
    vout: int
    outpoint: str
    block_height: int | None = None
    ts: int | None = None
    anchored_at: str | None = None
    matches_live: bool = False

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "TopicAnchor":
        return cls(
            root=d.get("root", ""),
            txid=d.get("txid", ""),
            vout=int(d.get("vout", 0)),
            outpoint=d.get("outpoint", ""),
            block_height=d.get("blockHeight"),
            ts=d.get("ts"),
            anchored_at=d.get("anchoredAt"),
            matches_live=bool(d.get("matchesLive", False)),
        )


@dataclass(frozen=True)
class TopicState:
    topic: str
    count: int
    state_root: str
    source: str
    anchor: TopicAnchor | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "TopicState":
        a = d.get("anchor")
        return cls(
            topic=d.get("topic", ""),
            count=int(d.get("count", 0)),
            state_root=d.get("stateRoot", ""),
            source=d.get("source", ""),
            anchor=TopicAnchor.from_dict(a) if isinstance(a, dict) else None,
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


@dataclass(frozen=True)
class FriendEntry:
    """One side of the friend graph, hydrated with the peer's canonical handle."""

    peer: str  # peer identity ROOT pubkey (66-hex compressed)
    handle: str | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "FriendEntry":
        return cls(peer=d.get("peer", ""), handle=d.get("handle"))


@dataclass(frozen=True)
class FriendsGraph:
    """GET /v1/friends/:subject — mutual-consent friendship layer.

    ``mutual`` = both directions attested + unrevoked (two one-way BRC-3
    records form a pair). ``pending_in``/``pending_out`` are one-way.
    ``legacy_outgoing``/``legacy_incoming`` mirror the BAP-era Bitcoin Schema
    rows (display-only; never count toward mutual).
    """

    mutual: list[FriendEntry] = field(default_factory=list)
    pending_in: list[FriendEntry] = field(default_factory=list)
    pending_out: list[FriendEntry] = field(default_factory=list)
    legacy_outgoing: list[dict[str, Any]] = field(default_factory=list)
    legacy_incoming: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "FriendsGraph":
        light = d.get("light") or {}
        data = d.get("data") or {}
        return cls(
            mutual=[FriendEntry.from_dict(x) for x in (light.get("mutual") or [])],
            pending_in=[FriendEntry.from_dict(x) for x in (light.get("pending_in") or [])],
            pending_out=[FriendEntry.from_dict(x) for x in (light.get("pending_out") or [])],
            legacy_outgoing=list(data.get("outgoing") or []),
            legacy_incoming=list(data.get("incoming") or []),
        )


@dataclass(frozen=True)
class NotificationItem:
    """One row from GET /v1/notifications/:address.

    ``actor`` is an address/username for like/reply/follow/mention and an
    identity ROOT pubkey for friend_request — resolve via resolve_identities
    (bound posting keys collapse to their identity).
    """

    type: str
    actor: str
    target_txid: str | None = None
    subject_txid: str | None = None
    timestamp: str | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "NotificationItem":
        ts = d.get("timestamp")
        return cls(
            type=d.get("type", ""),
            actor=d.get("actor", ""),
            target_txid=d.get("target_txid"),
            subject_txid=d.get("subject_txid"),
            timestamp=str(ts) if ts is not None else None,
        )
