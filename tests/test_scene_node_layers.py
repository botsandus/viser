"""Tests for the per-scene-node render-layer bitmask.

``SetSceneNodeLayersMessage`` mirrors ``SetSceneNodeVisibilityMessage`` in
every structural respect (same entity markers, same round-trip through the
message serializer); ``SceneNodeHandle.layers`` mirrors
``SceneNodeHandle.visible``. Additive-only: the default (1, i.e. bit 0 only)
must reproduce today's rendering for any node that never touches this.
"""

from __future__ import annotations

from typing import Generator

import msgspec.msgpack
import pytest

import viser
import viser._client_autobuild
from viser._messages import Message, SetSceneNodeLayersMessage

from .infra_utils import broadcast_messages


@pytest.fixture()
def server() -> Generator[viser.ViserServer, None, None]:
    viser._client_autobuild.ensure_client_is_built = lambda: None
    server = viser.ViserServer(port=0, verbose=False)
    yield server
    server.stop()


# ---------------------------------------------------------------------------
# SetSceneNodeLayersMessage structure + wire round-trip.
# ---------------------------------------------------------------------------


def test_layers_message_shares_visibility_messages_entity_markers() -> None:
    """Same (entity_type, lifecycle_phase, entity_id_field) as
    SetSceneNodeVisibilityMessage -- it follows the identical
    create/update/remove GC and redundancy-key rules."""
    assert SetSceneNodeLayersMessage.entity_type == "scene"
    assert SetSceneNodeLayersMessage.lifecycle_phase == "update_simple"
    assert SetSceneNodeLayersMessage.entity_id_field == "name"
    assert SetSceneNodeLayersMessage.include_in_scene_serialization is True


def test_layers_message_round_trips_through_serializer() -> None:
    """Serialize -> msgpack encode -> Message.deserialize must reproduce the
    original message, the same way test_scene_scopes.py exercises
    SetSceneNodeVisibilityMessage and friends."""
    msg = SetSceneNodeLayersMessage(name="/n", layers=6)
    serialized = msg.as_serializable_dict()
    assert serialized["type"] == "SetSceneNodeLayersMessage"
    assert serialized["name"] == "/n"
    assert serialized["layers"] == 6
    # Owner is init=False, default "" -- always on the wire regardless.
    assert serialized["owner"] == ""

    decoded = Message.deserialize(msgspec.msgpack.encode(serialized))
    assert type(decoded) is SetSceneNodeLayersMessage
    assert decoded.name == msg.name  # type: ignore[attr-defined]
    assert decoded.layers == msg.layers  # type: ignore[attr-defined]
    assert decoded.owner == msg.owner  # type: ignore[attr-defined]


def test_layers_message_redundancy_key_distinct_from_visibility() -> None:
    """update_simple messages key by type -- a pending SetSceneNodeLayers
    must not collide with (or be evicted by) a SetSceneNodeVisibility for
    the same node."""
    from viser._messages import SetSceneNodeVisibilityMessage

    layers = SetSceneNodeLayersMessage(name="/n", layers=2)
    vis = SetSceneNodeVisibilityMessage(name="/n", visible=False)
    assert layers.redundancy_key() != vis.redundancy_key()

    # Same type + same node -> same slot (coalesces, latest wins).
    assert (
        SetSceneNodeLayersMessage(name="/n", layers=4).redundancy_key()
        == layers.redundancy_key()
    )
    # Different node -> different slot.
    assert (
        SetSceneNodeLayersMessage(name="/other", layers=2).redundancy_key()
        != layers.redundancy_key()
    )


# ---------------------------------------------------------------------------
# SceneNodeHandle.layers.
# ---------------------------------------------------------------------------


def test_handle_layers_defaults_to_one(server: viser.ViserServer) -> None:
    """A fresh handle's layers default to bit 0 only -- the same bitmask a
    fresh three.js Object3D starts with, so a node that never sets this
    renders exactly as before the feature existed."""
    handle = server.scene.add_icosphere("/ball", radius=0.1)
    assert handle.layers == 1


def test_handle_layers_setter_queues_message_and_updates_impl(
    server: viser.ViserServer,
) -> None:
    """Assigning .layers queues a SetSceneNodeLayersMessage (mirrors
    .visible's setter) and updates the handle's cached state."""
    handle = server.scene.add_icosphere("/ball", radius=0.1)
    handle.layers = 2

    assert handle.layers == 2

    layer_msgs = [
        msg
        for msg in broadcast_messages(server)
        if isinstance(msg, SetSceneNodeLayersMessage) and msg.name == "/ball"
    ]
    assert len(layer_msgs) == 1
    assert layer_msgs[0].layers == 2


def test_handle_layers_setter_is_a_noop_when_unchanged(
    server: viser.ViserServer,
) -> None:
    """Assigning the same value again must not queue a second message (same
    equality short-circuit as .visible's setter)."""
    handle = server.scene.add_icosphere("/ball", radius=0.1)
    handle.layers = 2

    before = len(
        [
            msg
            for msg in broadcast_messages(server)
            if isinstance(msg, SetSceneNodeLayersMessage) and msg.name == "/ball"
        ]
    )
    handle.layers = 2  # Same value -- no-op.
    after = len(
        [
            msg
            for msg in broadcast_messages(server)
            if isinstance(msg, SetSceneNodeLayersMessage) and msg.name == "/ball"
        ]
    )
    assert before == after == 1
