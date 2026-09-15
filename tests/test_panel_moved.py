"""Tests for a floating panel's user-driven move report (AMRI fork).

``GuiPanelMovedMessage`` mirrors ``GuiPanelCloseMessage`` in every
structural respect (a plain client->server event, no create/update/remove
entity lifecycle) -- see ``test_panel_closable.py`` for the sibling feature
this one is modelled on. ``PanelHandle.on_move`` mirrors ``.on_close``'s
registration shape, but is a pure NOTIFICATION (every registered callback
fires; there is no single default action to replace, and nothing here for
the server to approve or refuse -- see the message's own docstring).
"""

from __future__ import annotations

import asyncio
import time
from typing import Generator, cast
from unittest.mock import patch

import msgspec.msgpack
import pytest

import viser
import viser._client_autobuild
from viser._gui_handles import GuiPanelMoveEvent
from viser._messages import GuiPanelMovedMessage, Message
from viser.infra import ClientId


@pytest.fixture()
def server() -> Generator[viser.ViserServer, None, None]:
    viser._client_autobuild.ensure_client_is_built = lambda: None
    server = viser.ViserServer(port=0, verbose=False)
    yield server
    server.stop()


def _connect_fake_client(server: viser.ViserServer, cid: int) -> None:
    """Registers a resolvable (but otherwise inert) connected client -- the
    same shortcut ``test_panel_closable.py`` uses."""
    server._connected_clients[cid] = cast(viser.ClientHandle, object())


def _wait_for(predicate, timeout: float = 2.0) -> None:  # type: ignore[no-untyped-def]
    """Polls ``predicate`` until it's truthy or ``timeout`` elapses --
    dispatch here runs on ``_thread_executor`` (a real ``ThreadPoolExecutor``,
    unlike ``_handle_gui_panel_close``'s own tests, which happen to pass
    synchronously-fast enough not to need this), so asserting on a callback's
    side effect immediately after ``await``ing the handler coroutine is a
    genuine race -- the same polling idiom `test_handle_lifecycle_bugs.py`'s
    own `wait_for_request` uses, one condition over."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.002)
    raise AssertionError("condition never became true")


def _run(coro) -> None:  # type: ignore[no-untyped-def]
    asyncio.run(coro)


# ---------------------------------------------------------------------------
# GuiPanelMovedMessage structure + wire round-trip.
# ---------------------------------------------------------------------------


def test_moved_message_has_no_entity_lifecycle() -> None:
    """A transient client->server event like GuiPanelCloseMessage, not an
    entity with create/update/remove GC -- no entity markers, excluded from
    scene serialization."""
    assert GuiPanelMovedMessage.entity_type is None
    assert GuiPanelMovedMessage.lifecycle_phase is None
    assert GuiPanelMovedMessage.entity_id_field is None
    assert GuiPanelMovedMessage.include_in_scene_serialization is False


def test_moved_message_round_trips_through_serializer() -> None:
    msg = GuiPanelMovedMessage(uuid="abc123", x=12.5, y=-3.0, docked=False)
    serialized = msg.as_serializable_dict()
    assert serialized["type"] == "GuiPanelMovedMessage"
    assert serialized["uuid"] == "abc123"
    assert serialized["x"] == 12.5
    assert serialized["y"] == -3.0
    assert serialized["docked"] is False

    decoded = Message.deserialize(msgspec.msgpack.encode(serialized))
    assert type(decoded) is GuiPanelMovedMessage
    assert decoded.uuid == msg.uuid  # type: ignore[attr-defined]
    assert decoded.x == msg.x  # type: ignore[attr-defined]
    assert decoded.y == msg.y  # type: ignore[attr-defined]
    assert decoded.docked == msg.docked  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# on_move registration + dispatch via _handle_gui_panel_moved.
# ---------------------------------------------------------------------------


def test_on_move_registers_and_returns_the_callback(
    server: viser.ViserServer,
) -> None:
    panel = server.gui.add_panel()

    def _cb(event: GuiPanelMoveEvent) -> None:
        del event

    returned = panel.on_move(_cb)
    assert returned is _cb
    assert panel._move_cbs == [_cb]


def test_moved_message_dispatches_to_every_on_move_callback(
    server: viser.ViserServer,
) -> None:
    """Unlike on_close (one action, replaced by a registered callback),
    on_move is a pure notification: EVERY registered callback fires, and
    there is no default action to skip."""
    panel = server.gui.add_panel()
    calls_a: list[GuiPanelMoveEvent] = []
    calls_b: list[GuiPanelMoveEvent] = []
    panel.on_move(lambda event: calls_a.append(event))
    panel.on_move(lambda event: calls_b.append(event))

    _connect_fake_client(server, 0)
    try:
        _run(
            server.gui._handle_gui_panel_moved(
                ClientId(0),
                GuiPanelMovedMessage(
                    uuid=panel._impl.uuid, x=40.0, y=-15.0, docked=False
                ),
            )
        )
    finally:
        server._connected_clients.pop(0, None)

    _wait_for(lambda: len(calls_a) == 1 and len(calls_b) == 1)
    for calls in (calls_a, calls_b):
        assert len(calls) == 1
        assert calls[0].target is panel
        assert calls[0].x == 40.0
        assert calls[0].y == -15.0
        assert calls[0].docked is False
    # A notification, never an action: the panel is left exactly as it was.
    assert panel._impl.removed is False


def test_moved_message_with_no_callback_is_a_silent_no_op(
    server: viser.ViserServer,
) -> None:
    """No on_move registered: the panel just stays wherever the client
    already put it (see the message's own docstring) -- nothing raises,
    nothing else happens."""
    panel = server.gui.add_panel()

    _connect_fake_client(server, 0)
    try:
        _run(
            server.gui._handle_gui_panel_moved(
                ClientId(0),
                GuiPanelMovedMessage(uuid=panel._impl.uuid, x=1.0, y=2.0, docked=False),
            )
        )
    finally:
        server._connected_clients.pop(0, None)

    assert panel._impl.removed is False


def test_moved_message_ignored_for_removed_panel(server: viser.ViserServer) -> None:
    panel = server.gui.add_panel()
    calls: list[GuiPanelMoveEvent] = []
    panel.on_move(lambda event: calls.append(event))
    uuid = panel._impl.uuid
    panel.remove()

    _connect_fake_client(server, 0)
    try:
        _run(
            server.gui._handle_gui_panel_moved(
                ClientId(0),
                GuiPanelMovedMessage(uuid=uuid, x=1.0, y=2.0, docked=False),
            )
        )
    finally:
        server._connected_clients.pop(0, None)

    assert calls == []


def test_moved_message_ignored_for_unknown_uuid(server: viser.ViserServer) -> None:
    # Should not raise even though "does-not-exist" was never registered.
    _connect_fake_client(server, 0)
    try:
        _run(
            server.gui._handle_gui_panel_moved(
                ClientId(0),
                GuiPanelMovedMessage(uuid="does-not-exist", x=1.0, y=2.0, docked=False),
            )
        )
    finally:
        server._connected_clients.pop(0, None)


def test_moved_message_ignored_when_client_unresolvable(
    server: viser.ViserServer,
) -> None:
    """No connected client behind the id (raced disconnect) -- dropped
    quietly, the same `_resolve_client` guard every other transient
    client->server handler uses."""
    panel = server.gui.add_panel()
    calls: list[GuiPanelMoveEvent] = []
    panel.on_move(lambda event: calls.append(event))

    _run(
        server.gui._handle_gui_panel_moved(
            ClientId(0),
            GuiPanelMovedMessage(uuid=panel._impl.uuid, x=1.0, y=2.0, docked=False),
        )
    )

    assert calls == []


@patch.object(viser._client_autobuild, "ensure_client_is_built", lambda: None)
def test_on_move_works_without_closable() -> None:
    """Unlike the close (X) affordance, a move report needs no opt-in prop:
    every standalone panel can be dragged, so on_move is available on a
    plain add_panel() with no closable=True."""
    server = viser.ViserServer(port=0, verbose=False)
    try:
        panel = server.gui.add_panel()
        assert panel.closable is False

        def _cb(event: GuiPanelMoveEvent) -> None:
            del event

        panel.on_move(_cb)
        assert panel._move_cbs == [_cb]
    finally:
        server.stop()
