"""Manual proof for hide_nodes-during-capture.

Starts a ViserServer, adds two boxes at the origin (a big RED one, and a
slightly larger GREEN one in front of it -- e.g. a TransformControls gizmo
that occludes what it's attached to), connects a real Playwright chromium
client, and calls client.get_render(hide_nodes=("/green_box",)) to check
that the capture shows only the red box.

Two checks that nothing persists past that one request:
- A second get_render() call right after (no hide_nodes) must go back to
  showing green on top -- the assertable proof.
- A real screenshot of the live canvas is saved to disk for a human to
  eyeball. This is NOT asserted on: the on-screen canvas's framing does not
  track get_render()'s virtual-camera framing pixel-for-pixel (same client
  camera, but the live view is also subject to the browser's own
  auto-fit-on-connect adjustment, which lands the box off-center at a
  screenshot-taking moment that a render request doesn't share), so pinning
  an exact pixel there would be asserting on an unrelated timing detail
  rather than on hide_nodes.

Uses the SAME default-camera framing as tests/e2e/test_get_render_capture.py
and tests/manual_render_layers_proof.py (a box centered at the origin fills
the view from viser's default initial camera pose, for get_render() itself).

Deliberately NOT under tests/ as a collected test (no pytest fixtures, no
assertions wired to CI) -- a one-off manual proof. Run directly:

    cd ~/repos/viser-fork-hidenodes
    source .venv/bin/activate  # or: uv venv .venv && uv pip install -e . playwright
    python -m playwright install chromium
    python tests/manual_hide_nodes_proof.py

Not named test_*.py / *_test.py on purpose, so pytest's default collection
(testpaths=["tests"] in pyproject.toml) never picks it up.
"""

from __future__ import annotations

import time

from playwright.sync_api import sync_playwright

import viser


def main() -> None:
    server = viser.ViserServer(port=8748, verbose=False)

    # RED box: never hidden -- always visible, like every node today.
    server.scene.add_box("/red_box", color=(255, 0, 0), dimensions=(2.0, 2.0, 2.0))
    # GREEN box: same spot, slightly larger so it fully occludes the red box
    # when both are visible. Stands in for a TransformControls gizmo that a
    # capture wants to exclude but that must stay pickable (and thus must
    # stay on the default render layer) for the operator.
    server.scene.add_box("/green_box", color=(0, 255, 0), dimensions=(2.2, 2.2, 2.2))

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 640, "height": 480})
        page.goto(f"http://localhost:{server.get_port()}")

        deadline = time.time() + 20.0
        while time.time() < deadline and len(server.get_clients()) == 0:
            time.sleep(0.2)
        clients = server.get_clients()
        assert len(clients) == 1, f"expected 1 connected client, got {len(clients)}"
        client = list(clients.values())[0]

        # Let the page finish its first paint / asset settle.
        time.sleep(1.0)

        def center_pixel(**kwargs) -> tuple[int, int, int]:
            img = client.get_render(
                height=96,
                width=128,
                transport_format="png",
                timeout=30.0,
                **kwargs,
            )
            cy, cx = img.shape[0] // 2, img.shape[1] // 2
            return tuple(int(v) for v in img[cy, cx, :3])

        # Baseline: both boxes visible, green occludes red.
        baseline = center_pixel()

        # hide_nodes excludes the green box from JUST this capture.
        hidden_capture = center_pixel(hide_nodes=("/green_box",))

        # A name with no live node must be skipped silently, not raise, and
        # must not affect the render -- matches baseline, not hidden_capture.
        harmless_capture = center_pixel(hide_nodes=("/does_not_exist",))

        # No persistence: the very next capture, with no hide_nodes, must be
        # back to baseline (green visible again).
        after_capture = center_pixel()

        # Qualitative-only: save what the operator's own canvas looks like
        # right now, for a human to eyeball (see module docstring for why
        # this isn't pixel-asserted).
        page.screenshot(path="/tmp/hide_nodes_proof_operator_view.png")

        browser.close()

    server.stop()

    print(f"baseline (both visible, green occludes red): RGB = {baseline}")
    print(f"hide_nodes=('/green_box',): RGB = {hidden_capture}")
    print(f"hide_nodes=('/does_not_exist',) (must not raise): RGB = {harmless_capture}")
    print(f"after_capture (no hide_nodes, right after): RGB = {after_capture}")
    print("Operator-view screenshot: /tmp/hide_nodes_proof_operator_view.png")

    ok = True
    if not (baseline[1] > baseline[0] and baseline[1] > 150):
        print("FAIL: baseline center pixel is not green-dominant:", baseline)
        ok = False
    if not (hidden_capture[0] > hidden_capture[1] and hidden_capture[0] > 150):
        print(
            "FAIL: hide_nodes capture center pixel is not red-dominant "
            "(green wasn't excluded):",
            hidden_capture,
        )
        ok = False
    if harmless_capture != baseline:
        print(
            "FAIL: hiding a nonexistent node changed the render (should "
            "match baseline, nothing was hidden):",
            harmless_capture,
            "vs baseline",
            baseline,
        )
        ok = False
    if after_capture != baseline:
        print(
            "FAIL: the capture right after a hide_nodes request is not back "
            "to baseline -- hide_nodes leaked past its one request:",
            after_capture,
            "vs baseline",
            baseline,
        )
        ok = False
    print("PROOF PASSED" if ok else "PROOF FAILED")


if __name__ == "__main__":
    main()
