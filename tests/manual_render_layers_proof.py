"""Manual proof for MVP-30 wave 2 render layers.

Starts a ViserServer, adds two boxes at the origin (a big RED one on the
default layers=1, and a slightly smaller GREEN one in front of it on
layers=2 -- e.g. a "human-only helper" that a simulated camera should be
able to exclude), connects a real Playwright chromium client, and calls
client.get_render(..., layers=1) and get_render(..., layers=2) to check
which box the center pixel shows under each mask.

Uses the SAME default-camera framing as the fork's own
tests/e2e/test_get_render_capture.py (a box centered at the origin fills
the view from viser's default initial camera pose) rather than a
hand-rolled camera pose, to avoid an unrelated camera-math bug swamping the
actual thing under test.

This is deliberately NOT under tests/ as a collected test (no pytest
fixtures, no assertions wired to CI) -- it is the one-off manual proof the
wave-2 brief asked for. Run directly:

    cd /home/greg-baker/repos/viser-fork-layers
    uv venv .venv-layers && source .venv-layers/bin/activate
    uv pip install -e . playwright
    python -m playwright install chromium
    python tests/manual_render_layers_proof.py

Not named test_*.py / *_test.py on purpose, so pytest's default collection
(testpaths=["tests"] in pyproject.toml) never picks it up.
"""

from __future__ import annotations

import time

from playwright.sync_api import sync_playwright

import viser


def main() -> None:
    server = viser.ViserServer(port=8747, verbose=False)

    # RED box: default layers (1) -- always visible, like every node today.
    red = server.scene.add_box(
        "/red_box", color=(255, 0, 0), dimensions=(2.0, 2.0, 2.0)
    )
    # GREEN box: same spot, slightly larger so it fully occludes the red box
    # when rendered. layers=2 -- a "human-only helper" a simulated camera
    # should be able to exclude while the operator keeps seeing it.
    green = server.scene.add_box(
        "/green_box", color=(0, 255, 0), dimensions=(2.2, 2.2, 2.2)
    )
    green.layers = 2
    assert red.layers == 1  # Default, untouched -- additive-only check.

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

        def center_pixel(layers: int) -> tuple[int, int, int]:
            img = client.get_render(
                height=96,
                width=128,
                transport_format="png",
                layers=layers,
                timeout=30.0,
            )
            cy, cx = img.shape[0] // 2, img.shape[1] // 2
            return tuple(int(v) for v in img[cy, cx, :3])

        results = {
            "layers=1 (default mask, bit 0 only -- green excluded)": center_pixel(1),
            "layers=2 (bit 1 only -- red excluded)": center_pixel(2),
            "layers=3 (bits 0+1 -- green occludes red)": center_pixel(3),
        }
        for label, rgb in results.items():
            print(f"{label}: center pixel RGB = {rgb}")

        browser.close()

    server.stop()

    # Sanity assertions, printed either way so a human can also eyeball them.
    r1 = results["layers=1 (default mask, bit 0 only -- green excluded)"]
    r2 = results["layers=2 (bit 1 only -- red excluded)"]
    r3 = results["layers=3 (bits 0+1 -- green occludes red)"]
    ok = True
    if not (r1[0] > r1[1] and r1[0] > 150):
        print("FAIL: layers=1 center pixel is not red-dominant:", r1)
        ok = False
    if not (r2[1] > r2[0] and r2[1] > 150):
        print("FAIL: layers=2 center pixel is not green-dominant:", r2)
        ok = False
    if not (r3[1] > r3[0] and r3[1] > 150):
        print(
            "FAIL: layers=3 center pixel is not green-dominant (green occludes red):",
            r3,
        )
        ok = False
    print("PROOF PASSED" if ok else "PROOF FAILED")


if __name__ == "__main__":
    main()
