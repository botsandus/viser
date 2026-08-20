> **Dexory fork.** This is [botsandus](https://github.com/botsandus)'s fork of
> upstream [viser-project/viser](https://github.com/viser-project/viser),
> branched from the `v1.1.0` tag. The `amri-tree-widget` branch adds two new
> GUI components, both built with no application-specific concepts baked in
> so they can be proposed upstream as PRs rather than living as permanent
> fork drift: a generic, server-driven tree widget (`gui.add_tree(...)`, see
> `examples/02_gui/12_tree_widget.py`) and a generic inline number row --
> N labelled number inputs sharing a single row (`gui.add_number_row(...)`,
> see `examples/02_gui/13_number_row.py`). Everything else tracks upstream
> unmodified.

<h1 align="left">
    <img alt="viser logo" src="https://viser.studio/main/_static/logo.svg" width="30" height="auto" />
    Viser
    <img alt="viser logo" src="https://viser.studio/main/_static/logo.svg" width="30" height="auto" />
</h1>

<p align="left">
    <img alt="pyright" src="https://github.com/viser-project/viser/actions/workflows/pyright.yml/badge.svg" />
    <img alt="typescript-compile" src="https://github.com/viser-project/viser/actions/workflows/typescript-compile.yml/badge.svg" />
    <a href="https://pypi.org/project/viser/">
        <img alt="codecov" src="https://img.shields.io/pypi/pyversions/viser" />
    </a>
    <a href="https://discord.gg/pnNTkHNUwP">
        <img alt="Viser Discord"  src="https://img.shields.io/discord/1423204924518432809?logo=discord&label=discord" />
    </a>
</p>

Viser is a 3D visualization library for computer vision and robotics in Python.

Features include:

- API for visualizing 3D primitives.
- GUI building blocks: buttons, checkboxes, text inputs, sliders, etc.
- Scene interaction tools (clicks, selection, transform gizmos).
- Programmatic camera control and rendering.
- An entirely web-based client, for easy use over SSH!

The goal is to provide primitives that are (1) easy for simple visualization tasks, but (2) can be composed into more elaborate interfaces. For more about design goals, see the [technical report](https://arxiv.org/abs/2507.22885).

Examples and documentation: https://viser.studio

## Installation

You can install `viser` with `pip`:

```bash
pip install viser            # Core dependencies only.
pip install viser[examples]  # To include example dependencies.
```

That's it! To learn more, we recommend looking at the examples in the [documentation](https://viser.studio/).

## Citation

To cite Viser in your work, you can use the BibTeX for our [technical report](https://arxiv.org/abs/2507.22885):

```
@article{yi2025viser,
  title={Viser: Imperative, web-based 3d visualization in python},
  author={Yi, Brent and Kim, Chung Min and Kerr, Justin and Wu, Gina and Feng, Rebecca and Zhang, Anthony and Kulhanek, Jonas and Choi, Hongsuk and Ma, Yi and Tancik, Matthew and Kanazawa, Angjoo},
  journal={arXiv preprint arXiv:2507.22885},
  year={2025}
}
```

## Acknowledgements

`viser` is heavily inspired by packages like
[Pangolin](https://github.com/stevenlovegrove/Pangolin),
[Dear ImGui](https://github.com/ocornut/imgui),
[rviz](https://wiki.ros.org/rviz/),
[meshcat](https://github.com/rdeits/meshcat), and
[Gradio](https://github.com/gradio-app/gradio).

The web client is implemented using [React](https://react.dev/), with:

- [Vite](https://vitejs.dev/) / [Rollup](https://rollupjs.org/) for bundling
- [three.js](https://threejs.org/) via [react-three-fiber](https://github.com/pmndrs/react-three-fiber) and [drei](https://github.com/pmndrs/drei)
- [Mantine](https://mantine.dev/) for UI components
- [zustand](https://github.com/pmndrs/zustand) for state management
- [vanilla-extract](https://vanilla-extract.style/) for stylesheets

Thanks to the authors of these projects for open-sourcing their work!
