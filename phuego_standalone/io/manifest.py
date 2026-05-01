import json
from pathlib import Path
from datetime import datetime
from typing import Optional
from phuego_standalone.io.fs import iter_visible_dirs


PHUEGO_VERSION = "2.1.0"


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def _safe_count_dirs(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for _ in iter_visible_dirs(path))


def _safe_count_sigma_nodes_edges(sigma_path: Path) -> tuple[int, int]:
    if not sigma_path.exists():
        return 0, 0
    try:
        data = json.loads(sigma_path.read_text())
        return len(data.get("nodes", [])), len(data.get("edges", []))
    except Exception:
        return 0, 0


# ---------------------------------------------------------------------
# Main Manifest Writer
# ---------------------------------------------------------------------

def write_manifest(
    *,
    run_out_folder: Path,
    submission_uuid: str,
    experiment_name: str,
    propagation_value: float,
    kde_dirname: str,
    inc_stats: dict | None = None,
    dec_stats: dict | None = None,
    seed_nodes=None,
    input_parameters=None,
    pvalues_pos=None,
    pvalues_neg=None,
    advanced_stats=None,
):
    """
    Phuego 2.1 Manifest Writer

    Fully deterministic.
    No dependence on runtime stats dict.
    Reads filesystem truth.
    Writes:
      - propagation-level manifest.json
      - experiment-level experiment_manifest.json
    """

    propagation_str = str(propagation_value)
    submission_root = run_out_folder.parents[1]   # results/<uuid>
    experiment_root = run_out_folder.parent       # results/<uuid>/<experiment>

    manifest = {
        "schema_version": "2.1",
        "run_metadata": {
            "uuid": submission_uuid,
            "experiment": experiment_name,
            "propagation": propagation_str,
            "kde": kde_dirname,
            "generated_at": datetime.utcnow().isoformat(),
            "phuego_version": PHUEGO_VERSION,
        },
        "input_parameters": input_parameters or {},
        "network_summary": {},
        "directions": {},
        "cross_experiment": {
            "exists": False,
            "paths": {}
        }
    }

    total_nodes_global = 0
    total_edges_global = 0

    # ---------------------------------------------------------
    # Per direction
    # ---------------------------------------------------------
    for direction in ("increased", "decreased"):

        base = run_out_folder / direction / kde_dirname
        exists = base.exists()

        modules_dir = base / "modules"
        modules_count = _safe_count_dirs(modules_dir)

        sigma_supernodes = base / "networks" / "supernodes_sigma.json"
        node_count, edge_count = _safe_count_sigma_nodes_edges(sigma_supernodes)

        total_nodes_global += node_count
        total_edges_global += edge_count

        direction_block = {
            "exists": bool(exists),
            "modules_count": int(modules_count),
            "node_count": int(node_count),
            "edge_count": int(edge_count),
            "paths": {}
        }



        if exists:
            direction_block["paths"] = {
                "supernodes": {
                    "sigma": f"{direction}/{kde_dirname}/networks/supernodes_sigma.json",
                    "graphml": f"{direction}/{kde_dirname}/networks/supernodes_sigma.graphml",
                    "drugs": f"{direction}/{kde_dirname}/tables/supernodes/drugs.json",
                    "diseases": f"{direction}/{kde_dirname}/tables/supernodes/diseases.json",
                    "gene_druggability": f"{direction}/{kde_dirname}/tables/supernodes/gene_druggability.json",
                    "drugs_txt": f"{direction}/{kde_dirname}/supernodes/drugs.txt",
                    "diseases_txt": f"{direction}/{kde_dirname}/supernodes/diseases.txt",
                    "gene_druggability_txt": f"{direction}/{kde_dirname}/supernodes/gene_druggability.txt",
                },
            
                "module_meta": f"{direction}/{kde_dirname}/networks/module_meta_sigma.json",
            
                "modules": {
                    "sigma_pattern": f"{direction}/{kde_dirname}/networks/modules_sigma/module_{{id}}.json",
                    "graphml_pattern": f"{direction}/{kde_dirname}/networks/modules_sigma/module_{{id}}.graphml",
                    "tables_pattern": f"{direction}/{kde_dirname}/tables/modules/module_{{id}}",
                    "drugs_pattern": f"{direction}/{kde_dirname}/tables/modules/module_{{id}}/drugs.json",
                    "diseases_pattern": f"{direction}/{kde_dirname}/tables/modules/module_{{id}}/diseases.json",
                    "gene_druggability_pattern": f"{direction}/{kde_dirname}/tables/modules/module_{{id}}/gene_druggability.json",
                    "disease_profile_pattern": f"{direction}/{kde_dirname}/tables/modules/module_{{id}}/disease_profile.json",
                    "drugs_txt_pattern": f"{direction}/{kde_dirname}/modules/module_{{id}}/drugs.txt",
                    "diseases_txt_pattern": f"{direction}/{kde_dirname}/modules/module_{{id}}/diseases.txt",
                    "gene_druggability_txt_pattern": f"{direction}/{kde_dirname}/modules/module_{{id}}/gene_druggability.txt",
                },
            
                "summary_stats": f"stats/summary_stats.json",
                "heatmap": f"{direction}/{kde_dirname}/tables/enrichment_heatmap.json",
                "modules_dir": f"{direction}/{kde_dirname}/modules",
                "supernodes_dir": f"{direction}/{kde_dirname}/supernodes",
                "enrichment_supernodes_dir": f"{direction}/{kde_dirname}/supernodes/enrichment",
                "enrichment_json": f"{direction}/{kde_dirname}/tables/enrichment.json",
                "enrichment_gene_term": f"{direction}/{kde_dirname}/tables/enrichment_gene_term.json",
            }
        manifest["directions"][direction] = direction_block

    # ---------------------------------------------------------
    # Global Network Summary
    # ---------------------------------------------------------
    manifest["network_summary"] = {
        "total_nodes": int(total_nodes_global),
        "total_edges": int(total_edges_global),
        "seed_count": len(seed_nodes) if seed_nodes else 0,
    }

    # ---------------------------------------------------------
    # Cross-Experiment Detection
    # results/<uuid>/<prop>/cross_experiment/
    # ---------------------------------------------------------
    cross_dir = submission_root / propagation_str / "cross_experiment"

    if cross_dir.exists():
        manifest["cross_experiment"]["exists"] = True
        manifest["cross_experiment"]["paths"] = {
            "increased": {
                "kde_overlap": f"../{propagation_str}/cross_experiment/increased/kde_overlap_network.json",
                "module_similarity": f"../{propagation_str}/cross_experiment/increased/module_similarity_network.json",
                "module_matrix": f"../{propagation_str}/cross_experiment/increased/module_similarity_matrix.json",
            },
            "decreased": {
                "kde_overlap": f"../{propagation_str}/cross_experiment/decreased/kde_overlap_network.json",
                "module_similarity": f"../{propagation_str}/cross_experiment/decreased/module_similarity_network.json",
                "module_matrix": f"../{propagation_str}/cross_experiment/decreased/module_similarity_matrix.json",
            }
        }

    # ---------------------------------------------------------
    # Write propagation-level manifest
    # ---------------------------------------------------------
    manifest_path = run_out_folder / "manifest.json"
    if advanced_stats is not None:
        manifest["advanced_stats"] = advanced_stats

    manifest_path.write_text(json.dumps(manifest, indent=2))

    # ---------------------------------------------------------
    # Write experiment-level manifest (no scanning needed in web)
    # results/<uuid>/<experiment>/experiment_manifest.json
    # ---------------------------------------------------------
    experiment_manifest_path = experiment_root / "experiment_manifest.json"

    if experiment_manifest_path.exists():
        exp_manifest = json.loads(experiment_manifest_path.read_text())
    else:
        exp_manifest = {
            "schema_version": "2.1",
            "uuid": submission_uuid,
            "experiment": experiment_name,
            "available_propagations": [],
            "default_propagation": propagation_str,
        }

    if propagation_str not in exp_manifest["available_propagations"]:
        exp_manifest["available_propagations"].append(propagation_str)
        exp_manifest["available_propagations"].sort(key=lambda x: float(x))

    exp_manifest["default_propagation"] = propagation_str
    if advanced_stats is not None:
        exp_manifest["advanced_stats"] = advanced_stats
    experiment_manifest_path.write_text(json.dumps(exp_manifest, indent=2))
