"""Export-stage graph utilities.

Export stage serializes graphs and tables to disk.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Set, Tuple

import igraph as ig
import pandas as pd


def graph_to_df(module_net: ig.Graph, seed: Set[str], nodes_modules: Dict[str, Set[str]]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Convert a module network to annotated edge/node dataframes."""
    edges = []
    for e in module_net.es:
        ProteinA = module_net.vs[e.source]["name"]
        ProteinA_GeneName = module_net.vs[e.source]["Gene_name"]
        ProteinB = module_net.vs[e.target]["name"]
        ProteinB_GeneName = module_net.vs[e.target]["Gene_name"]
        edge_dict = {
            "ProteinA": ProteinA,
            "ProteinB": ProteinB,
            "ProteinA_GeneName": ProteinA_GeneName,
            "ProteinB_GeneName": ProteinB_GeneName,
            "weight": e["weight"],
            "A_is_seed": ProteinA in seed,
            "B_is_seed": ProteinB in seed,
            "all_modules": [],
        }
        in_any_module = False
        for module_name, node_list in sorted(nodes_modules.items()):
            in_module = (ProteinA in node_list) and (ProteinB in node_list)
            edge_dict[f"is_{module_name}"] = in_module
            if in_module:
                in_any_module = True
                edge_dict["all_modules"].append(module_name.split("_")[1])
        edge_dict["inter_module"] = not in_any_module
        edges.append(edge_dict)
    df_edges = pd.DataFrame(edges)

    nodes = []
    for v in module_net.vs:
        Protein = v["name"]
        Protein_GeneName = v["Gene_name"]
        node_dict = {
            "Protein": Protein,
            "Protein_GeneName": Protein_GeneName,
            "Protein_is_seed": Protein in seed,
        }
        for module_name, node_list in sorted(nodes_modules.items()):
            node_dict[f"is_{module_name}"] = Protein in node_list
        nodes.append(node_dict)
    df_nodes = pd.DataFrame(nodes)
    return df_edges, df_nodes


def write_graph(graph: ig.Graph, path: str | Path, net_format: str) -> None:
    """Write an igraph graph to disk using the requested format."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    ig.write(graph, str(path), format=net_format)
