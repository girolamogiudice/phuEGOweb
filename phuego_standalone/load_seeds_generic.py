from dataclasses import dataclass
from collections import defaultdict
from typing import Dict, List, Tuple
from pathlib import Path
import pandas as pd

from .domain import SeedData, SeedLayout
from .utils import load_zscores, load_semantic_similarity

MAX_LAYERS = 3


# ---------------------------------------------------------------------
# Internal dataclasses
# ---------------------------------------------------------------------

@dataclass
class SeedDataset:
    seeds_pos: Dict[str, float]
    seeds_neg: Dict[str, float]
    rows: List[Tuple[str, float, int]]


@dataclass
class SeedParseResult:
    datasets: Dict[str, SeedDataset]


# ---------------------------------------------------------------------
# Parse seed file
# ---------------------------------------------------------------------


def filter_dataset_to_graph(dataset, graph_nodes):
    graph_nodes = set(graph_nodes)

    filtered_rows = []
    filtered_pos = {}
    filtered_neg = {}

    excluded_pos = []
    excluded_neg = []

    for protein, lfc, layer in dataset.rows:
        if protein in graph_nodes:
            filtered_rows.append((protein, lfc, layer))
            if lfc > 0:
                filtered_pos[protein] = lfc
            elif lfc < 0:
                filtered_neg[protein] = abs(lfc)
        else:
            if lfc > 0:
                excluded_pos.append(protein)
            elif lfc < 0:
                excluded_neg.append(protein)

    filtered_dataset = SeedDataset(
        seeds_pos=filtered_pos,
        seeds_neg=filtered_neg,
        rows=filtered_rows,
    )

    return filtered_dataset, sorted(set(excluded_pos)), sorted(set(excluded_neg))
 
 

def parse_seed_file(path: str) -> SeedParseResult:

    datasets: Dict[str, List[Tuple[str, float, int]]] = {}
    

    with open(path) as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue

            if line.startswith(">"):
                current_dataset = line[1:].strip()
                if current_dataset in datasets:
                    raise ValueError(f"Duplicate dataset name: {current_dataset}")
                datasets[current_dataset] = []
                continue


            parts = line.split()
            
            if len(parts) < 2:
                raise ValueError(f"Invalid seed line: {line}")
            
            protein = parts[0]
            lfc = float(parts[1])
            
            # optional layer (used only in custom mode)
            layer = None
            if len(parts) >= 3:
                layer = int(parts[2])
            else:
                layer = 1
            datasets[current_dataset].append((protein, lfc, layer))
    parsed = {}

    for name, rows in datasets.items():

        seeds_pos = {}
        seeds_neg = {}

        for protein, lfc, layer in rows:
            if lfc > 0:
                seeds_pos[protein] = lfc
            elif lfc < 0:
                seeds_neg[protein] = abs(lfc)
        parsed[name] = SeedDataset(
            seeds_pos=seeds_pos,
            seeds_neg=seeds_neg,
            rows=rows,
        )
    return SeedParseResult(datasets=parsed)

   

# ---------------------------------------------------------------------
# Apply support layers (PFAM / TF-RC)
# ---------------------------------------------------------------------

def apply_support_layers(dataset, support_file, graph_nodes):

    pos = set(dataset.seeds_pos.keys())
    neg = set(dataset.seeds_neg.keys())
    graph_nodes = set(graph_nodes)

    layers_pos = []
    layers_neg = []

    assigned_pos = set()
    assigned_neg = set()

    with open(support_file) as f:
        for line in f:
            name, *proteins = line.strip().split()
            proteins = set(proteins)

            lp = (proteins & pos) & graph_nodes
            ln = (proteins & neg) & graph_nodes
            
            layers_pos.append(list(lp))
            layers_neg.append(list(ln))

            assigned_pos |= lp
            assigned_neg |= ln

    # residual layer
    layers_pos.append(list((pos - assigned_pos) & graph_nodes))
    layers_neg.append(list((neg - assigned_neg) & graph_nodes))

    return layers_pos, layers_neg


# ---------------------------------------------------------------------
# Main loader
# ---------------------------------------------------------------------
def load_seeds_batch(
    input_file,
    layer_mode,
    support_data_folder,
    sim_mean_std_path,
    sim_all_folder_path,
    graph_nodes,
):

    seed_parse = parse_seed_file(input_file)

    zscores_global = load_zscores(sim_mean_std_path)

    results = {}

    for dataset_name, dataset in seed_parse.datasets.items():
    
        dataset, excluded_pos, excluded_neg = filter_dataset_to_graph(dataset, graph_nodes)
        rows = dataset.rows
        if not rows:
            results[dataset_name] = SeedData(
                seeds_pos={},
                seeds_neg={},
                seeds_layers=[],
                zscores_global=zscores_global,
                ssim={},
                layout=SeedLayout(layers_per_direction={"pos": 0, "neg": 0}),
                excluded_pos=excluded_pos,
                excluded_neg=excluded_neg,
            )
            continue
        
        # ---------------------------------------------------------
        # Layer assignment
        # ---------------------------------------------------------

        if layer_mode == "custom":
            max_layer = max([layer for _, _, layer in rows])

            layers_pos = [[] for _ in range(max_layer)]
            layers_neg = [[] for _ in range(max_layer)]

            for protein, lfc, layer in rows:
                idx = layer - 1
                if lfc > 0:
                    layers_pos[idx].append(protein)
                elif lfc < 0:
                    layers_neg[idx].append(protein)

            layout = SeedLayout(
                layers_per_direction={"pos": max_layer, "neg": max_layer}
            )

        else:
            support_root = Path(support_data_folder).resolve()
            shared_root = support_root.parent

            support_file = {
                "kinases": shared_root / "pfam_domains.txt",
                "tf_rc": shared_root / "receptor_tf.txt",
            }[layer_mode]


            layers_pos, layers_neg = apply_support_layers(
                dataset,
                support_file,
                graph_nodes,
            )

            layout = SeedLayout(
                layers_per_direction={"pos": 3, "neg": 3}
            )

        # ---------------------------------------------------------
        # Similarity (per experiment)
        # ---------------------------------------------------------
       
        ssim = load_semantic_similarity(
            sim_all_folder_path,
            dataset.seeds_pos,
            dataset.seeds_neg,
            graph_nodes,
        )

        results[dataset_name] = SeedData(
            seeds_pos=dataset.seeds_pos,
            seeds_neg=dataset.seeds_neg,
            seeds_layers=layers_pos + layers_neg,
            zscores_global=zscores_global,
            ssim=ssim,
            layout=layout,
            excluded_pos=excluded_pos,
            excluded_neg=excluded_neg,
        )

    return results
