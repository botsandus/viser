"""Tests for tree row drag-and-drop (AMRI fork).

``GuiTreeRowDropMessage`` mirrors the shape of dropdown option hover: a
transient client->server event, dispatched with a fixed, non-generic
``GuiTreeRowDropEvent`` (see ``test_dropdown_option_hover.py``'s own
``_wait_for``/``_connect_fake_client`` pattern this is modelled on) -- unlike
the tree's other three callbacks (row click, icon click, expand), which are
plain positional dispatches with no client identity attached.

Opt-in: a tree only reports row drops when created with
``rows_draggable=True`` (default ``False``, matching what the client renders
without the flag). The server handler re-checks that flag itself (not just
trusting the client to gate its own messages), so a stray
``GuiTreeRowDropMessage`` for a non-opted-in tree produces no callback side
effects either.
"""

from __future__ import annotations

import asyncio
import time
from typing import Generator, cast

import pytest

import viser
import viser._client_autobuild
from viser._gui_handles import GuiTreeRowDropEvent
from viser._messages import (
    GuiTreeMessage,
    GuiTreeRowDropMessage,
    TreeIcon,
    TreeRow,
)
from viser.infra import ClientId


@pytest.fixture()
def server() -> Generator[viser.ViserServer, None, None]:
    viser._client_autobuild.ensure_client_is_built = lambda: None
    server = viser.ViserServer(port=0, verbose=False)
    yield server
    server.stop()


def _connect_fake_client(server: viser.ViserServer, cid: int) -> None:
    """Registers a resolvable (but otherwise inert) connected client -- the
    same shortcut ``test_dropdown_option_hover.py``/``test_panel_moved.py``
    use."""
    server._connected_clients[cid] = cast(viser.ClientHandle, object())


def _wait_for(predicate, timeout: float = 2.0) -> None:  # type: ignore[no-untyped-def]
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.002)
    raise AssertionError("condition never became true")


def _run(coro) -> None:  # type: ignore[no-untyped-def]
    asyncio.run(coro)


def _sample_rows() -> list[TreeRow]:
    return [
        TreeRow(
            id="root",
            parent_id=None,
            label="Root",
            icons=(TreeIcon(name="eye", state="active"),),
        ),
        TreeRow(
            id="child",
            parent_id="root",
            label="Child",
            icons=(),
        ),
        TreeRow(
            id="sibling",
            parent_id="root",
            label="Sibling",
            icons=(),
        ),
    ]


# ---------------------------------------------------------------------------
# rows_draggable: default off, byte-for-byte otherwise; opt-in is threaded
# through to the create message and to the live handle read.
# ---------------------------------------------------------------------------


def test_rows_draggable_defaults_to_false(server: viser.ViserServer) -> None:
    handle = server.gui.add_tree(_sample_rows())
    assert handle.rows_draggable is False


def test_rows_draggable_true_is_threaded_through_to_create_message(
    server: viser.ViserServer,
) -> None:
    sent: list = []
    original_queue = server._websock_server.queue_message

    def capture_queue(message):
        sent.append(message)
        return original_queue(message)

    server._websock_server.queue_message = capture_queue

    handle = server.gui.add_tree(_sample_rows(), rows_draggable=True)

    assert handle.rows_draggable is True
    create_msgs = [m for m in sent if isinstance(m, GuiTreeMessage)]
    assert len(create_msgs) == 1
    assert create_msgs[0].props.rows_draggable is True


# ---------------------------------------------------------------------------
# on_row_drop registration + dispatch via _handle_gui_tree_row_drop.
# ---------------------------------------------------------------------------


def test_on_row_drop_registers_and_returns_the_callback(
    server: viser.ViserServer,
) -> None:
    tree = server.gui.add_tree(_sample_rows(), rows_draggable=True)

    def _cb(event: GuiTreeRowDropEvent) -> None:
        del event

    returned = tree.on_row_drop(_cb)
    assert returned is _cb
    assert tree._tree_impl.row_drop_cb == [_cb]


@pytest.mark.parametrize("position", ["into", "before", "after"])
def test_row_drop_message_dispatches_with_the_right_event_fields(
    server: viser.ViserServer, position: str
) -> None:
    tree = server.gui.add_tree(_sample_rows(), rows_draggable=True)
    calls: list[GuiTreeRowDropEvent] = []
    tree.on_row_drop(lambda event: calls.append(event))

    _connect_fake_client(server, 0)
    try:
        _run(
            server.gui._handle_gui_tree_row_drop(
                ClientId(0),
                GuiTreeRowDropMessage(
                    uuid=tree._impl.uuid,
                    row_id="child",
                    target_row_id="sibling",
                    position=position,  # type: ignore[arg-type]
                ),
            )
        )
    finally:
        server._connected_clients.pop(0, None)

    _wait_for(lambda: len(calls) == 1)
    event = calls[0]
    assert event.target is tree
    assert event.row_id == "child"
    assert event.target_row_id == "sibling"
    assert event.position == position
    assert event.client_id == 0


def test_row_drop_dispatches_to_every_registered_callback(
    server: viser.ViserServer,
) -> None:
    tree = server.gui.add_tree(_sample_rows(), rows_draggable=True)
    calls_a: list[GuiTreeRowDropEvent] = []
    calls_b: list[GuiTreeRowDropEvent] = []
    tree.on_row_drop(lambda event: calls_a.append(event))
    tree.on_row_drop(lambda event: calls_b.append(event))

    _connect_fake_client(server, 0)
    try:
        _run(
            server.gui._handle_gui_tree_row_drop(
                ClientId(0),
                GuiTreeRowDropMessage(
                    uuid=tree._impl.uuid,
                    row_id="child",
                    target_row_id="sibling",
                    position="into",
                ),
            )
        )
    finally:
        server._connected_clients.pop(0, None)

    _wait_for(lambda: len(calls_a) == 1 and len(calls_b) == 1)


# ---------------------------------------------------------------------------
# The flag off (default rows_draggable=False): no message handler side
# effects, even if a message somehow arrives anyway.
# ---------------------------------------------------------------------------


def test_row_drop_message_is_a_no_op_when_rows_draggable_is_false(
    server: viser.ViserServer,
) -> None:
    tree = server.gui.add_tree(_sample_rows())  # rows_draggable defaults False
    calls: list[GuiTreeRowDropEvent] = []
    tree.on_row_drop(lambda event: calls.append(event))

    _connect_fake_client(server, 0)
    try:
        _run(
            server.gui._handle_gui_tree_row_drop(
                ClientId(0),
                GuiTreeRowDropMessage(
                    uuid=tree._impl.uuid,
                    row_id="child",
                    target_row_id="sibling",
                    position="into",
                ),
            )
        )
    finally:
        server._connected_clients.pop(0, None)

    assert calls == []


# ---------------------------------------------------------------------------
# Removed-handle / unknown-uuid / unresolvable-client conventions, mirroring
# test_tree.py and test_dropdown_option_hover.py.
# ---------------------------------------------------------------------------


def test_row_drop_ignored_for_removed_tree(server: viser.ViserServer) -> None:
    tree = server.gui.add_tree(_sample_rows(), rows_draggable=True)
    calls: list[GuiTreeRowDropEvent] = []
    tree.on_row_drop(lambda event: calls.append(event))
    uuid = tree._impl.uuid
    tree.remove()

    _connect_fake_client(server, 0)
    try:
        _run(
            server.gui._handle_gui_tree_row_drop(
                ClientId(0),
                GuiTreeRowDropMessage(
                    uuid=uuid,
                    row_id="child",
                    target_row_id="sibling",
                    position="into",
                ),
            )
        )
    finally:
        server._connected_clients.pop(0, None)

    assert calls == []


def test_row_drop_ignored_for_unknown_uuid(server: viser.ViserServer) -> None:
    server.gui.add_tree(_sample_rows(), rows_draggable=True)

    # Should not raise even though "does-not-exist" was never registered.
    _connect_fake_client(server, 0)
    try:
        _run(
            server.gui._handle_gui_tree_row_drop(
                ClientId(0),
                GuiTreeRowDropMessage(
                    uuid="does-not-exist",
                    row_id="child",
                    target_row_id="sibling",
                    position="into",
                ),
            )
        )
    finally:
        server._connected_clients.pop(0, None)


def test_row_drop_ignored_when_client_unresolvable(
    server: viser.ViserServer,
) -> None:
    """No connected client behind the id (raced disconnect) -- dropped
    quietly, the same `_resolve_client` guard every other transient
    client->server handler uses."""
    tree = server.gui.add_tree(_sample_rows(), rows_draggable=True)
    calls: list[GuiTreeRowDropEvent] = []
    tree.on_row_drop(lambda event: calls.append(event))

    _run(
        server.gui._handle_gui_tree_row_drop(
            ClientId(0),
            GuiTreeRowDropMessage(
                uuid=tree._impl.uuid,
                row_id="child",
                target_row_id="sibling",
                position="into",
            ),
        )
    )

    assert calls == []
