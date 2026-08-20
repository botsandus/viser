"""Contract tests for the generic inline number row widget (``add_number_row``).

Mirrors the conventions in ``tests/test_tree.py`` (handle construction,
property round-tripping, message queuing on create/update/remove) but --
unlike the tree widget -- a number row has a natural single ``value`` (a
tuple of floats), so it reuses the same generic value-sync machinery as
every other GUI input handle (``add_vector3``, ``add_multi_slider``, ...)
instead of bespoke click/action messages. Client-originated edits are
therefore exercised the same way ``test_handle_lifecycle_bugs.py`` exercises
``add_slider``: via ``server.gui._handle_gui_updates``.
"""

from __future__ import annotations

import asyncio
from typing import cast
from unittest.mock import patch

import pytest

import viser
import viser._client_autobuild
from viser._messages import GuiNumberRowMessage, GuiUpdateMessage
from viser.infra import ClientId

from .thread_isolation import run_isolated
from .utils import viser_server


@patch.object(viser._client_autobuild, "ensure_client_is_built", lambda: None)
def test_add_number_row_returns_handle_with_values() -> None:
    """add_number_row() should return a handle whose `.values` (and `.value`)
    echo the initial values, alongside the fixed `.labels`."""
    with viser_server() as server:
        handle = server.gui.add_number_row(("X", "Y", "Z"), (1.0, 2.0, 3.0))

        assert handle.values == (1.0, 2.0, 3.0)
        assert handle.value == (1.0, 2.0, 3.0)
        assert handle.labels == ("X", "Y", "Z")
        assert handle.visible is True
        assert handle.disabled is False


@patch.object(viser._client_autobuild, "ensure_client_is_built", lambda: None)
def test_add_number_row_sends_create_message() -> None:
    """add_number_row() should queue a GuiNumberRowMessage carrying the
    initial values and labels."""
    with viser_server() as server:
        sent: list = []
        original_queue = server._websock_server.queue_message

        def capture_queue(message):
            sent.append(message)
            return original_queue(message)

        server._websock_server.queue_message = capture_queue

        handle = server.gui.add_number_row(("Roll", "Pitch", "Yaw"), (0.0, 0.0, 0.0))

        create_msgs = [m for m in sent if isinstance(m, GuiNumberRowMessage)]
        assert len(create_msgs) == 1
        assert create_msgs[0].uuid == handle._impl.uuid
        assert create_msgs[0].value == (0.0, 0.0, 0.0)
        assert create_msgs[0].props.labels == ("Roll", "Pitch", "Yaw")


@patch.object(viser._client_autobuild, "ensure_client_is_built", lambda: None)
def test_add_number_row_rejects_label_value_length_mismatch() -> None:
    with viser_server() as server:
        with pytest.raises(ValueError, match="3 labels"):
            server.gui.add_number_row(("X", "Y", "Z"), (1.0, 2.0))


@patch.object(viser._client_autobuild, "ensure_client_is_built", lambda: None)
def test_add_number_row_rejects_empty_labels() -> None:
    with viser_server() as server:
        with pytest.raises(ValueError, match="at least one label"):
            server.gui.add_number_row((), ())


@patch.object(viser._client_autobuild, "ensure_client_is_built", lambda: None)
def test_number_row_values_setter_queues_update() -> None:
    """Assigning `.values` should be visible immediately and queue a
    GuiUpdateMessage carrying the new tuple under the `value` key -- the
    generic `_GuiInputHandle` path shared with every other value-holding
    widget."""
    with viser_server() as server:
        handle = server.gui.add_number_row(("X", "Y", "Z"), (0.0, 0.0, 0.0))

        sent: list = []
        original_queue = server._websock_server.queue_message

        def capture_queue(message):
            sent.append(message)
            return original_queue(message)

        server._websock_server.queue_message = capture_queue

        handle.values = (1.0, 2.0, 3.0)

        assert handle.values == (1.0, 2.0, 3.0)
        assert handle.value == (1.0, 2.0, 3.0)

        update_msgs = [m for m in sent if isinstance(m, GuiUpdateMessage)]
        assert len(update_msgs) == 1
        assert update_msgs[0].uuid == handle._impl.uuid
        assert update_msgs[0].updates["value"] == (1.0, 2.0, 3.0)


@patch.object(viser._client_autobuild, "ensure_client_is_built", lambda: None)
def test_number_row_value_and_values_are_aliases() -> None:
    """`.value` and `.values` are two names for the same underlying state --
    assigning either is visible through both."""
    with viser_server() as server:
        handle = server.gui.add_number_row(("X", "Y"), (0.0, 0.0))

        handle.value = (5.0, 6.0)
        assert handle.values == (5.0, 6.0)

        handle.values = (7.0, 8.0)
        assert handle.value == (7.0, 8.0)


@patch.object(viser._client_autobuild, "ensure_client_is_built", lambda: None)
def test_number_row_values_setter_rejects_length_mismatch() -> None:
    """Assigning a tuple of the wrong length must raise instead of silently
    desyncing the client (which zips values against labels 1:1)."""
    with viser_server() as server:
        handle = server.gui.add_number_row(("X", "Y", "Z"), (0.0, 0.0, 0.0))

        with pytest.raises(ValueError, match="expected 3 values"):
            handle.values = (1.0, 2.0)

        # The prior (valid) values should be untouched after the rejected
        # assignment.
        assert handle.values == (0.0, 0.0, 0.0)


@patch.object(viser._client_autobuild, "ensure_client_is_built", lambda: None)
def test_number_row_disabled_and_visible_round_trip() -> None:
    with viser_server() as server:
        handle = server.gui.add_number_row(
            ("X", "Y"), (0.0, 0.0), disabled=True, visible=False
        )
        assert handle.disabled is True
        assert handle.visible is False

        handle.disabled = False
        handle.visible = True
        assert handle.disabled is False
        assert handle.visible is True


@patch.object(viser._client_autobuild, "ensure_client_is_built", lambda: None)
def test_number_row_remove_cleans_up_registry() -> None:
    """remove() should tombstone the handle and drop it from the generic
    input-handle registry, like every other value-holding GUI element."""
    with viser_server() as server:
        handle = server.gui.add_number_row(("X", "Y"), (0.0, 0.0))

        uuid = handle._impl.uuid
        assert uuid in server.gui._gui_input_handle_from_uuid

        handle.remove()
        assert handle._impl.removed is True
        assert uuid not in server.gui._gui_input_handle_from_uuid


@patch.object(viser._client_autobuild, "ensure_client_is_built", lambda: None)
def test_number_row_on_update_dispatch() -> None:
    """on_update() callbacks fire with a GuiEvent whose `.target.values` is
    the FULL updated tuple, not just the entry the client changed -- this is
    what a consumer editing one field of a compact transform needs to read
    back the other, untouched fields."""
    cid = ClientId(0)
    with viser_server() as server:
        handle = server.gui.add_number_row(("X", "Y", "Z"), (1.0, 2.0, 3.0))

        calls: list[tuple[float, ...]] = []

        @handle.on_update
        def _(event: viser.GuiEvent) -> None:
            calls.append(event.target.values)

        server._connected_clients[0] = cast(viser.ClientHandle, object())
        try:
            run_isolated(
                lambda: asyncio.run(
                    server.gui._handle_gui_updates(
                        cid,
                        GuiUpdateMessage(
                            uuid=handle._impl.uuid,
                            updates={"value": [9.0, 2.0, 3.0]},
                        ),
                    )
                )
            )
        finally:
            server._connected_clients.pop(0, None)

        assert calls == [(9.0, 2.0, 3.0)]
        assert handle.values == (9.0, 2.0, 3.0)


@patch.object(viser._client_autobuild, "ensure_client_is_built", lambda: None)
def test_reset_clears_number_rows() -> None:
    """reset() should remove number rows along with every other GUI input,
    via the generic root-container child walk."""
    with viser_server() as server:
        h1 = server.gui.add_number_row(("X", "Y"), (0.0, 0.0))
        h2 = server.gui.add_number_row(("X", "Y", "Z"), (0.0, 0.0, 0.0))

        assert h1._impl.uuid in server.gui._gui_input_handle_from_uuid
        assert h2._impl.uuid in server.gui._gui_input_handle_from_uuid

        server.gui.reset()

        assert h1._impl.uuid not in server.gui._gui_input_handle_from_uuid
        assert h2._impl.uuid not in server.gui._gui_input_handle_from_uuid
