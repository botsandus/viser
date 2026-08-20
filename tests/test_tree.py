"""Contract tests for the server-driven tree widget (``add_tree``).

Mirrors the conventions in ``test_commands.py``: handle construction,
property round-tripping, callback registration, message queuing on
create/update/remove, and (since a tree's callbacks are plain positional
dispatches rather than ``GuiEvent``-wrapped ones) direct dispatch through the
registered websocket handlers.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any, Coroutine
from unittest.mock import patch

import viser
import viser._client_autobuild
from viser._messages import (
    GuiTreeExpandMessage,
    GuiTreeIconClickMessage,
    GuiTreeMessage,
    GuiTreeRowClickMessage,
    GuiUpdateMessage,
    TreeIcon,
    TreeRow,
)


def _run_coro(coro: Coroutine[Any, Any, Any]) -> Any:
    """Run a coroutine on a fresh event loop on a worker thread.

    Same rationale as ``tests/test_modifier_filtering.py``: some fixtures
    leave a running loop attached to the main thread, which breaks
    ``asyncio.run``/``run_until_complete`` if called directly here.
    """
    result: list[Any] = []
    error: list[BaseException] = []

    def _target() -> None:
        loop = asyncio.new_event_loop()
        try:
            result.append(loop.run_until_complete(coro))
        except BaseException as e:
            error.append(e)
        finally:
            loop.close()

    t = threading.Thread(target=_target)
    t.start()
    t.join()
    if error:
        raise error[0]
    return result[0]


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
            icons=(
                TreeIcon(name="lock-open", state="active"),
                TreeIcon(name="trash", state="active"),
            ),
            expanded=False,
        ),
    ]


@patch.object(viser._client_autobuild, "ensure_client_is_built", lambda: None)
def test_add_tree_returns_handle_with_rows() -> None:
    """add_tree() should return a handle whose `.rows` echoes what was passed."""
    server = viser.ViserServer()
    rows = _sample_rows()
    handle = server.gui.add_tree(rows)

    assert handle.rows == tuple(rows)
    assert handle.visible is True


@patch.object(viser._client_autobuild, "ensure_client_is_built", lambda: None)
def test_add_tree_sends_create_message() -> None:
    """add_tree() should queue a GuiTreeMessage carrying the initial rows."""
    server = viser.ViserServer()

    sent: list = []
    original_queue = server._websock_server.queue_message

    def capture_queue(message):
        sent.append(message)
        return original_queue(message)

    server._websock_server.queue_message = capture_queue

    rows = _sample_rows()
    handle = server.gui.add_tree(rows)

    create_msgs = [m for m in sent if isinstance(m, GuiTreeMessage)]
    assert len(create_msgs) == 1
    assert create_msgs[0].uuid == handle._impl.uuid
    assert create_msgs[0].props.rows == tuple(rows)


@patch.object(viser._client_autobuild, "ensure_client_is_built", lambda: None)
def test_tree_rows_setter_queues_full_update() -> None:
    """Assigning `.rows` is a full, server-driven replacement: it should be
    visible on the handle immediately and queue a GuiUpdateMessage carrying
    the new rows under the `rows` key (the generic AssignablePropsBase path
    shared with every other Gui*Props field)."""
    server = viser.ViserServer()

    sent: list = []
    original_queue = server._websock_server.queue_message

    def capture_queue(message):
        sent.append(message)
        return original_queue(message)

    handle = server.gui.add_tree(_sample_rows())
    server._websock_server.queue_message = capture_queue

    new_rows = _sample_rows() + [
        TreeRow(id="child2", parent_id="root", label="Child2", icons=())
    ]
    handle.rows = new_rows

    assert handle.rows == tuple(new_rows)

    update_msgs = [m for m in sent if isinstance(m, GuiUpdateMessage)]
    assert len(update_msgs) == 1
    assert update_msgs[0].uuid == handle._impl.uuid
    assert update_msgs[0].updates["rows"] == tuple(new_rows)


@patch.object(viser._client_autobuild, "ensure_client_is_built", lambda: None)
def test_tree_remove_cleans_up_registry() -> None:
    """remove() should tombstone the handle and drop it from the tree
    registry, mirroring CommandHandle's contract."""
    server = viser.ViserServer()
    handle = server.gui.add_tree(_sample_rows())

    uuid = handle._impl.uuid
    assert uuid in server.gui._tree_handle_from_uuid

    handle.remove()
    assert handle._impl.removed is True
    assert uuid not in server.gui._tree_handle_from_uuid


@patch.object(viser._client_autobuild, "ensure_client_is_built", lambda: None)
def test_reset_clears_trees() -> None:
    """reset() should remove all registered trees, like it does for commands."""
    server = viser.ViserServer()
    server.gui.add_tree(_sample_rows())
    server.gui.add_tree(_sample_rows())

    assert len(server.gui._tree_handle_from_uuid) == 2

    server.gui.reset()
    assert len(server.gui._tree_handle_from_uuid) == 0


@patch.object(viser._client_autobuild, "ensure_client_is_built", lambda: None)
def test_tree_on_click_dispatch() -> None:
    """on_click() callbacks fire with the clicked row's id when the client's
    GuiTreeRowClickMessage is dispatched."""
    server = viser.ViserServer()
    handle = server.gui.add_tree(_sample_rows())

    calls: list[str] = []
    handle.on_click(lambda row_id: calls.append(row_id))

    _run_coro(
        server.gui._handle_gui_tree_row_click(
            client_id=0,
            message=GuiTreeRowClickMessage(uuid=handle._impl.uuid, row_id="child"),
        )
    )
    assert calls == ["child"]


@patch.object(viser._client_autobuild, "ensure_client_is_built", lambda: None)
def test_tree_on_icon_click_dispatch() -> None:
    """on_icon_click() callbacks fire with (row_id, icon_index)."""
    server = viser.ViserServer()
    handle = server.gui.add_tree(_sample_rows())

    calls: list[tuple[str, int]] = []
    handle.on_icon_click(lambda row_id, icon_index: calls.append((row_id, icon_index)))

    _run_coro(
        server.gui._handle_gui_tree_icon_click(
            client_id=0,
            message=GuiTreeIconClickMessage(
                uuid=handle._impl.uuid, row_id="child", icon_index=1
            ),
        )
    )
    assert calls == [("child", 1)]


@patch.object(viser._client_autobuild, "ensure_client_is_built", lambda: None)
def test_tree_on_expand_change_dispatch() -> None:
    """on_expand_change() callbacks fire with (row_id, expanded)."""
    server = viser.ViserServer()
    handle = server.gui.add_tree(_sample_rows())

    calls: list[tuple[str, bool]] = []
    handle.on_expand_change(lambda row_id, expanded: calls.append((row_id, expanded)))

    _run_coro(
        server.gui._handle_gui_tree_expand(
            client_id=0,
            message=GuiTreeExpandMessage(
                uuid=handle._impl.uuid, row_id="child", expanded=True
            ),
        )
    )
    assert calls == [("child", True)]


@patch.object(viser._client_autobuild, "ensure_client_is_built", lambda: None)
def test_tree_dispatch_ignores_removed_handle() -> None:
    """A click/expand message for an already-removed tree should be a no-op,
    not raise -- mirrors the removed-guard on every other GUI handler."""
    server = viser.ViserServer()
    handle = server.gui.add_tree(_sample_rows())
    uuid = handle._impl.uuid

    calls: list[str] = []
    handle.on_click(lambda row_id: calls.append(row_id))
    handle.remove()

    _run_coro(
        server.gui._handle_gui_tree_row_click(
            client_id=0,
            message=GuiTreeRowClickMessage(uuid=uuid, row_id="child"),
        )
    )
    assert calls == []


@patch.object(viser._client_autobuild, "ensure_client_is_built", lambda: None)
def test_tree_dispatch_ignores_unknown_uuid() -> None:
    """A message referencing a uuid we never registered (e.g. a stale client)
    should be dropped silently."""
    server = viser.ViserServer()
    server.gui.add_tree(_sample_rows())

    # Should not raise even though "does-not-exist" was never registered.
    _run_coro(
        server.gui._handle_gui_tree_row_click(
            client_id=0,
            message=GuiTreeRowClickMessage(uuid="does-not-exist", row_id="child"),
        )
    )
