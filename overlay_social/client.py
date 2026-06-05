"""Read-only clients for overlay.peck.to — sync (`OverlayClient`) and async
(`AsyncOverlayClient`).

A PURE READ LENS over the canonical peck social overlay. It does NOT write,
mint, pay, or federate — none of those exist on the live service. It speaks the
REST facade that actually runs today (verified against overlay.peck.to), NOT
the BRC-24 ``peck-schema`` lookup (that lookup is a no-op).

Semantics mirror @overlay-social/sdk and peck-web/overlay_client.py:
  * ``resolve_identities`` returns ``{}`` on ANY error and omits keys without a
    canonical ProfileToken, so a feed UI can enrich defensively and NEVER break.
  * single-item lookups return ``None`` for missing/invalid (404/400/empty).
  * only ``get_feed`` / ``get_state`` raise on genuine 5xx / network failure.
  * every request has a hard timeout; the overlay is load-bearing for apps.
"""

from __future__ import annotations

from typing import Any

import httpx

from .models import (
    FeedResponse,
    HandleResolution,
    IdentityBundle,
    OverlayState,
    PeckRow,
    ProfileRow,
    ResolvedIdentity,
    ThreadResponse,
    TopicAnchor,
    TopicState,
)

DEFAULT_OVERLAY_URL = "https://overlay.peck.to"
DEFAULT_TIMEOUT_S = 8.0
MAX_RESOLVE_KEYS = 200

_JSON_HEADERS = {"accept": "application/json"}


class OverlayError(RuntimeError):
    """Raised by get_feed/get_state on a genuine upstream/network failure."""


# ── pure request planners + response interpreters (shared sync/async) ────────


def _feed_query(params: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}

    def put(k: str, v: Any) -> None:
        if v is not None and v != "":
            out[k] = str(v)

    put("limit", params.get("limit", 50))
    put("offset", params.get("offset"))
    put("app", params.get("app"))
    put("tag", params.get("tag"))
    # `types` (CSV) takes precedence server-side; only send `type` without it.
    put("type", None if params.get("types") else params.get("type"))
    put("types", params.get("types"))
    put("author", params.get("author"))
    put("order", params.get("order", "desc"))
    put("before", params.get("before"))
    return out


def _profile_query(sel: dict[str, Any]) -> dict[str, str] | None:
    for key in ("subject", "owner", "outpoint"):
        if sel.get(key):
            return {key: str(sel[key])}
    return None


def _resolve_body(pubkeys: list[str] | None, addresses: list[str] | None) -> dict[str, list[str]] | None:
    pks = [p for p in (pubkeys or []) if p][:MAX_RESOLVE_KEYS]
    addrs = [a for a in (addresses or []) if a][:MAX_RESOLVE_KEYS]
    if not pks and not addrs:
        return None
    body: dict[str, list[str]] = {}
    if pks:
        body["pubkeys"] = pks
    if addrs:
        body["addresses"] = addrs
    return body


def _interp_resolve(ok: bool, data: Any) -> dict[str, ResolvedIdentity]:
    if not ok or not isinstance(data, dict):
        return {}
    ids = data.get("identities") or {}
    return {k: ResolvedIdentity.from_dict(v) for k, v in ids.items() if isinstance(v, dict)}


def _interp_list_identities(data: Any) -> list[ResolvedIdentity]:
    if not isinstance(data, dict):
        return []
    ids = data.get("identities") or []
    return [ResolvedIdentity.from_dict(v) for v in ids if isinstance(v, dict)]


def _interp_identity(data: Any) -> IdentityBundle | None:
    if not isinstance(data, dict) or data.get("error") or not data.get("pubkey"):
        return None
    return IdentityBundle.from_dict(data)


def _interp_handle(data: Any) -> HandleResolution | None:
    if not isinstance(data, dict) or data.get("error") or not data.get("pubkey"):
        return None
    return HandleResolution.from_dict(data)


def _interp_profile(data: Any) -> ProfileRow | None:
    if not isinstance(data, dict) or data.get("error"):
        return None
    results = data.get("results")
    if not isinstance(results, list) or not results:
        return None
    return ProfileRow.from_dict(results[0])


def _interp_feed(data: Any) -> FeedResponse:
    if not isinstance(data, dict) or data.get("status") != "ok" or not isinstance(data.get("data"), list):
        raise OverlayError("overlay feed: unexpected shape")
    return FeedResponse.from_dict(data)


def _interp_post(data: Any) -> PeckRow | None:
    if not isinstance(data, dict) or data.get("error") or data.get("status") != "ok" or not data.get("data"):
        return None
    return data["data"]


def _interp_thread(data: Any) -> ThreadResponse:
    if not isinstance(data, dict):
        return ThreadResponse(post=None, replies=[])
    post = data.get("parent") or data.get("post") or data.get("data")
    return ThreadResponse(post=post, replies=list(data.get("replies") or []))


def _base(url: str) -> str:
    return url.rstrip("/")


# ── sync client ──────────────────────────────────────────────────────────────


class OverlayClient:
    """Synchronous read client. Usable as a context manager."""

    def __init__(
        self,
        base_url: str = DEFAULT_OVERLAY_URL,
        *,
        timeout: float = DEFAULT_TIMEOUT_S,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = _base(base_url)
        self._timeout = timeout
        self._client = client or httpx.Client(timeout=timeout, headers=_JSON_HEADERS)
        self._owns_client = client is None

    def __enter__(self) -> "OverlayClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    # low-level
    def _get(self, path: str) -> httpx.Response:
        return self._client.get(f"{self.base_url}{path}")

    def _get_json(self, path: str) -> Any:
        r = self._get(path)
        if r.status_code // 100 != 2:
            raise OverlayError(f"overlay {r.status_code} on {path}: {r.text[:200]}")
        return r.json()

    def _get_json_or_null(self, path: str) -> Any:
        r = self._get(path)
        if r.status_code in (400, 404):
            return None
        if r.status_code // 100 != 2:
            raise OverlayError(f"overlay {r.status_code} on {path}: {r.text[:200]}")
        return r.json()

    # identity
    def resolve_identities(
        self, *, pubkeys: list[str] | None = None, addresses: list[str] | None = None
    ) -> dict[str, ResolvedIdentity]:
        body = _resolve_body(pubkeys, addresses)
        if body is None:
            return {}
        try:
            r = self._client.post(
                f"{self.base_url}/v1/identities/resolve",
                json=body,
                headers={"content-type": "application/json"},
            )
            return _interp_resolve(r.status_code // 100 == 2, r.json() if r.content else None)
        except Exception:
            return {}

    def list_identities(self, *, limit: int = 50, offset: int = 0) -> list[ResolvedIdentity]:
        """GET /v1/identities — people-discovery: canonical profiles, newest
        first ("who's on the overlay"). Returns [] on any error."""
        try:
            r = self._client.get(
                f"{self.base_url}/v1/identities",
                params={"limit": limit, "offset": offset},
            )
            if r.status_code // 100 != 2:
                return []
            return _interp_list_identities(r.json() if r.content else None)
        except Exception:
            return []

    def get_identity(self, pubkey: str) -> IdentityBundle | None:
        if not pubkey:
            return None
        return _interp_identity(self._get_json_or_null(f"/identity/{pubkey}"))

    def resolve_handle(self, handle: str) -> HandleResolution | None:
        if not handle:
            return None
        return _interp_handle(self._get_json_or_null(f"/resolve/{handle}"))

    def get_profile(
        self, *, subject: str | None = None, owner: str | None = None, outpoint: str | None = None
    ) -> ProfileRow | None:
        q = _profile_query({"subject": subject, "owner": owner, "outpoint": outpoint})
        if q is None:
            return None
        resp = self._client.get(f"{self.base_url}/v1/bio/profile", params=q)
        if resp.status_code in (400, 404):
            return None
        if resp.status_code // 100 != 2:
            raise OverlayError(f"overlay {resp.status_code} on /v1/bio/profile")
        return _interp_profile(resp.json())

    # feed / posts
    def get_feed(self, **params: Any) -> FeedResponse:
        resp = self._client.get(f"{self.base_url}/v1/feed", params=_feed_query(params))
        if resp.status_code // 100 != 2:
            raise OverlayError(f"overlay {resp.status_code} on /v1/feed: {resp.text[:200]}")
        return _interp_feed(resp.json())

    def get_post(self, txid: str) -> PeckRow | None:
        if not txid:
            return None
        return _interp_post(self._get_json_or_null(f"/v1/post/{txid}"))

    def get_thread(self, txid: str) -> ThreadResponse:
        if not txid:
            return ThreadResponse(post=None, replies=[])
        return _interp_thread(self._get_json_or_null(f"/v1/thread/{txid}"))

    # overlay state
    def get_state(self) -> OverlayState:
        return OverlayState.from_dict(self._get_json("/state"))

    def get_topic_root(self, topic: str) -> TopicState | None:
        if not topic:
            return None
        try:
            for t in self.get_state().topics:
                if t.topic == topic:
                    return t
        except OverlayError:
            return None
        return None

    def get_anchor(self, topic: str) -> TopicAnchor | None:
        """Latest on-chain anchor for a topic's state-root, or None when nothing
        is anchored yet (anchoring not enabled / topic untracked)."""
        if not topic:
            return None
        try:
            for t in self.get_state().topics:
                if t.topic == topic:
                    return t.anchor
        except OverlayError:
            return None
        return None

    def verify_root(self, topic: str) -> dict:
        """Verify the current state-root against the chain. Returns whether the
        topic has any anchor, whether the live root matches the anchored root,
        and the anchor txid for independent BEEF verification (BRC-62)."""
        empty = {"anchored": False, "matches_live": False, "live_root": None, "anchored_root": None, "txid": None}
        if not topic:
            return empty
        try:
            state = self.get_state()
        except OverlayError:
            return empty
        t = next((x for x in state.topics if x.topic == topic), None)
        if t is None:
            return empty
        a = t.anchor
        return {
            "anchored": a is not None,
            "matches_live": bool(a and a.matches_live),
            "live_root": t.state_root,
            "anchored_root": a.root if a else None,
            "txid": a.txid if a else None,
        }


# ── async client ─────────────────────────────────────────────────────────────


class AsyncOverlayClient:
    """Asynchronous read client. Usable as an async context manager."""

    def __init__(
        self,
        base_url: str = DEFAULT_OVERLAY_URL,
        *,
        timeout: float = DEFAULT_TIMEOUT_S,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = _base(base_url)
        self._timeout = timeout
        self._client = client or httpx.AsyncClient(timeout=timeout, headers=_JSON_HEADERS)
        self._owns_client = client is None

    async def __aenter__(self) -> "AsyncOverlayClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _get_json(self, path: str) -> Any:
        r = await self._client.get(f"{self.base_url}{path}")
        if r.status_code // 100 != 2:
            raise OverlayError(f"overlay {r.status_code} on {path}: {r.text[:200]}")
        return r.json()

    async def _get_json_or_null(self, path: str) -> Any:
        r = await self._client.get(f"{self.base_url}{path}")
        if r.status_code in (400, 404):
            return None
        if r.status_code // 100 != 2:
            raise OverlayError(f"overlay {r.status_code} on {path}: {r.text[:200]}")
        return r.json()

    async def resolve_identities(
        self, *, pubkeys: list[str] | None = None, addresses: list[str] | None = None
    ) -> dict[str, ResolvedIdentity]:
        body = _resolve_body(pubkeys, addresses)
        if body is None:
            return {}
        try:
            r = await self._client.post(
                f"{self.base_url}/v1/identities/resolve",
                json=body,
                headers={"content-type": "application/json"},
            )
            return _interp_resolve(r.status_code // 100 == 2, r.json() if r.content else None)
        except Exception:
            return {}

    async def get_identity(self, pubkey: str) -> IdentityBundle | None:
        if not pubkey:
            return None
        return _interp_identity(await self._get_json_or_null(f"/identity/{pubkey}"))

    async def resolve_handle(self, handle: str) -> HandleResolution | None:
        if not handle:
            return None
        return _interp_handle(await self._get_json_or_null(f"/resolve/{handle}"))

    async def get_profile(
        self, *, subject: str | None = None, owner: str | None = None, outpoint: str | None = None
    ) -> ProfileRow | None:
        q = _profile_query({"subject": subject, "owner": owner, "outpoint": outpoint})
        if q is None:
            return None
        resp = await self._client.get(f"{self.base_url}/v1/bio/profile", params=q)
        if resp.status_code in (400, 404):
            return None
        if resp.status_code // 100 != 2:
            raise OverlayError(f"overlay {resp.status_code} on /v1/bio/profile")
        return _interp_profile(resp.json())

    async def get_feed(self, **params: Any) -> FeedResponse:
        resp = await self._client.get(f"{self.base_url}/v1/feed", params=_feed_query(params))
        if resp.status_code // 100 != 2:
            raise OverlayError(f"overlay {resp.status_code} on /v1/feed: {resp.text[:200]}")
        return _interp_feed(resp.json())

    async def get_post(self, txid: str) -> PeckRow | None:
        if not txid:
            return None
        return _interp_post(await self._get_json_or_null(f"/v1/post/{txid}"))

    async def get_thread(self, txid: str) -> ThreadResponse:
        if not txid:
            return ThreadResponse(post=None, replies=[])
        return _interp_thread(await self._get_json_or_null(f"/v1/thread/{txid}"))

    async def get_state(self) -> OverlayState:
        return OverlayState.from_dict(await self._get_json("/state"))

    async def get_topic_root(self, topic: str) -> TopicState | None:
        if not topic:
            return None
        try:
            state = await self.get_state()
        except OverlayError:
            return None
        for t in state.topics:
            if t.topic == topic:
                return t
        return None

    async def get_anchor(self, topic: str) -> TopicAnchor | None:
        if not topic:
            return None
        try:
            state = await self.get_state()
        except OverlayError:
            return None
        for t in state.topics:
            if t.topic == topic:
                return t.anchor
        return None

    async def verify_root(self, topic: str) -> dict:
        empty = {"anchored": False, "matches_live": False, "live_root": None, "anchored_root": None, "txid": None}
        if not topic:
            return empty
        try:
            state = await self.get_state()
        except OverlayError:
            return empty
        t = next((x for x in state.topics if x.topic == topic), None)
        if t is None:
            return empty
        a = t.anchor
        return {
            "anchored": a is not None,
            "matches_live": bool(a and a.matches_live),
            "live_root": t.state_root,
            "anchored_root": a.root if a else None,
            "txid": a.txid if a else None,
        }


def create_overlay_client(base_url: str = DEFAULT_OVERLAY_URL, **kw: Any) -> OverlayClient:
    """Convenience factory for the sync client."""
    return OverlayClient(base_url, **kw)


def create_async_overlay_client(base_url: str = DEFAULT_OVERLAY_URL, **kw: Any) -> AsyncOverlayClient:
    """Convenience factory for the async client."""
    return AsyncOverlayClient(base_url, **kw)
