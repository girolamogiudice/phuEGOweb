# phuego/io/export_sigma_module_meta.py

import json
from pathlib import Path
from itertools import combinations
import igraph as ig
from phuego_standalone.io.fs import iter_visible_dirs
from phuego_standalone.io.utils_sigma import style_edges


# -------------------------------------------------------
# Utilities
# -------------------------------------------------------

def overlap_coeff(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / float(min(len(a), len(b)))


# -------------------------------------------------------
# Main exporter
# -------------------------------------------------------

def export_module_meta_sigma(kde_dir: Path) -> None:

    networks_dir = kde_dir / "networks"
    modules_dir = kde_dir / "modules"

    if not modules_dir.exists():
        return

    module_nodes = {}

    # -------------------------
    # Read modules
    # -------------------------
    for module_path in iter_visible_dirs(modules_dir):
        if not module_path.name.startswith("module_"):
            continue

        module_id = module_path.name.replace("module_", "Module ")

        ego_file = module_path / "module_egos.txt"
        if not ego_file.exists():
            continue

        proteins = set()
        with ego_file.open() as f:
            for line in f:
                parts = line.strip().split("\t")
                proteins.update(parts)

        if proteins:
            module_nodes[module_id] = proteins

    if not module_nodes:
        return

    # -------------------------
    # Build graph
    # -------------------------
    g = ig.Graph()
    module_ids = sorted(module_nodes.keys())

    g.add_vertices(module_ids)
    g.vs["name"] = module_ids

    for (m1, p1), (m2, p2) in combinations(module_nodes.items(), 2):
        score = overlap_coeff(p1, p2)
        if score > 0:
            g.add_edge(m1, m2, weight=score)

    if g.ecount() == 0:
        return

    # -------------------------
    # Layout
    # -------------------------
    layout = g.layout_fruchterman_reingold(
        weights=g.es["weight"],
        niter=500
    )

    for i, v in enumerate(g.vs):
        v["x"] = float(layout[i][0])
        v["y"] = float(layout[i][1])

    # -------------------------
    # Nodes
    # -------------------------
    max_module_size = max(len(p) for p in module_nodes.values())

    nodes = []
    for v in g.vs:
        module_id = v["name"]
        size_scale = len(module_nodes[module_id]) / max_module_size

        nodes.append({
            "id": module_id,
            "label": module_id,
            "size": 8 + 10 * size_scale,
            "color": "#999999",
            "x": v["x"],
            "y": v["y"],
        })

    # -------------------------
    # Edges (FIXED)
    # -------------------------
    raw_edges = []

    for eid, e in enumerate(g.es):
        raw_edges.append({
            "id": f"e{eid}",
            "source": g.vs[e.source]["name"],
            "target": g.vs[e.target]["name"],
            "weight": float(e["weight"]),
            "type": "similarity"   # ✅ REQUIRED FIX
        })

    edges = style_edges(raw_edges)

    # -------------------------
    # Save
    # -------------------------
    networks_dir.mkdir(exist_ok=True)
    out_path = networks_dir / "module_meta_sigma.json"

    out_path.write_text(
        json.dumps({"nodes": nodes, "edges": edges}, indent=2)
    )

    print(f"✅ Exported module_meta_sigma.json ({len(nodes)} nodes, {len(edges)} edges)")
