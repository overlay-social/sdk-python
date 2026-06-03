"""Live integration tests against overlay.peck.to.

These hit the real overlay (read-only, safe). Skipped automatically if the
network/endpoint is unreachable so the suite stays green offline.

    pip install -e .[test]   # or: pip install pytest pytest-asyncio
    pytest
"""

from __future__ import annotations

import pytest

from overlay_social import (
    AsyncOverlayClient,
    OverlayClient,
    OverlayState,
    create_overlay_client,
)


def _overlay_up() -> bool:
    try:
        with create_overlay_client(timeout=6.0) as o:
            return o.get_state().status == "ok"
    except Exception:
        return False


live = pytest.mark.skipif(not _overlay_up(), reason="overlay.peck.to unreachable")


@live
def test_get_state_sync() -> None:
    with OverlayClient() as o:
        state = o.get_state()
    assert isinstance(state, OverlayState)
    assert state.status == "ok"
    assert state.network == "main"
    assert any(t.topic == "tm_peck-bio-profile" for t in state.topics)
    # state-roots are 64-hex sha256
    for t in state.topics:
        assert len(t.state_root) == 64


@live
def test_get_topic_root_sync() -> None:
    with OverlayClient() as o:
        root = o.get_topic_root("peck-schema")
        missing = o.get_topic_root("does-not-exist")
    assert root is not None and root.topic == "peck-schema"
    assert missing is None


@live
def test_resolve_identities_never_raises_and_omits_ghosts() -> None:
    with OverlayClient() as o:
        # garbage + empty are simply absent; the call returns a dict, never raises
        ids = o.resolve_identities(addresses=["1NotARealAddressZZZ"])
    assert isinstance(ids, dict)
    assert "1NotARealAddressZZZ" not in ids


@live
def test_single_lookups_return_none_for_missing() -> None:
    with OverlayClient() as o:
        assert o.resolve_handle("definitely-no-such-handle-zzz") is None
        assert o.get_post("00" * 32) is None
        assert o.get_profile(subject="02" + "00" * 32) is None


@live
def test_get_feed_shape() -> None:
    with OverlayClient() as o:
        feed = o.get_feed(limit=3)
    assert feed.status == "ok"
    assert isinstance(feed.data, list)
    assert feed.limit == 3


@live
@pytest.mark.asyncio
async def test_async_state_matches_sync() -> None:
    async with AsyncOverlayClient() as o:
        astate = await o.get_state()
    with OverlayClient() as o:
        sstate = o.get_state()
    assert astate.status == sstate.status == "ok"
    assert {t.topic for t in astate.topics} == {t.topic for t in sstate.topics}
