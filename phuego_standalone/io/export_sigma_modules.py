import json
import math
import random
from pathlib import Path

import igraph as ig
from phuego_standalone.io.utils_sigma import style_edges
from collections import defaultdict

# -------------------------------------------------------
# Utilities
# -------------------------------------------------------
def build_module_disease_profile(nodes_out, opentargets_lookup):
    disease_scores = defaultdict(float)

    for n in nodes_out:
        pid = n["id"]
        ot = opentargets_lookup.get(pid, {})

        for d in ot.get("target_diseases", []):
            name = d.get("disease")
            score = d.get("score", 0)

            if name:
                disease_scores[name] += score

    # sort
    ranked = sorted(disease_scores.items(), key=lambda x: -x[1])

    return [
        {"disease": d, "score": s}
        for d, s in ranked[:20]
    ]

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
    
def _read_seed_nodes(seed_file: Path):
    if not seed_file.exists():
        return set()
    return {line.strip() for line in seed_file.open() if line.strip()}

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
    out = []
    for d in disease_items or []:
        if isinstance(d, dict):
            name = d.get("disease")
            if name:
                out.append(name)
    return sorted(dict.fromkeys(out))




def build_gene_disease_table(nodes_out, opentargets_lookup, uniprot_to_gene):
    """
    Gene biology only.
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


def build_all_disease_table(nodes_out, opentargets_lookup, uniprot_to_gene):
    """
    Union(target_diseases + drug_diseases).
    """
    table = []

    for n in nodes_out:
        pid = n["id"]
        gene = uniprot_to_gene.get(pid, pid)

        ot = opentargets_lookup.get(pid, {}) if opentargets_lookup else {}
        all_diseases = ot.get("all_diseases", [])

        table.append({
            "gene_id": pid,
            "gene_name": gene,
            "diseases": ", ".join(_extract_sorted_diseases(all_diseases)),
        })

    return table


# -------------------------------------------------------
# Layout
# -------------------------------------------------------

def compute_module_layout(sub: ig.Graph, seeds_set):
    random.seed(42)

    degrees = sub.degree()
    max_deg = max(degrees) if degrees else 1

    seed_nodes = [v["name"] for v in sub.vs if v["name"] in seeds_set]
    n_seeds = max(1, len(seed_nodes))

    seed_index = 0

    seed_radius = 280
    buddy_radius_min = 440
    buddy_radius_max = 840

    initial_layout = []

    for v in sub.vs:
        name = v["name"]
        deg = sub.degree(v.index)
        hub_factor = 1 + math.sqrt(deg / max_deg) if max_deg > 0 else 1

        if name in seeds_set:
            angle = 2 * math.pi * seed_index / n_seeds
            seed_index += 1
            r = seed_radius * hub_factor
        else:
            angle = random.random() * 2 * math.pi
            r = random.uniform(buddy_radius_min, buddy_radius_max) * hub_factor

        x = r * math.cos(angle)
        y = r * math.sin(angle)
        initial_layout.append((x, y))

    layout = sub.layout_fruchterman_reingold(
        niter=350,
        seed=initial_layout,
    )

    return layout


# -------------------------------------------------------
# Main exporter
# -------------------------------------------------------

def export_modules_sigma(
    kde_dir,
    tables_root,
    direction_dir,
    base_network,
    uniprot_to_gene,
    modules_len,
    opentargets_lookup=None,
):
    modules_dir = kde_dir / "modules"
    modules_sigma_dir = kde_dir / "networks" / "modules_sigma"
    modules_tables_root = kde_dir / "tables" / "modules"

    modules_sigma_dir.mkdir(parents=True, exist_ok=True)
    modules_tables_root.mkdir(parents=True, exist_ok=True)

    seed_file = direction_dir / "seed_nodes.txt"
    seeds_set = _read_seed_nodes(seed_file)

    if not modules_dir.exists():
        return

    for module_idx in range(1, modules_len + 1):
        module_dir = modules_dir / f"module_{module_idx}"
        ego_file = module_dir / "module_egos.txt"

        if not ego_file.exists():
            continue

        module_id = f"module_{module_idx}"
        module_tables_dir = modules_tables_root / module_id
        module_tables_dir.mkdir(parents=True, exist_ok=True)

        nodes = set()
        with ego_file.open() as f:
            for line in f:
                nodes.update([x for x in line.strip().split("\t") if x])

        existing = set(base_network.vs["name"])
        nodes = [n for n in nodes if n in existing]

        if len(nodes) < 2:
            continue

        sub = base_network.induced_subgraph(nodes)
        layout = compute_module_layout(sub, seeds_set)

        nodes_out = []

        for idx, v in enumerate(sub.vs):
            name = v["name"]
            x, y = layout[idx]

            is_seed = name in seeds_set
            label = uniprot_to_gene.get(name, name)
            ot = opentargets_lookup.get(name, {}) if opentargets_lookup else {}

            node_data = {
                "id": name,
                "label": label,
                "x": float(x),
                "y": float(y),
                "size": 8 if is_seed else 4,
                "color": "#9970AC" if is_seed else "#5AAE61",
                "is_seed": is_seed,
                "module": module_id,
                "neigh": [sub.vs[n]["name"] for n in sub.neighbors(v.index)],
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
            }

            nodes_out.append(node_data)

        edges_out = []
        raw_weights = []

        for e in sub.es:
            w = float(e["weight"]) if "weight" in e.attributes() else 1.0
            raw_weights.append(w)

        w_min = min(raw_weights) if raw_weights else 0
        w_max = max(raw_weights) if raw_weights else 1

        norm_weights = [
            (w - w_min) / (w_max - w_min) if w_max != w_min else 1.0
            for w in raw_weights
        ]

        for i, e in enumerate(sub.es):
            edges_out.append({
                "id": f"e{i}",
                "source": sub.vs[e.source]["name"],
                "target": sub.vs[e.target]["name"],
                "weight": float(norm_weights[i]),
                "weight_raw": float(raw_weights[i]),
                "type": "similarity",
            })

        edges_out = style_edges(edges_out)

        (modules_sigma_dir / f"{module_id}.json").write_text(
            json.dumps({"nodes": nodes_out, "edges": edges_out}, indent=2)
        )

        sub.write_graphml(str(modules_sigma_dir / f"{module_id}.graphml"))

        drug_table = build_drug_table(nodes_out, opentargets_lookup, uniprot_to_gene)
        gene_table = build_gene_disease_table(nodes_out, opentargets_lookup, uniprot_to_gene)
        gene_druggability = build_gene_metadata_table(nodes_out, opentargets_lookup, uniprot_to_gene)
        disease_profile = build_module_disease_profile(nodes_out, opentargets_lookup)

        (module_tables_dir / "drugs.json").write_text(json.dumps(drug_table, indent=2))
        (module_tables_dir / "diseases.json").write_text(json.dumps(gene_table, indent=2))
        (module_tables_dir / "gene_druggability.json").write_text(json.dumps(gene_druggability, indent=2))
        (module_tables_dir / "disease_profile.json").write_text(json.dumps(disease_profile, indent=2))

        write_tsv(module_dir / "drugs.txt", drug_table)
        write_tsv(module_dir / "diseases.txt", gene_table)
        write_tsv(module_dir / "gene_druggability.txt", gene_druggability)
        print(f"✅ Exported {module_id} ({len(nodes)} nodes, {len(edges_out)} edges)")
