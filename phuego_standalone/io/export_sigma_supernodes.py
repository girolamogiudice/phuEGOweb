import json
import math
from pathlib import Path
from phuego_standalone.io.fs import iter_visible_dirs
from phuego_standalone.io.utils_sigma import style_edges


# -------------------------------------------------------
# Utilities
# -------------------------------------------------------
def _extract_sorted_diseases(disease_items):
    return [
        d["disease"]
        for d in sorted(
            disease_items or [],
            key=lambda x: -x.get("score", 0)
        )
        if isinstance(d, dict) and d.get("disease")
    ]
    
def write_tsv(path, table):
    if not table:
        return

    with open(path, "w") as f:
        header = list(table[0].keys())
        f.write("\t".join(header) + "\n")

        for row in table:
            values = []
            for h in header:
                v = row.get(h, "")
                if isinstance(v, list):
                    v = ", ".join(str(x) for x in v)
                values.append(str(v))
            f.write("\t".join(values) + "\n")


def _extract_disease_names(disease_items):
    """
    disease_items can be:
      [
        {"disease_id": "...", "disease": "..."},
        ...
      ]
    or
      [
        {"disease_id": "...", "disease": "...", "score": ...},
        ...
      ]
    """
    out = []
    for d in disease_items or []:
        if isinstance(d, dict):
            name = d.get("disease")
            if name:
                out.append(name)
    return sorted(dict.fromkeys(out))


def build_drug_table(nodes_out, opentargets_lookup, uniprot_to_gene):
    table = []

    for n in nodes_out:
        pid = n["id"]
        gene = uniprot_to_gene.get(pid, pid)

        ot = opentargets_lookup.get(pid, {}) if opentargets_lookup else {}
        drugs = ot.get("drugs", [])
        seen = set()

        for d in drugs:
            key = (pid, d.get("chembl_id"))

            if key in seen:
                continue
            seen.add(key)

            table.append({
                "gene_id": pid,
                "gene_name": gene,
                "chembl_id": d.get("chembl_id", ""),
                "drug_name": d.get("name", ""),
                "phase": d.get("phase", ""),
                "drug_diseases": ", ".join(d.get("diseases", []))
            })

    return table

def build_gene_disease_table(nodes_out, opentargets_lookup, uniprot_to_gene):
    """
    This table is the gene biology table:
      one row per gene
      diseases = target_diseases only
    """
    table = []

    for n in nodes_out:
        pid = n["id"]
        gene = uniprot_to_gene.get(pid, pid)

        ot = opentargets_lookup.get(pid, {}) if opentargets_lookup else {}
        target_diseases = ot.get("target_diseases", [])

        table.append({
            "gene_id": pid,
            "gene_name": gene,
            "diseases": _extract_sorted_diseases(target_diseases),
            "scores": [round(d.get("score", 0), 3) for d in target_diseases],
        })

    return table

def build_gene_metadata_table(nodes_out, opentargets_lookup, uniprot_to_gene):
    table = []

    for n in nodes_out:
        pid = n["id"]
        gene = uniprot_to_gene.get(pid, pid)

        ot = opentargets_lookup.get(pid, {}) if opentargets_lookup else {}
        druggability = ot.get("druggability", {})

        table.append({
            "gene_id": pid,
            "gene_name": gene,
            "druggability_score": druggability.get("druggability_score", 0),
            "modalities": ", ".join(druggability.get("modalities", [])),
            "max_phase": ot.get("max_phase", 0)
        })

    return table
    

def read_seed_nodes(seed_file: Path):
    if not seed_file.exists():
        return set()
    return {line.strip() for line in seed_file.open() if line.strip()}


def read_kde_egos(egos_file: Path):
    neighbors = {}
    all_nodes = set()

    if not egos_file.exists():
        return neighbors, all_nodes

    with egos_file.open() as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) <= 2:
                continue
            seed = parts[0]
            buddies = list(dict.fromkeys(parts[1:]))
            neighbors[seed] = buddies
            all_nodes.update(buddies)
            all_nodes.add(seed)

    return neighbors, all_nodes


def read_module_membership(modules_dir: Path):
    membership = {}

    if not modules_dir.exists():
        return membership

    for mod_dir in iter_visible_dirs(modules_dir):
        if not mod_dir.name.startswith("module_"):
            continue

        label = mod_dir.name.replace("module_", "Module ")
        egos_file = mod_dir / "module_egos.txt"

        if not egos_file.exists():
            continue

        with egos_file.open() as f:
            for line in f:
                parts = line.strip().split("\t")
                for p in parts:
                    if p:
                        membership.setdefault(p, []).append(label)

    return membership


# -------------------------------------------------------
# Layout
# -------------------------------------------------------

def compute_supernode_layout(g, module_membership, seeds_set, neighbors):
    import random

    random.seed(42)

    modules = {}
    for protein, mods in module_membership.items():
        for m in mods:
            modules.setdefault(m, []).append(protein)

    module_names = sorted(modules.keys())

    module_radius = 9000
    seed_base_radius = 700
    seed_spacing = 280
    neighbor_radius = 1400

    centroids = {}
    n = len(module_names)

    for i, m in enumerate(module_names):
        angle = 2 * math.pi * i / max(n, 1)
        centroids[m] = (
            module_radius * math.cos(angle),
            module_radius * math.sin(angle),
        )

    seed_positions = {}

    for m, nodes in modules.items():
        cx, cy = centroids[m]
        seeds = [x for x in nodes if x in seeds_set]

        n_seeds = max(len(seeds), 1)
        r = seed_base_radius + seed_spacing * n_seeds

        for i, seed in enumerate(seeds):
            angle = 2 * math.pi * i / n_seeds
            seed_positions[seed] = (
                cx + r * math.cos(angle),
                cy + r * math.sin(angle),
            )

    layout = []

    for v in g.vs:
        name = v["name"]

        if name in seed_positions:
            layout.append(seed_positions[name])
            continue

        placed = False
        for seed, buds in neighbors.items():
            if name in buds and seed in seed_positions:
                sx, sy = seed_positions[seed]
                r = neighbor_radius + 20 * len(buds)

                angle = random.random() * 2 * math.pi
                layout.append((sx + r * math.cos(angle), sy + r * math.sin(angle)))
                placed = True
                break

        if placed:
            continue

        layout.append((0.0, 0.0))

    return layout


# -------------------------------------------------------
# Main exporter
# -------------------------------------------------------
def export_supernodes_sigma(
    kde_dir,
    tables_root,
    direction_dir,
    base_network,
    uniprot_to_gene,
    opentargets_lookup=None,
):
    networks_dir = kde_dir / "networks"
    supernodes_dir = kde_dir / "supernodes"
    tables_supernodes_dir = tables_root / "supernodes"

    networks_dir.mkdir(parents=True, exist_ok=True)
    supernodes_dir.mkdir(parents=True, exist_ok=True)
    tables_supernodes_dir.mkdir(parents=True, exist_ok=True)

    seed_file = direction_dir / "seed_nodes.txt"
    egos_path = kde_dir / "supernodes" / "KDE_supernodes_egos.txt"
    modules_dir = kde_dir / "modules"

    seeds_set = read_seed_nodes(seed_file)
    neighbors, all_nodes = read_kde_egos(egos_path)
    module_membership = read_module_membership(modules_dir)

    base_names = set(base_network.vs["name"])
    selected_nodes = list(all_nodes & base_names)

    if not selected_nodes:
        print("⚠ No nodes selected for supernodes export")
        return

    g = base_network.induced_subgraph(selected_nodes)

    layout = compute_supernode_layout(
        g,
        module_membership,
        seeds_set,
        neighbors,
    )

    for i, v in enumerate(g.vs):
        v["x"] = float(layout[i][0])
        v["y"] = float(layout[i][1])

    degrees = g.degree()
    max_deg = max(degrees) if degrees else 1

    nodes = []

    for v in g.vs:
        pid = v["name"]
        deg = g.degree(v.index)
        is_seed = pid in seeds_set

        if is_seed:
            size = 10 + 4 * math.sqrt(deg / max_deg) if max_deg > 0 else 10
        else:
            size = 6 + 3 * math.sqrt(deg / max_deg) if max_deg > 0 else 6

        label = str(uniprot_to_gene.get(pid, pid))
        ot = opentargets_lookup.get(pid, {}) if opentargets_lookup else {}

        nodes.append({
            "id": pid,
            "label": label,
            "color": "purple" if is_seed else "green",
            "size": float(size),
            "is_seed": is_seed,
            "superList": sorted(list(set(module_membership.get(pid, [])))),
            "neigh": neighbors.get(pid, []),
            "x": float(v["x"]),
            "y": float(v["y"]),
            "ot": {
                "max_phase": ot.get("max_phase", 0),
                "druggability_score": ot.get("druggability", {}).get("druggability_score", 0),
                "modalities": ot.get("druggability", {}).get("modalities", []),
                "drugs": [
                    {
                        "name": d.get("name", ""),
                        "chembl_id": d.get("chembl_id", ""),
                        "phase": d.get("phase", 0),
                        "diseases": d.get("diseases", []),
                    }
                    for d in ot.get("drugs", [])[:10]
                ],
                "top_diseases": [
                    {
                        "disease": d.get("disease", ""),
                        "score": d.get("score", 0),
                    }
                    for d in ot.get("target_diseases", [])[:10]
                    if isinstance(d, dict) and d.get("disease")
                ],
            }
        })

    edges = []
    raw_weights = []

    for e in g.es:
        w = float(e["weight"]) if "weight" in e.attributes() else 1.0
        raw_weights.append(w)

    w_min = min(raw_weights) if raw_weights else 0
    w_max = max(raw_weights) if raw_weights else 1

    norm_weights = [
        (w - w_min) / (w_max - w_min) if w_max != w_min else 1.0
        for w in raw_weights
    ]

    for i, e in enumerate(g.es):
        edges.append({
            "id": f"e{i}",
            "source": g.vs[e.source]["name"],
            "target": g.vs[e.target]["name"],
            "weight": float(norm_weights[i]),
            "weight_raw": float(raw_weights[i]),
            "type": "similarity",
        })

    edges = style_edges(edges)

    (networks_dir / "supernodes_sigma.json").write_text(
        json.dumps({"nodes": nodes, "edges": edges}, indent=2)
    )

    g.write_graphml(str(networks_dir / "supernodes_sigma.graphml"))

    drug_table = build_drug_table(nodes, opentargets_lookup, uniprot_to_gene)
    gene_table = build_gene_disease_table(nodes, opentargets_lookup, uniprot_to_gene)
    gene_druggability = build_gene_metadata_table(nodes, opentargets_lookup, uniprot_to_gene)

    (tables_supernodes_dir / "drugs.json").write_text(json.dumps(drug_table, indent=2))
    (tables_supernodes_dir / "diseases.json").write_text(json.dumps(gene_table, indent=2))
    (tables_supernodes_dir / "gene_druggability.json").write_text(json.dumps(gene_druggability, indent=2))

    write_tsv(supernodes_dir / "drugs.txt", drug_table)
    write_tsv(supernodes_dir / "diseases.txt", gene_table)
    write_tsv(supernodes_dir / "gene_druggability.txt", gene_druggability)

    print(f"✅ Exported supernodes ({len(nodes)} nodes, {len(edges)} edges)")
