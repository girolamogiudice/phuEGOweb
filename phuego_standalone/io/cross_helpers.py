# phuego/io/cross_helpers.py

import json
import random
from pathlib import Path
from itertools import combinations
import igraph as ig

from phuego_standalone.io.fs import iter_visible_dirs
from phuego_standalone.io.utils_sigma import style_edges


# -------------------------------------------------------
# Constants
# -------------------------------------------------------

TAB20 = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728",
    "#9467bd", "#8c564b", "#e377c2", "#7f7f7f",
    "#bcbd22", "#17becf",
    "#aec7e8", "#ffbb78", "#98df8a", "#ff9896",
    "#c5b0d5", "#c49c94", "#f7b6d2", "#c7c7c7",
    "#dbdb8d", "#9edae5"
]

SHAPES = [
    "circle", "square", "triangle", "diamond",
    "cross", "star", "hexagon"
]


# -------------------------------------------------------
# Utilities
# -------------------------------------------------------

def overlap_coeff(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / float(min(len(a), len(b)))


# -------------------------------------------------------
# Layout + styling
# -------------------------------------------------------

def apply_layout_and_style_igraph(nodes, edges, weight_key="weight"):
    """
    Deterministic layout + node size scaling + edge styling.
    Returns Sigma-ready graph.
    """

    if not nodes:
        return {"nodes": [], "edges": []}

    node_ids = [n["id"] for n in nodes]
    id_index = {nid: i for i, nid in enumerate(node_ids)}

    # -------------------------
    # Build igraph
    # -------------------------
    g = ig.Graph()
    g.add_vertices(node_ids)

    edge_tuples = []
    weights = []

    for e in edges:
        if e["source"] in id_index and e["target"] in id_index:
            edge_tuples.append((e["source"], e["target"]))
            weights.append(e.get(weight_key, 1.0))

    if edge_tuples:
        g.add_edges(edge_tuples)
        g.es["weight"] = weights

    # -------------------------
    # Layout (deterministic)
    # -------------------------
    random.seed(42)

    layout = g.layout_fruchterman_reingold(
        weights=g.es["weight"] if g.ecount() else None,
        niter=500
    )

    coords = layout.coords

    # Normalize coordinates 0–1
    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    def norm(v, vmin, vmax):
        if vmax - vmin == 0:
            return 0.5
        return (v - vmin) / (vmax - vmin)

    # -------------------------
    # Node size scaling
    # -------------------------
    degrees = g.degree()
    max_degree = max(degrees) if degrees else 1
    max_degree = max(max_degree, 1)

    styled_nodes = []
    for i, n in enumerate(nodes):
        x, y = coords[i]
        deg = degrees[i]

        styled_nodes.append({
            **n,
            "x": norm(x, min_x, max_x),
            "y": norm(y, min_y, max_y),
            "size": 5 + 10 * (deg / max_degree)
        })

    # -------------------------
    # Edge styling
    # -------------------------
    raw_edges = []

    for i, e in enumerate(edges):
        raw_edges.append({
            "id": f"e{i}",
            "source": e["source"],
            "target": e["target"],
            "weight": e.get(weight_key, 1.0),
            "type": "similarity"
        })

    styled_edges = style_edges(raw_edges)

    return {"nodes": styled_nodes, "edges": styled_edges}


# -------------------------------------------------------
# KDE LEVEL EXPERIMENT OVERLAP
# -------------------------------------------------------

def build_kde_overlap(submission_dir: Path, propagation: str, direction: str, kde_dirname: str):

    exp_seed_sets = {}

    for exp_dir in iter_visible_dirs(submission_dir):

        # skip numeric folders (UUID-only dirs)
        if exp_dir.name.replace(".", "", 1).isdigit():
            continue

        kde_path = (
            exp_dir
            / propagation
            / direction
            / kde_dirname
            / "supernodes"
            / "KDE_supernodes_egos.txt"
        )

        if not kde_path.exists():
            continue

        seeds = set()

        with kde_path.open() as f:
            for line in f:
                parts = line.strip().split("\t")
                if len(parts) < 2:
                    continue
                if parts[0] == parts[1]:
                    continue
                seeds.add(parts[0])

        if seeds:
            exp_seed_sets[exp_dir.name] = seeds

    if len(exp_seed_sets) < 2:
        return {"nodes": [], "edges": []}

    experiments = sorted(exp_seed_sets.keys())

    # Assign colors + shapes
    color_map = {exp: TAB20[i % 20] for i, exp in enumerate(experiments)}
    shape_map = {exp: SHAPES[i % len(SHAPES)] for i, exp in enumerate(experiments)}

    nodes = [
        {
            "id": exp,
            "color": color_map[exp],
            "shape": shape_map[exp]
        }
        for exp in experiments
    ]

    edges = []

    for i in range(len(experiments)):
        for j in range(i + 1, len(experiments)):
            a = exp_seed_sets[experiments[i]]
            b = exp_seed_sets[experiments[j]]

            w = overlap_coeff(a, b)
            if w > 0:
                edges.append({
                    "source": experiments[i],
                    "target": experiments[j],
                    "weight": w
                })

    return apply_layout_and_style_igraph(nodes, edges)


# -------------------------------------------------------
# MODULE SIMILARITY (cross-experiment)
# -------------------------------------------------------

def build_module_similarity(submission_dir: Path, propagation: str, direction: str, kde_dirname: str):

    modules = {}

    for exp_dir in iter_visible_dirs(submission_dir):

        modules_dir = (
            exp_dir
            / propagation
            / direction
            / kde_dirname
            / "modules"
        )

        if not modules_dir.exists():
            continue

        for mod_dir in iter_visible_dirs(modules_dir):
            if not mod_dir.name.startswith("module_"):
                continue

            mod_id = mod_dir.name.replace("module_", "Module ")
            full_id = f"{exp_dir.name}_{mod_id}"

            ego_file = mod_dir / "module_egos.txt"
            if not ego_file.exists():
                continue

            proteins = set()

            with ego_file.open() as f:
                for line in f:
                    parts = line.strip().split("\t")
                    proteins.update(parts)

            if proteins:
                modules[full_id] = {
                    "proteins": proteins,
                    "experiment": exp_dir.name,
                    "module_id": mod_id
                }

    if len(modules) < 2:
        return None, None

    experiments = sorted({v["experiment"] for v in modules.values()})

    color_map = {exp: TAB20[i % 20] for i, exp in enumerate(experiments)}
    shape_map = {exp: SHAPES[i % len(SHAPES)] for i, exp in enumerate(experiments)}

    labels = sorted(modules.keys())

    matrix = []
    edges = []

    for i, a in enumerate(labels):
        row = []
        for j, b in enumerate(labels):

            if i == j:
                val = 1.0
            else:
                val = overlap_coeff(
                    modules[a]["proteins"],
                    modules[b]["proteins"]
                )

            row.append(val)

            if i < j and val > 0:
                edges.append({
                    "source": a,
                    "target": b,
                    "weight": val
                })

        matrix.append(row)

    nodes = [
        {
            "id": m,
            "experiment": modules[m]["experiment"],
            "module_id": modules[m]["module_id"],
            "color": color_map[modules[m]["experiment"]],
            "shape": shape_map[modules[m]["experiment"]],
        }
        for m in labels
    ]

    network = apply_layout_and_style_igraph(nodes, edges)
    matrix_obj = {"labels": labels, "matrix": matrix}

    return network, matrix_obj
