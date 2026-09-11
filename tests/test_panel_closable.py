"""Tests for closable standalone panels (AMRI fork).

``GuiPanelCloseMessage`` mirrors ``GuiButtonHoverMessage`` in every
structural respect (a plain client->server event, no create/update/remove
entity lifecycle): see ``test_scene_node_layers.py`` for the analogous
message-shape tests on a different feature. ``PanelHandle.closable`` /
``.on_close`` mirror ``GuiButtonHandle``'s prop + callback pattern
(``.hover_events`` / ``.on_hover``).

Additive-only: the default (``closable=False``) must reproduce today's
behavior -- no close message is ever sent by the client, and the server
drops one anyway if it somehow arrived.
"""

from __future__ import annotations

import asyncio
from typing import Generator, cast
from unittest.mock import patch

import msgspec.msgpack
import pytest

import viser
import viser._client_autobuild
from viser._messages import GuiPanelCloseMessage, GuiPanelMessage, Message
from viser.infra import ClientId

from .infra_utils import broadcast_messages


@pytest.fixture()
def server() -> Generator[viser.ViserServer, None, None]:
    viser._client_autobuild.ensure_client_is_built = lambda: None
    server = viser.ViserServer(port=0, verbose=False)
    yield server
    server.stop()


def _connect_fake_client(server: viser.ViserServer, cid: int) -> None:
    """Registers a resolvable (but otherwise inert) connected client, the
    same shortcut ``test_number_row.py`` uses for dispatch tests that need
    ``_resolve_client`` to succeed."""
    server._connected_clients[cid] = cast(viser.ClientHandle, object())


def _run(coro) -> None:  # type: ignore[no-untyped-def]
    asyncio.run(coro)


# ---------------------------------------------------------------------------
# GuiPanelCloseMessage structure + wire round-trip.
# ---------------------------------------------------------------------------


def test_close_message_has_no_entity_lifecycle() -> None:
    """A transient client->server event like GuiButtonHoverMessage, not an
    entity with create/update/remove GC -- no entity markers, excluded from
    scene serialization."""
    assert GuiPanelCloseMessage.entity_type is None
    assert GuiPanelCloseMessage.lifecycle_phase is None
    assert GuiPanelCloseMessage.entity_id_field is None
    assert GuiPanelCloseMessage.include_in_scene_serialization is False


def test_close_message_round_trips_through_serializer() -> None:
    msg = GuiPanelCloseMessage(uuid="abc123")
    serialized = msg.as_serializable_dict()
    assert serialized["type"] == "GuiPanelCloseMessage"
    assert serialized["uuid"] == "abc123"

    decoded = Message.deserialize(msgspec.msgpack.encode(serialized))
    assert type(decoded) is GuiPanelCloseMessage
    assert decoded.uuid == msg.uuid  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# add_panel(closable=...) / PanelHandle.closable.
# ---------------------------------------------------------------------------


def test_add_panel_closable_defaults_false(server: viser.ViserServer) -> None:
    """A fresh panel's closable defaults to False -- the client draws no
    close (X) control, reproducing pre-existing behavior exactly."""
    panel = server.gui.add_panel()
    assert panel.closable is False

    create_msgs = [
        msg
        for msg in broadcast_messages(server)
        if isinstance(msg, GuiPanelMessage) and msg.uuid == panel._impl.uuid
    ]
    assert len(create_msgs) == 1
    assert create_msgs[0].props.closable is False


def test_add_panel_closable_true_is_carried_on_the_create_message(
    server: viser.ViserServer,
) -> None:
    panel = server.gui.add_panel(closable=True)
    assert panel.closable is True

    create_msgs = [
        msg
        for msg in broadcast_messages(server)
        if isinstance(msg, GuiPanelMessage) and msg.uuid == panel._impl.uuid
    ]
    assert len(create_msgs) == 1
    assert create_msgs[0].props.closable is True


# ---------------------------------------------------------------------------
# on_close registration + dispatch via _handle_gui_panel_close.
# ---------------------------------------------------------------------------


def test_on_close_registers_and_returns_the_callback(
    server: viser.ViserServer,
) -> None:
    panel = server.gui.add_panel(closable=True)

    def _cb(event: viser.GuiEvent) -> None:
        del event

    returned = panel.on_close(_cb)
    assert returned is _cb
    assert panel._close_cbs == [_cb]


def test_close_message_dispatches_to_on_close_callback(
    server: viser.ViserServer,
) -> None:
    """A closable panel's registered on_close callback fires on
    GuiPanelCloseMessage -- and, since a callback IS registered, the default
    remove() action does not also run."""
    panel = server.gui.add_panel(closable=True)
    calls: list[viser.GuiEvent] = []
    panel.on_close(lambda event: calls.append(event))

    _connect_fake_client(server, 0)
    try:
        _run(
            server.gui._handle_gui_panel_close(
                ClientId(0), GuiPanelCloseMessage(uuid=panel._impl.uuid)
            )
        )
    finally:
        server._connected_clients.pop(0, None)

    assert len(calls) == 1
    assert calls[0].target is panel
    assert panel._impl.removed is False  # the callback, not the default, ran


def test_close_message_with_no_callback_removes_the_panel(
    server: viser.ViserServer,
) -> None:
    """closable=True with no on_close wired: the default action is
    remove() -- so closable alone is enough to make the X functional."""
    panel = server.gui.add_panel(closable=True)
    assert panel._impl.removed is False

    _connect_fake_client(server, 0)
    try:
        _run(
            server.gui._handle_gui_panel_close(
                ClientId(0), GuiPanelCloseMessage(uuid=panel._impl.uuid)
            )
        )
    finally:
        server._connected_clients.pop(0, None)

    assert panel._impl.removed is True
    assert panel._impl.uuid not in server.gui._panel_handle_from_uuid


def test_close_message_ignored_when_panel_not_closable(
    server: viser.ViserServer,
) -> None:
    """The server does not trust the client blindly: a close request for a
    closable=False panel is dropped even if one somehow arrives."""
    panel = server.gui.add_panel(closable=False)
    calls: list[viser.GuiEvent] = []
    panel.on_close(lambda event: calls.append(event))

    _connect_fake_client(server, 0)
    try:
        _run(
            server.gui._handle_gui_panel_close(
                ClientId(0), GuiPanelCloseMessage(uuid=panel._impl.uuid)
            )
        )
    finally:
        server._connected_clients.pop(0, None)

    assert calls == []
    assert panel._impl.removed is False


def test_close_message_ignored_for_removed_panel(
    server: viser.ViserServer,
) -> None:
    panel = server.gui.add_panel(closable=True)
    calls: list[viser.GuiEvent] = []
    panel.on_close(lambda event: calls.append(event))
    uuid = panel._impl.uuid
    panel.remove()

    _connect_fake_client(server, 0)
    try:
        _run(
            server.gui._handle_gui_panel_close(
                ClientId(0), GuiPanelCloseMessage(uuid=uuid)
            )
        )
    finally:
        server._connected_clients.pop(0, None)

    assert calls == []


def test_close_message_ignored_for_unknown_uuid(server: viser.ViserServer) -> None:
    # Should not raise even though "does-not-exist" was never registered.
    _connect_fake_client(server, 0)
    try:
        _run(
            server.gui._handle_gui_panel_close(
                ClientId(0), GuiPanelCloseMessage(uuid="does-not-exist")
            )
        )
    finally:
        server._connected_clients.pop(0, None)


@patch.object(viser._client_autobuild, "ensure_client_is_built", lambda: None)
def test_props_dataclass_field_has_no_default() -> None:
    """closable itself must obey the same no-field-defaults rule every other
    props field does (see test_handle_prop_reads.py) -- the default lives in
    add_panel's signature."""
    import dataclasses

    from viser import _messages

    fields = {f.name: f for f in dataclasses.fields(_messages.GuiPanelProps)}
    assert "closable" in fields
    assert fields["closable"].default is dataclasses.MISSING
    assert fields["closable"].default_factory is dataclasses.MISSING
