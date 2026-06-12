# overlay-social (Python)

[![PyPI version](https://img.shields.io/pypi/v/overlay-social.svg)](https://pypi.org/project/overlay-social/)
[![CI](https://github.com/overlay-social/sdk-python/actions/workflows/ci.yml/badge.svg)](https://github.com/overlay-social/sdk-python/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Open%20BSV-blue.svg)](LICENSE)

Read-only Python client for **overlay.peck.to** — the canonical peck social
overlay on BSV. Identity resolution, profiles, handles, feed, threads, and
overlay topic-state. Sync **and** async. The Python sibling of
[`@overlay-social/sdk`](https://www.npmjs.com/package/@overlay-social/sdk).

It is a **pure read lens**. It does not write, mint, pay, or federate — none of
those exist on the live service. It speaks the REST facade that actually runs
today.

## Install

```bash
pip install overlay-social
```

## Use

```python
from overlay_social import create_overlay_client

overlay = create_overlay_client()  # https://overlay.peck.to

# Overlay topic-state (counts + state-roots)
state = overlay.get_state()
for t in state.topics:
    print(t.topic, t.count, t.state_root[:10])

# Batch-resolve feed authors to canonical ProfileToken identity.
# Pass P2PKH base58 in `addresses`, pubkey-hex subjects in `pubkeys`.
# ONE round-trip per feed page — never per row.
ids = overlay.resolve_identities(addresses=["1Abc...", "1Def..."])
for key, ident in ids.items():
    print(key, ident.handle, ident.display_name, ident.avatar_ref)

# Single lookups return None when there's no canonical token (never raise).
profile = overlay.get_profile(subject="02...")        # ProfileRow | None
who     = overlay.resolve_handle("thomas")             # HandleResolution | None
bundle  = overlay.get_identity("02...")                # IdentityBundle | None
```

### Async (FastAPI / Starlette / FastHTML)

```python
from overlay_social import create_async_overlay_client

async with create_async_overlay_client() as overlay:
    feed = await overlay.get_feed(limit=20, type="post")
    ids = await overlay.resolve_identities(
        addresses=[row.get("author") for row in feed.data]
    )
```

## Error semantics

Mirrors the overlay's load-bearing role for other apps:

- `resolve_identities` returns `{}` on **any** error and omits keys without a
  canonical ProfileToken (ghost authors). A feed UI can enrich defensively and
  never break.
- Single-item lookups (`get_identity`, `resolve_handle`, `get_profile`,
  `get_post`) return `None` for missing/invalid (404/400/empty).
- Only `get_feed` and `get_state` raise `OverlayError` on a genuine 5xx /
  network failure.
- Every request has a hard timeout (default 8s).

## Social graph & notifications (0.2.0)

```python
graph = overlay.get_friends("<identity-root-pubkey>")
graph.mutual        # active friendships (both directions attested, BRC-3)
graph.pending_in    # incoming requests
graph.pending_out   # outgoing requests

notifs = overlay.get_notifications("<posting-address>", limit=50)
# -> [NotificationItem(type='friend_request'|'like'|'reply'|'follow'|'mention', actor=..., ...)]

overlay.get_follows("<address>")          # follower/following counts + rows
overlay.get_blocks("<address>")           # OUTGOING block/mute list only
overlay.get_feed(near={"lat": 59.94, "lng": 10.76}, radius_km=2)   # geo
overlay.get_feed(bbox=(10.5, 59.8, 11.0, 60.1))                    # bounding box
overlay.verify_root("tm_social-content")  # on-chain anchor vs live state-root
```

All graph/notification reads are best-effort: safe empties on error, so
social UI never bricks on enrichment. Friendship is **mutual consent** —
two one-way BRC-3 attestations form an active pair; legacy BAP-era friend
rows are exposed display-only.

## Endpoints used

`GET /state`, `GET /v1/topic/:topic/root`, `POST /v1/identities/resolve`,
`GET /v1/identities`, `GET /identity/:pubkey`, `GET /resolve/:handle`,
`GET /v1/bio/profile`, `GET /v1/feed` (incl. `near`/`bbox`),
`GET /v1/post/:txid`, `GET /v1/thread/:txid`, `GET /v1/friends/:subject`,
`GET /v1/notifications/:address`, `GET /v1/follows/:address`,
`GET /v1/blocks/:address`. WhatsOnChain is **never** called.

## License

Open BSV License v5 — usable only on the Bitcoin SV blockchain, by design.
