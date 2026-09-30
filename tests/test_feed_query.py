"""Offline tests for the /v1/feed query the clients send.

No network: the clients are given an ``httpx`` mock transport that records the
request, so these run everywhere (unlike the live tests in ``test_client.py``).
"""

from __future__ import annotations

import httpx
import pytest

from overlay_social import AsyncOverlayClient, OverlayClient

_EMPTY_FEED = {"status": "ok", "data": [], "limit": 50, "offset": 0}


def _recording_handler(calls: list[httpx.Request]):
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json=_EMPTY_FEED)

    return handler


def _sync_client(calls: list[httpx.Request]) -> OverlayClient:
    transport = httpx.MockTransport(_recording_handler(calls))
    return OverlayClient(base_url="https://overlay.test", client=httpx.Client(transport=transport))


def _async_client(calls: list[httpx.Request]) -> AsyncOverlayClient:
    transport = httpx.MockTransport(_recording_handler(calls))
    return AsyncOverlayClient(
        base_url="https://overlay.test", client=httpx.AsyncClient(transport=transport)
    )


# Oslo: longitude about 10.7, latitude about 59.9.
# The argument is (west, south, east, north), longitude first (GeoJSON order).
OSLO_BBOX = (10.6, 59.8, 10.9, 60.0)
# The overlay reads minLat,minLng,maxLat,maxLng.
OSLO_WIRE = "59.8,10.6,60.0,10.9"


def test_bbox_is_sent_latitude_first_sync() -> None:
    calls: list[httpx.Request] = []
    with _sync_client(calls) as o:
        o.get_feed(bbox=OSLO_BBOX)
    assert calls[0].url.params["bbox"] == OSLO_WIRE


@pytest.mark.asyncio
async def test_bbox_is_sent_latitude_first_async() -> None:
    calls: list[httpx.Request] = []
    async with _async_client(calls) as o:
        await o.get_feed(bbox=OSLO_BBOX)
    assert calls[0].url.params["bbox"] == OSLO_WIRE


def test_bbox_accepts_a_list_and_integers() -> None:
    calls: list[httpx.Request] = []
    with _sync_client(calls) as o:
        o.get_feed(bbox=[10, 59, 11, 60])
    assert calls[0].url.params["bbox"] == "59,10,60,11"


def test_near_wins_over_bbox_and_keeps_its_wire_format() -> None:
    calls: list[httpx.Request] = []
    with _sync_client(calls) as o:
        o.get_feed(near={"lat": 59.9, "lng": 10.7}, radius_km=3, bbox=(1, 2, 3, 4))
    params = calls[0].url.params
    assert params["near"] == "59.9,10.7"
    assert params["radius_km"] == "3"
    assert "bbox" not in params


def test_no_bbox_param_without_a_geo_filter() -> None:
    calls: list[httpx.Request] = []
    with _sync_client(calls) as o:
        o.get_feed(limit=5)
    assert "bbox" not in calls[0].url.params


@pytest.mark.parametrize("bad", [(1, 2, 3), (1, 2, 3, 4, 5), 7])
def test_bbox_with_the_wrong_shape_is_rejected_before_any_request(bad: object) -> None:
    calls: list[httpx.Request] = []
    with _sync_client(calls) as o:
        with pytest.raises(ValueError, match="west, south, east, north"):
            o.get_feed(bbox=bad)
    assert calls == []
