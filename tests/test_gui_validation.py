"""Validation contracts for GUI inputs that take an options list.

Empty options previously produced a raw ``IndexError`` from ``options[0]``;
these now raise a descriptive ``ValueError``.

Also: container-context misuse (overlapping ``with`` blocks on one handle).
"""

import threading
from unittest.mock import patch

import pytest

import viser
import viser._client_autobuild

from .utils import viser_server


@patch.object(viser._client_autobuild, "ensure_client_is_built", lambda: None)
def test_add_dropdown_rejects_empty_options() -> None:
    server = viser.ViserServer()
    with pytest.raises(ValueError, match="at least one option"):
        server.gui.add_dropdown("Empty", options=[])


@patch.object(viser._client_autobuild, "ensure_client_is_built", lambda: None)
def test_add_button_group_rejects_empty_options() -> None:
    server = viser.ViserServer()
    with pytest.raises(ValueError, match="at least one option"):
        server.gui.add_button_group("Empty", options=[])


@patch.object(viser._client_autobuild, "ensure_client_is_built", lambda: None)
def test_dropdown_options_setter_rejects_empty() -> None:
    server = viser.ViserServer()
    dropdown = server.gui.add_dropdown("D", options=["a", "b"])
    with pytest.raises(ValueError, match="at least one option"):
        dropdown.options = []
    # The prior (valid) options should be untouched after the rejected assignment.
    assert dropdown.options == ("a", "b")


@patch.object(viser._client_autobuild, "ensure_client_is_built", lambda: None)
def test_dropdown_options_disabled_defaults_to_none() -> None:
    """No `options_disabled`/`options_title` given means every option is
    enabled and carries no hover title -- the pre-existing behaviour, still
    the default now that both are optional kwargs."""
    server = viser.ViserServer()
    dropdown = server.gui.add_dropdown("D", options=["a", "b", "c"])
    assert dropdown.options_disabled is None
    assert dropdown.options_title is None


@patch.object(viser._client_autobuild, "ensure_client_is_built", lambda: None)
def test_dropdown_options_disabled_and_title_round_trip() -> None:
    """A per-option disabled/title list passed at construction reads back
    unchanged, and the two are independent (a disabled option needn't carry
    a title, and vice versa)."""
    server = viser.ViserServer()
    dropdown = server.gui.add_dropdown(
        "D",
        options=["a", "b", "c"],
        options_disabled=[False, True, False],
        options_title=[None, "filtered by the current branch", None],
    )
    assert dropdown.options_disabled == (False, True, False)
    assert dropdown.options_title == (None, "filtered by the current branch", None)


@patch.object(viser._client_autobuild, "ensure_client_is_built", lambda: None)
def test_add_dropdown_rejects_mismatched_options_disabled_length() -> None:
    server = viser.ViserServer()
    with pytest.raises(ValueError, match="options_disabled has"):
        server.gui.add_dropdown("D", options=["a", "b"], options_disabled=[True])


@patch.object(viser._client_autobuild, "ensure_client_is_built", lambda: None)
def test_add_dropdown_rejects_mismatched_options_title_length() -> None:
    server = viser.ViserServer()
    with pytest.raises(ValueError, match="options_title has"):
        server.gui.add_dropdown("D", options=["a", "b"], options_title=["only one"])


@patch.object(viser._client_autobuild, "ensure_client_is_built", lambda: None)
def test_dropdown_options_disabled_setter_validates_length() -> None:
    server = viser.ViserServer()
    dropdown = server.gui.add_dropdown("D", options=["a", "b"])
    dropdown.options_disabled = [True, False]
    assert dropdown.options_disabled == (True, False)
    with pytest.raises(ValueError, match="options_disabled has"):
        dropdown.options_disabled = [True]
    # The prior (valid) assignment is untouched by the rejected one.
    assert dropdown.options_disabled == (True, False)
    dropdown.options_disabled = None
    assert dropdown.options_disabled is None


@patch.object(viser._client_autobuild, "ensure_client_is_built", lambda: None)
def test_folder_context_rejects_overlapping_entry() -> None:
    """A container handle supports one active ``with`` block at a time: a
    second enter -- self-nesting or a concurrent enter from another thread --
    raises instead of corrupting the first block's restore slot. Sequential
    re-entry stays legal."""
    with viser_server() as server:
        folder = server.gui.add_folder("F")

        # Self-nesting.
        with folder:
            with pytest.raises(RuntimeError, match="one active"):
                with folder:
                    pass

        # Concurrent entry from another thread while the block is held open.
        entered = threading.Event()
        release = threading.Event()

        def hold_open() -> None:
            with folder:
                entered.set()
                release.wait(timeout=5.0)

        thread = threading.Thread(target=hold_open)
        thread.start()
        try:
            assert entered.wait(timeout=5.0)
            with pytest.raises(RuntimeError, match="another thread"):
                with folder:
                    pass
        finally:
            release.set()
            thread.join(timeout=5.0)
        assert not thread.is_alive()

        # Sequential re-entry after both blocks closed works, and elements
        # land in the folder.
        with folder:
            button = server.gui.add_button("ok")
        assert button._impl.parent_container_id == folder._impl.uuid


@patch.object(viser._client_autobuild, "ensure_client_is_built", lambda: None)
def test_tab_context_rejects_overlapping_entry() -> None:
    """Same overlapping-entry contract for tab handles."""
    with viser_server() as server:
        tab = server.gui.add_tab_group().add_tab("T")
        with tab:
            with pytest.raises(RuntimeError, match="one active"):
                with tab:
                    pass
        with tab:  # Sequential re-entry is fine.
            server.gui.add_button("ok")


@patch.object(viser._client_autobuild, "ensure_client_is_built", lambda: None)
def test_slider_precision_covers_value_grid() -> None:
    """Slider display precision must cover the value grid min + k*step (and
    the clamped max), not just the step: with min=0.5, step=1.0 every legal
    value ends in .5, and step-derived precision of 0 made the client's
    number box display 2.5 as "3" and reject typed decimals."""
    with viser_server() as server:

        def precision_of(handle) -> int:
            return handle._impl.props.precision

        # Off-grid min: the original regression.
        s = server.gui.add_slider("a", min=0.5, max=9.5, step=1.0, initial_value=2.5)
        assert precision_of(s) == 1
        # Integer grid stays integer (no float-noise regression).
        s = server.gui.add_slider("b", min=0, max=10, step=1, initial_value=5)
        assert precision_of(s) == 0
        # Step finer than min/max.
        s = server.gui.add_slider("c", min=0, max=1, step=0.01, initial_value=0.5)
        assert precision_of(s) == 2
        # Fractional min finer than step.
        s = server.gui.add_slider("d", min=0.05, max=1.05, step=0.1, initial_value=0.05)
        assert precision_of(s) == 2
        # Off-grid max is a legal (clamped) value.
        s = server.gui.add_slider("e", min=0, max=9.5, step=1, initial_value=0)
        assert precision_of(s) == 1

        # Multi-slider uses the same rule.
        m = server.gui.add_multi_slider(
            "f", min=0.5, max=9.5, step=1.0, initial_value=(1.5, 2.5)
        )
        assert precision_of(m) == 1


@patch.object(viser._client_autobuild, "ensure_client_is_built", lambda: None)
def test_number_and_vector_precision_covers_creation_values() -> None:
    """Number/vector inputs aren't grid-bound, so display precision must
    also cover the creation-time value and bounds when an explicit step is
    coarser than them: add_number(initial_value=0.25, step=0.5) displayed
    the value as "0.2"."""
    with viser_server() as server:

        def precision_of(handle) -> int:
            return handle._impl.props.precision

        n = server.gui.add_number("a", initial_value=0.25, step=0.5)
        assert precision_of(n) == 2
        # Auto-computed step already covers value/bounds; stays tight.
        n = server.gui.add_number("b", initial_value=2)
        assert precision_of(n) == 0
        n = server.gui.add_number("c", initial_value=1.0, min=0.05, step=1.0)
        assert precision_of(n) == 2

        v = server.gui.add_vector2("d", initial_value=(0.25, 1.0), step=0.5)
        assert precision_of(v) == 2
        v = server.gui.add_vector3(
            "e", initial_value=(1.0, 2.0, 3.0), min=(0.125, 0.0, 0.0), step=0.5
        )
        assert precision_of(v) == 3


@patch.object(viser._client_autobuild, "ensure_client_is_built", lambda: None)
def test_slider_nudge_step_defaults_to_none() -> None:
    """No `nudge_step` given means the client renders the slider exactly as
    before -- no inline -/+ buttons."""
    server = viser.ViserServer()
    slider = server.gui.add_slider("S", min=0, max=10, step=1, initial_value=5)
    assert slider.nudge_step is None


@patch.object(viser._client_autobuild, "ensure_client_is_built", lambda: None)
def test_slider_nudge_step_round_trip() -> None:
    server = viser.ViserServer()
    slider = server.gui.add_slider(
        "S", min=0, max=10, step=1, initial_value=5, nudge_step=2
    )
    assert slider.nudge_step == 2


@patch.object(viser._client_autobuild, "ensure_client_is_built", lambda: None)
def test_add_slider_rejects_non_positive_nudge_step() -> None:
    server = viser.ViserServer()
    with pytest.raises(ValueError, match="nudge_step"):
        server.gui.add_slider("S", min=0, max=10, step=1, initial_value=5, nudge_step=0)
    with pytest.raises(ValueError, match="nudge_step"):
        server.gui.add_slider(
            "S", min=0, max=10, step=1, initial_value=5, nudge_step=-1
        )


@patch.object(viser._client_autobuild, "ensure_client_is_built", lambda: None)
def test_add_slider_rejects_nudge_step_larger_than_range() -> None:
    server = viser.ViserServer()
    with pytest.raises(ValueError, match="nudge_step"):
        server.gui.add_slider(
            "S", min=0, max=10, step=1, initial_value=5, nudge_step=11
        )
    # Exactly the full range is allowed (not larger than).
    slider = server.gui.add_slider(
        "S2", min=0, max=10, step=1, initial_value=5, nudge_step=10
    )
    assert slider.nudge_step == 10


@patch.object(viser._client_autobuild, "ensure_client_is_built", lambda: None)
def test_slider_nudge_step_setter() -> None:
    """`nudge_step` is a plain live prop (like `min`/`max`/`step`): read/write
    via the generic props get/set machinery, no cross-field validation on the
    setter -- exactly like the other live props on this handle."""
    server = viser.ViserServer()
    slider = server.gui.add_slider("S", min=0, max=10, step=1, initial_value=5)
    slider.nudge_step = 2
    assert slider.nudge_step == 2
    slider.nudge_step = None
    assert slider.nudge_step is None


@patch.object(viser._client_autobuild, "ensure_client_is_built", lambda: None)
def test_number_nudge_step_defaults_to_none() -> None:
    """No `nudge_step` given means the client renders the number input
    exactly as before -- no inline -/+ buttons."""
    server = viser.ViserServer()
    number = server.gui.add_number("N", initial_value=5)
    assert number.nudge_step is None


@patch.object(viser._client_autobuild, "ensure_client_is_built", lambda: None)
def test_number_nudge_step_round_trip() -> None:
    server = viser.ViserServer()
    number = server.gui.add_number("N", initial_value=5, min=0, max=10, nudge_step=2)
    assert number.nudge_step == 2


@patch.object(viser._client_autobuild, "ensure_client_is_built", lambda: None)
def test_add_number_rejects_non_positive_nudge_step() -> None:
    server = viser.ViserServer()
    with pytest.raises(ValueError, match="nudge_step"):
        server.gui.add_number("N", initial_value=5, nudge_step=0)
    with pytest.raises(ValueError, match="nudge_step"):
        server.gui.add_number("N", initial_value=5, nudge_step=-1)


@patch.object(viser._client_autobuild, "ensure_client_is_built", lambda: None)
def test_add_number_rejects_nudge_step_larger_than_range() -> None:
    server = viser.ViserServer()
    with pytest.raises(ValueError, match="nudge_step"):
        server.gui.add_number("N", initial_value=5, min=0, max=10, nudge_step=11)
    # Exactly the full range is allowed (not larger than).
    number = server.gui.add_number("N2", initial_value=5, min=0, max=10, nudge_step=10)
    assert number.nudge_step == 10


@patch.object(viser._client_autobuild, "ensure_client_is_built", lambda: None)
def test_add_number_allows_large_nudge_step_when_only_one_bound_given() -> None:
    """The `nudge_step <= max - min` check only applies when both `min` and
    `max` are given -- `add_number`'s bounds are optional, unlike
    `add_slider`'s."""
    server = viser.ViserServer()
    number = server.gui.add_number("N", initial_value=5, min=0, nudge_step=1000)
    assert number.nudge_step == 1000
    number2 = server.gui.add_number("N2", initial_value=5, max=10, nudge_step=1000)
    assert number2.nudge_step == 1000
    number3 = server.gui.add_number("N3", initial_value=5, nudge_step=1000)
    assert number3.nudge_step == 1000


@patch.object(viser._client_autobuild, "ensure_client_is_built", lambda: None)
def test_number_nudge_step_setter() -> None:
    """`nudge_step` is a plain live prop (like `min`/`max`/`step`): read/write
    via the generic props get/set machinery, no cross-field validation on the
    setter -- exactly like the other live props on this handle."""
    server = viser.ViserServer()
    number = server.gui.add_number("N", initial_value=5)
    number.nudge_step = 2
    assert number.nudge_step == 2
    number.nudge_step = None
    assert number.nudge_step is None
