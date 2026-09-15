"""Tests for ``GuiTabHandle.activate()`` (AMRI fork).

``GuiTabActivateMessage`` mirrors ``SetGuiPanelLabelMessage`` in every
structural respect: a plain server->client command, no create/update/remove
entity lifecycle -- the client just applies it. ``activate()`` itself mirrors
``CommandHandle.on_trigger``'s removed-guard: an operation OTHER than
``remove()`` raises on an already-removed handle, rather than warning like
``remove()`` does on a double-remove.

Both tab-container kinds (a standalone ``PanelHandle`` and an inline
``GuiTabGroupHandle``) share ``_TabContainerMixin``, so a tab's ``activate()``
is exercised once per container kind below to confirm the message carries
that container's own uuid in both cases.
"""

from __future__ import annotations

from typing import Generator, List

import msgspec.msgpack
import pytest

import viser
from viser._messages import GuiTabActivateMessage, Message


@pytest.fixture()
def server() -> Generator[viser.ViserServer, None, None]:
    server = viser.ViserServer(port=0, verbose=False)
    yield server
    server.stop()


def _patch_queue_message(server: viser.ViserServer) -> List[Message]:
    """Records every message queued to the server's websock interface."""
    sent: List[Message] = []
    real_queue_message = server.gui._websock_interface.queue_message

    def recording_queue_message(message: Message) -> None:
        sent.append(message)
        real_queue_message(message)

    server.gui._websock_interface.queue_message = recording_queue_message  # type: ignore[method-assign]
    return sent


# ---------------------------------------------------------------------------
# Message structure + wire round-trip.
# ---------------------------------------------------------------------------


def test_message_has_no_entity_lifecycle() -> None:
    """A plain server->client command like SetGuiPanelLabelMessage, not an
    entity with its own create/update/remove GC -- no entity markers, and
    excluded from scene serialization (nothing to replay)."""
    assert GuiTabActivateMessage.entity_type is None
    assert GuiTabActivateMessage.lifecycle_phase is None
    assert GuiTabActivateMessage.entity_id_field is None
    assert GuiTabActivateMessage.include_in_scene_serialization is False


def test_message_round_trips_through_serializer() -> None:
    msg = GuiTabActivateMessage(
        container_uuid="panel-uuid", tab_container_id="tab-uuid"
    )
    serialized = msg.as_serializable_dict()
    assert serialized["type"] == "GuiTabActivateMessage"
    assert serialized["container_uuid"] == "panel-uuid"
    assert serialized["tab_container_id"] == "tab-uuid"

    decoded = Message.deserialize(msgspec.msgpack.encode(serialized))
    assert type(decoded) is GuiTabActivateMessage
    assert decoded.container_uuid == msg.container_uuid  # type: ignore[attr-defined]
    assert decoded.tab_container_id == msg.tab_container_id  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# GuiTabHandle.activate()
# ---------------------------------------------------------------------------


def test_activate_sends_expected_message_for_tab_group(
    server: viser.ViserServer,
) -> None:
    group = server.gui.add_tab_group()
    tab_a = group.add_tab("A")
    group.add_tab("B")
    sent = _patch_queue_message(server)

    tab_a.activate()

    activate_messages = [m for m in sent if isinstance(m, GuiTabActivateMessage)]
    assert len(activate_messages) == 1
    assert activate_messages[0].container_uuid == group._impl.uuid
    assert activate_messages[0].tab_container_id == tab_a._id


def test_activate_sends_expected_message_for_standalone_panel(
    server: viser.ViserServer,
) -> None:
    panel = server.gui.add_panel()
    tab_a = panel.add_tab("A")
    sent = _patch_queue_message(server)

    tab_a.activate()

    activate_messages = [m for m in sent if isinstance(m, GuiTabActivateMessage)]
    assert len(activate_messages) == 1
    assert activate_messages[0].container_uuid == panel._impl.uuid
    assert activate_messages[0].tab_container_id == tab_a._id


def test_activate_on_removed_tab_raises(server: viser.ViserServer) -> None:
    """Unlike remove() on an already-removed handle (which warns), activate()
    on a removed handle raises -- the same shape as on_trigger's removed-guard
    on CommandHandle, and add_tab's own removed-container guard."""
    group = server.gui.add_tab_group()
    tab_a = group.add_tab("A")
    tab_a.remove()

    with pytest.raises(RuntimeError, match="removed"):
        tab_a.activate()


def test_activate_after_sibling_removed_still_targets_correct_tab(
    server: viser.ViserServer,
) -> None:
    """Removing a sibling tab must not shift which tab activate() targets --
    GuiTabHandle carries its own stable _id, no index arithmetic."""
    group = server.gui.add_tab_group()
    tab_a = group.add_tab("A")
    tab_b = group.add_tab("B")
    tab_a.remove()
    sent = _patch_queue_message(server)

    tab_b.activate()

    activate_messages = [m for m in sent if isinstance(m, GuiTabActivateMessage)]
    assert len(activate_messages) == 1
    assert activate_messages[0].tab_container_id == tab_b._id
