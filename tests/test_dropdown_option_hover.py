"""Tests for dropdown OPTION hover events (AMRI fork).

``GuiDropdownOptionHoverMessage`` mirrors ``GuiButtonHoverMessage`` in every
structural respect (a plain client->server event, no create/update/remove
entity lifecycle) -- see ``test_panel_moved.py`` for the sibling pattern this
one is modelled on, including its ``_wait_for`` polling idiom (dispatch runs
on ``_thread_executor``, a real ``ThreadPoolExecutor``). Unlike button hover
(``GuiButtonProps.hover_events``, opt-in, gated because an ordinary button
would otherwise generate extra traffic), a dropdown's OPTION hover has no
opt-in flag: the client always sends it for the open list, enabled or
disabled options alike -- the behaviour this replaces (per-branch preview
buttons) always had it too.
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
from viser._gui_handles import GuiDropdownOptionHoverEvent
from viser._messages import GuiDropdownOptionHoverMessage, Message
from viser.infra import ClientId


@pytest.fixture()
def server() -> Generator[viser.ViserServer, None, None]:
    viser._client_autobuild.ensure_client_is_built = lambda: None
    server = viser.ViserServer(port=0, verbose=False)
    yield server
    server.stop()


def _connect_fake_client(server: viser.ViserServer, cid: int) -> None:
    """Registers a resolvable (but otherwise inert) connected client -- the
    same shortcut ``test_panel_moved.py``/``test_panel_closable.py`` use."""
    server._connected_clients[cid] = cast(viser.ClientHandle, object())


def _wait_for(predicate, timeout: float = 2.0) -> None:  # type: ignore[no-untyped-def]
    """Polls ``predicate`` until it's truthy or ``timeout`` elapses -- see
    ``test_panel_moved.py``'s own ``_wait_for`` for why this is needed
    (dispatch happens on a real thread pool, so asserting on a callback's
    side effect immediately after ``await``ing the handler coroutine races)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.002)
    raise AssertionError("condition never became true")


def _run(coro) -> None:  # type: ignore[no-untyped-def]
    asyncio.run(coro)


# ---------------------------------------------------------------------------
# GuiDropdownOptionHoverMessage structure + wire round-trip.
# ---------------------------------------------------------------------------


def test_message_has_no_entity_lifecycle() -> None:
    """A transient client->server event like GuiButtonHoverMessage, not an
    entity with create/update/remove GC -- no entity markers, excluded from
    scene serialization."""
    assert GuiDropdownOptionHoverMessage.entity_type is None
    assert GuiDropdownOptionHoverMessage.lifecycle_phase is None
    assert GuiDropdownOptionHoverMessage.entity_id_field is None
    assert GuiDropdownOptionHoverMessage.include_in_scene_serialization is False


def test_message_round_trips_through_serializer_on_enter() -> None:
    msg = GuiDropdownOptionHoverMessage(uuid="abc123", option="branch_a")
    serialized = msg.as_serializable_dict()
    assert serialized["type"] == "GuiDropdownOptionHoverMessage"
    assert serialized["uuid"] == "abc123"
    assert serialized["option"] == "branch_a"

    decoded = Message.deserialize(msgspec.msgpack.encode(serialized))
    assert type(decoded) is GuiDropdownOptionHoverMessage
    assert decoded.uuid == msg.uuid  # type: ignore[attr-defined]
    assert decoded.option == msg.option  # type: ignore[attr-defined]


def test_message_round_trips_through_serializer_on_leave() -> None:
    msg = GuiDropdownOptionHoverMessage(uuid="abc123", option=None)
    serialized = msg.as_serializable_dict()
    assert serialized["option"] is None

    decoded = Message.deserialize(msgspec.msgpack.encode(serialized))
    assert type(decoded) is GuiDropdownOptionHoverMessage
    assert decoded.option is None  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# on_option_hover registration + dispatch via _handle_gui_dropdown_option_hover.
# ---------------------------------------------------------------------------


def test_on_option_hover_registers_and_returns_the_callback(
    server: viser.ViserServer,
) -> None:
    dropdown = server.gui.add_dropdown("Branch", options=("a", "b"))

    def _cb(event: GuiDropdownOptionHoverEvent) -> None:
        del event

    returned = dropdown.on_option_hover(_cb)
    assert returned is _cb
    assert dropdown._dropdown_impl.option_hover_cbs == [_cb]


def test_hover_message_dispatches_enter_with_the_option_value(
    server: viser.ViserServer,
) -> None:
    dropdown = server.gui.add_dropdown("Branch", options=("a", "b", "c"))
    calls: list[GuiDropdownOptionHoverEvent] = []
    dropdown.on_option_hover(lambda event: calls.append(event))

    _connect_fake_client(server, 0)
    try:
        _run(
            server.gui._handle_gui_dropdown_option_hover(
                ClientId(0),
                GuiDropdownOptionHoverMessage(uuid=dropdown._impl.uuid, option="b"),
            )
        )
    finally:
        server._connected_clients.pop(0, None)

    _wait_for(lambda: len(calls) == 1)
    assert calls[0].target is dropdown
    assert calls[0].option == "b"


def test_hover_message_dispatches_leave_with_none(
    server: viser.ViserServer,
) -> None:
    dropdown = server.gui.add_dropdown("Branch", options=("a", "b", "c"))
    calls: list[GuiDropdownOptionHoverEvent] = []
    dropdown.on_option_hover(lambda event: calls.append(event))

    _connect_fake_client(server, 0)
    try:
        _run(
            server.gui._handle_gui_dropdown_option_hover(
                ClientId(0),
                GuiDropdownOptionHoverMessage(uuid=dropdown._impl.uuid, option=None),
            )
        )
    finally:
        server._connected_clients.pop(0, None)

    _wait_for(lambda: len(calls) == 1)
    assert calls[0].target is dropdown
    assert calls[0].option is None


def test_hover_message_dispatches_to_every_on_option_hover_callback(
    server: viser.ViserServer,
) -> None:
    """A pure notification, same as button/panel hover: EVERY registered
    callback fires, disabled options included -- there is no single default
    action to replace."""
    dropdown = server.gui.add_dropdown(
        "Branch", options=("a", "b"), options_disabled=(False, True)
    )
    calls_a: list[GuiDropdownOptionHoverEvent] = []
    calls_b: list[GuiDropdownOptionHoverEvent] = []
    dropdown.on_option_hover(lambda event: calls_a.append(event))
    dropdown.on_option_hover(lambda event: calls_b.append(event))

    _connect_fake_client(server, 0)
    try:
        _run(
            server.gui._handle_gui_dropdown_option_hover(
                ClientId(0),
                GuiDropdownOptionHoverMessage(uuid=dropdown._impl.uuid, option="b"),
            )
        )
    finally:
        server._connected_clients.pop(0, None)

    _wait_for(lambda: len(calls_a) == 1 and len(calls_b) == 1)
    for calls in (calls_a, calls_b):
        assert len(calls) == 1
        # Fires for a disabled option too -- hover is a notification, not an
        # action the disabled state should gate.
        assert calls[0].option == "b"


def test_hover_message_with_no_callback_is_a_silent_no_op(
    server: viser.ViserServer,
) -> None:
    dropdown = server.gui.add_dropdown("Branch", options=("a", "b"))

    _connect_fake_client(server, 0)
    try:
        _run(
            server.gui._handle_gui_dropdown_option_hover(
                ClientId(0),
                GuiDropdownOptionHoverMessage(uuid=dropdown._impl.uuid, option="a"),
            )
        )
    finally:
        server._connected_clients.pop(0, None)

    assert dropdown._impl.removed is False


def test_hover_message_ignored_for_removed_dropdown(
    server: viser.ViserServer,
) -> None:
    dropdown = server.gui.add_dropdown("Branch", options=("a", "b"))
    calls: list[GuiDropdownOptionHoverEvent] = []
    dropdown.on_option_hover(lambda event: calls.append(event))
    uuid = dropdown._impl.uuid
    dropdown.remove()

    _connect_fake_client(server, 0)
    try:
        _run(
            server.gui._handle_gui_dropdown_option_hover(
                ClientId(0),
                GuiDropdownOptionHoverMessage(uuid=uuid, option="a"),
            )
        )
    finally:
        server._connected_clients.pop(0, None)

    assert calls == []


def test_hover_message_ignored_for_unknown_uuid(server: viser.ViserServer) -> None:
    # Should not raise even though "does-not-exist" was never registered.
    _connect_fake_client(server, 0)
    try:
        _run(
            server.gui._handle_gui_dropdown_option_hover(
                ClientId(0),
                GuiDropdownOptionHoverMessage(uuid="does-not-exist", option="a"),
            )
        )
    finally:
        server._connected_clients.pop(0, None)


def test_hover_message_ignored_when_client_unresolvable(
    server: viser.ViserServer,
) -> None:
    """No connected client behind the id (raced disconnect) -- dropped
    quietly, the same `_resolve_client` guard every other transient
    client->server handler uses."""
    dropdown = server.gui.add_dropdown("Branch", options=("a", "b"))
    calls: list[GuiDropdownOptionHoverEvent] = []
    dropdown.on_option_hover(lambda event: calls.append(event))

    _run(
        server.gui._handle_gui_dropdown_option_hover(
            ClientId(0),
            GuiDropdownOptionHoverMessage(uuid=dropdown._impl.uuid, option="a"),
        )
    )

    assert calls == []


@patch.object(viser._client_autobuild, "ensure_client_is_built", lambda: None)
def test_hover_message_ignored_for_non_dropdown_handle() -> None:
    """Guards against a uuid collision with some other input handle type --
    mirrors `_handle_gui_button_hover`'s own `isinstance(handle,
    GuiButtonHandle)` check."""
    server = viser.ViserServer(port=0, verbose=False)
    try:
        button = server.gui.add_button("Click me")

        _connect_fake_client(server, 0)
        try:
            _run(
                server.gui._handle_gui_dropdown_option_hover(
                    ClientId(0),
                    GuiDropdownOptionHoverMessage(uuid=button._impl.uuid, option="a"),
                )
            )
        finally:
            server._connected_clients.pop(0, None)
        # No assertion beyond "did not raise" -- there is nothing on a
        # button to have been notified.
    finally:
        server.stop()
