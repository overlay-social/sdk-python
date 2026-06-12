# Changelog

All notable changes to `overlay-social` (Python). Mirrors
`@overlay-social/sdk` (TypeScript) one-to-one.

## 0.2.0 — 2026-06-12

### Added
- `get_friends(subject)` (sync + async) — mutual-consent friendship graph
  (`GET /v1/friends/:subject`): `FriendsGraph` with `mutual` / `pending_in` /
  `pending_out` (two one-way BRC-3 attestations = an active pair) plus
  legacy BAP-era rows (display-only). Safe-empty on error.
- `get_notifications(address, limit=, offset=, mentions=)` (sync + async) —
  likes, replies, follows, mentions and friend requests targeting a posting
  address. `[]` on error.
- `get_follows(address)` / `get_blocks(address, kind=)` (sync + async).
  Blocks are outgoing-only by design (the overlay does not expose
  who-blocked-me).
- Geo feed queries: `get_feed(near={"lat":..,"lng":..}, radius_km=..)` and
  `get_feed(bbox=(w, s, e, n))`.
- Models: `FriendEntry`, `FriendsGraph`, `NotificationItem`.

### Changed
- `get_topic_root(topic)` uses the real per-topic route
  (`GET /v1/topic/:topic/root`) with a `/state` fallback. The per-topic route
  does not carry the anchor — use `get_anchor()`/`verify_root()`.
- Identity docs: the live overlay collapses BOUND posting keys/addresses
  (key-binding) into their identity root and prefers light self-attested
  profiles/handles over legacy ProfileTokens. Same response shapes.

## 0.1.0 — 2026-06-03

- Initial release: sync + async clients — `resolve_identities`,
  `list_identities`, `get_identity`, `resolve_handle`, `get_profile`,
  `get_feed`, `get_post`, `get_thread`, `get_state`, `get_topic_root`,
  `get_anchor`, `verify_root`.
