"""Tests for GetRenderRequestMessage.hide_nodes.

Shaped after tests/test_scene_node_layers.py: message defaults +
round-trip, then get_render()'s parameter actually reaching the wire
message. hide_nodes is a per-request capture override (not a persistent
scene-node property like layers), so there is no handle-property half to
test here -- only the message and the get_render() plumbing.
"""

from __future__ import annotations

import time
from typing import Generator

import msgspec.msgpack
import numpy as np
import pytest

import viser
import viser._client_autobuild
from viser._messages import GetRenderRequestMessage, Message

from .infra_utils import client_buffer_messages, make_synthetic_client


@pytest.fixture()
def server() -> Generator[viser.ViserServer, None, None]:
    # Same fixture as test_scene_node_layers.py: skip the real client
    # (autobuild's node/npm dance) for tests that only exercise server-side
    # message plumbing.
    viser._client_autobuild.ensure_client_is_built = lambda: None
    server = viser.ViserServer(port=0, verbose=False)
    yield server
    server.stop()


def _request_kwargs(**overrides: object) -> dict:
    kwargs: dict = dict(
        format="image/jpeg",
        height=8,
        width=8,
        quality=80,
        wxyz=(1.0, 0.0, 0.0, 0.0),
        position=(0.0, 0.0, 0.0),
        fov=1.0,
        render_uuid="uuid",
    )
    kwargs.update(overrides)
    return kwargs


# ---------------------------------------------------------------------------
# GetRenderRequestMessage.hide_nodes structure + wire round-trip.
# ---------------------------------------------------------------------------


def test_hide_nodes_defaults_to_empty_tuple() -> None:
    """A caller that never touches hide_nodes must reproduce today's
    rendering byte for byte -- the additive-only invariant starts here."""
    msg = GetRenderRequestMessage(**_request_kwargs())
    assert msg.hide_nodes == ()


def test_hide_nodes_round_trips_through_serializer() -> None:
    """Serialize -> msgpack encode -> Message.deserialize must reproduce the
    original message, the same way test_scene_node_layers.py exercises
    SetSceneNodeLayersMessage."""
    msg = GetRenderRequestMessage(**_request_kwargs(hide_nodes=("/gizmo", "/other")))
    serialized = msg.as_serializable_dict()
    assert serialized["type"] == "GetRenderRequestMessage"
    assert list(serialized["hide_nodes"]) == ["/gizmo", "/other"]

    decoded = Message.deserialize(msgspec.msgpack.encode(serialized))
    assert type(decoded) is GetRenderRequestMessage
    assert tuple(decoded.hide_nodes) == msg.hide_nodes  # type: ignore[attr-defined]


def test_hide_nodes_empty_round_trips() -> None:
    """The default (no hide_nodes passed) must also round-trip cleanly --
    an empty tuple/list is not the same failure mode as a populated one."""
    msg = GetRenderRequestMessage(**_request_kwargs())
    serialized = msg.as_serializable_dict()
    assert list(serialized["hide_nodes"]) == []

    decoded = Message.deserialize(msgspec.msgpack.encode(serialized))
    assert tuple(decoded.hide_nodes) == ()  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# get_render()'s hide_nodes parameter reaching the queued message.
# ---------------------------------------------------------------------------


def test_get_render_threads_hide_nodes_into_request_message(
    server: viser.ViserServer,
) -> None:
    """client.get_render(hide_nodes=...) must appear verbatim on the
    GetRenderRequestMessage it queues. No response is ever delivered here,
    so the call times out -- we only care what hit the buffer before then."""
    client = make_synthetic_client(server, client_id=910_001)
    server._connected_clients[client.client_id] = client
    try:
        with pytest.raises(TimeoutError):
            client.get_render(
                height=8,
                width=8,
                wxyz=(1.0, 0.0, 0.0, 0.0),
                position=(0.0, 0.0, 0.0),
                fov=1.0,
                timeout=0.25,
                hide_nodes=("/gizmo",),
            )
    finally:
        server._connected_clients.pop(client.client_id, None)

    requests = [
        m
        for m in client_buffer_messages(client)
        if isinstance(m, GetRenderRequestMessage)
    ]
    assert len(requests) == 1
    assert requests[0].hide_nodes == ("/gizmo",)


def test_get_render_default_hide_nodes_is_empty(server: viser.ViserServer) -> None:
    """A get_render() call that never passes hide_nodes must queue a request
    with hide_nodes == () -- the client-side additive-only guarantee."""
    client = make_synthetic_client(server, client_id=910_002)
    server._connected_clients[client.client_id] = client
    try:
        with pytest.raises(TimeoutError):
            client.get_render(
                height=8,
                width=8,
                wxyz=(1.0, 0.0, 0.0, 0.0),
                position=(0.0, 0.0, 0.0),
                fov=1.0,
                timeout=0.25,
            )
    finally:
        server._connected_clients.pop(client.client_id, None)

    requests = [
        m
        for m in client_buffer_messages(client)
        if isinstance(m, GetRenderRequestMessage)
    ]
    assert len(requests) == 1
    assert requests[0].hide_nodes == ()


def test_camera_handle_alias_threads_hide_nodes_into_request_message(
    server: viser.ViserServer,
) -> None:
    """CameraHandle.get_render() (the client.camera-side alias) must also
    thread hide_nodes into the message -- it forwards to
    ClientHandle.get_render() rather than duplicating the request build."""
    client = make_synthetic_client(server, client_id=910_003)
    server._connected_clients[client.client_id] = client
    # The alias reads camera.position/wxyz/fov directly; a real client sets
    # these from its first CameraStateMessage, which this synthetic client
    # never sends.
    client.camera._state.wxyz = np.array([1.0, 0.0, 0.0, 0.0])
    client.camera._state.position = np.zeros(3)
    client.camera._state.fov = 1.0
    client.camera._state.update_timestamp = time.time()
    try:
        with pytest.raises(TimeoutError):
            client.camera.get_render(
                height=8,
                width=8,
                timeout=0.25,
                hide_nodes=("/tool-gizmo",),
            )
    finally:
        server._connected_clients.pop(client.client_id, None)

    requests = [
        m
        for m in client_buffer_messages(client)
        if isinstance(m, GetRenderRequestMessage)
    ]
    assert len(requests) == 1
    assert requests[0].hide_nodes == ("/tool-gizmo",)
