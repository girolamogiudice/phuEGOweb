"""Annotate-stage graph utilities.

The annotate stage adds node/edge attributes without changing graph topology.
All functions mutate the graph in-place.
"""

from __future__ import annotations

from typing import Dict, Mapping, Sequence, Set, Tuple
import colorsys

import igraph as ig
import numpy as np


def annotate_gene_names(graph: ig.Graph, uniprot_to_gene: Mapping[str, str]) -> None:
    """Set the `Gene_name` vertex attribute using a UniProt→gene mapping."""
    graph.vs["Gene_name"] = [uniprot_to_gene.get(u, u) for u in graph.vs["name"]]


def annotate_is_seed(graph: ig.Graph, seeds: Sequence[str], attr: str = "Is_seed") -> None:
    """Annotate a boolean seed flag for each node."""
    seed_set = set(seeds)
    graph.vs[attr] = [name in seed_set for name in graph.vs["name"]]


def annotate_module_membership(
    graph: ig.Graph,
    nodes_by_module: Dict[str, Set[str]],
    prefix: str = "",
) -> None:
    """Annotate per-module membership flags on nodes."""
    if graph.vcount() == 0:
        return

    names = np.array(graph.vs["name"], dtype=object)
    for module_name, nodes in sorted(nodes_by_module.items()):
        attr = f"{prefix}{module_name}" if prefix else module_name
        graph.vs[attr] = np.isin(names, list(nodes))


def _tab10_palette() -> Tuple[Tuple[int, int, int], ...]:
    return (
        (31, 119, 180),
        (255, 127, 14),
        (44, 160, 44),
        (214, 39, 40),
        (148, 103, 189),
        (140, 86, 75),
        (227, 119, 194),
        (127, 127, 127),
        (188, 189, 34),
        (23, 190, 207),
    )


def _tab20_palette() -> Tuple[Tuple[int, int, int], ...]:
    return (
        (31, 119, 180), (174, 199, 232),
        (255, 127, 14), (255, 187, 120),
        (44, 160, 44), (152, 223, 138),
        (214, 39, 40), (255, 152, 150),
        (148, 103, 189), (197, 176, 213),
        (140, 86, 75), (196, 156, 148),
        (227, 119, 194), (247, 182, 210),
        (127, 127, 127), (199, 199, 199),
        (188, 189, 34), (219, 219, 141),
        (23, 190, 207), (158, 218, 229),
    )


def _rainbow_palette(n: int) -> Tuple[Tuple[int, int, int], ...]:
    colors = []
    for i in range(n):
        h = i / n
        r, g, b = colorsys.hsv_to_rgb(h, 0.65, 0.9)
        colors.append((int(r * 255), int(g * 255), int(b * 255)))
    return tuple(colors)


def _select_palette(n_modules: int) -> Tuple[Tuple[int, int, int], ...]:
    if n_modules <= 10:
        return _tab10_palette()
    elif n_modules <= 20:
        return _tab20_palette()
    else:
        return _rainbow_palette(n_modules)


def annotate_module_labels_and_colors(
    graph: ig.Graph,
    modules: Sequence[str],
    label_attr: str = "ModuleLabel",
    color_attr: str = "ModuleColor",
) -> None:
    """Create composite module label and Cytoscape-friendly RGB color strings."""

    palette = _select_palette(len(modules))

    module_colors = {
        m: palette[i] for i, m in enumerate(modules)
    }

    for idx, v in enumerate(graph.vs):
        module_identity = [m for m in modules if v[m] == 1.0]

        graph.vs[idx][label_attr] = "_".join(module_identity)

        if len(module_identity) == 1:
            r, g, b = module_colors[module_identity[0]]
            graph.vs[idx][color_attr] = f"rgb({r},{g},{b})"
        else:
            graph.vs[idx][color_attr] = "rgb(255, 255, 255)"
