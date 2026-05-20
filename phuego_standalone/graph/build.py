"""Build-stage graph utilities.

The build stage derives new graph *topologies* from existing graphs.
It should not read or write files; pass parsed inputs in.

All graphs are igraph.Graph objects.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Sequence, Set, Tuple

import igraph as ig


def build_rwr_networks(
    base_network: ig.Graph,
    seeds_increase: Sequence[str],
    seeds_decrease: Sequence[str],
    rwr_hits_increase: Sequence[str],
    rwr_hits_decrease: Sequence[str],
) -> Tuple[ig.Graph, ig.Graph]:
    """Derive RWR hit networks for increased/decreased directions.

    Parameters
    ----------
    base_network:
        The full interactome (already loaded).
    seeds_increase, seeds_decrease:
        Direction-specific seed node IDs.
    rwr_hits_increase, rwr_hits_decrease:
        Direction-specific RWR-selected node IDs (excluding seeds is ok).

    Returns
    -------
    (rwr_increased, rwr_decreased)
        Induced subgraphs for each direction.
    """
    pos_nodes = list(dict.fromkeys(list(rwr_hits_increase) + list(seeds_increase)))
    neg_nodes = list(dict.fromkeys(list(rwr_hits_decrease) + list(seeds_decrease)))
    rwr_increased = base_network.induced_subgraph(pos_nodes)
    rwr_increased["title"] = "RWR_increased_net"

    rwr_decreased = base_network.induced_subgraph(neg_nodes)
    rwr_decreased["title"] = "RWR_decreased_net"

    return rwr_increased, rwr_decreased


def build_kde_signature_network(
    rwr_network: ig.Graph,
    signature_nodes: Iterable[str],
    title: str,
) -> ig.Graph:
    """Derive KDE signature network from a direction-specific RWR network."""
    nodes = list(signature_nodes)
    if not nodes:
        kde_net = ig.Graph()
        kde_net["title"] = title
        return kde_net

    kde_net = rwr_network.induced_subgraph(nodes)
    kde_net["title"] = title
    return kde_net


def build_module_network(kde_network, nodes_by_module, title):
    if kde_network.vcount() == 0:
        module_net = ig.Graph()
        module_net["title"] = title
        return module_net

    kde_nodes = set(kde_network.vs["name"])

    all_nodes = set()
    for nodes in nodes_by_module.values():
        all_nodes.update(nodes)

    valid_nodes = [n for n in all_nodes if n in kde_nodes]
    if not valid_nodes:
        module_net = ig.Graph()
        module_net["title"] = title
        return module_net

    module_net = kde_network.induced_subgraph(valid_nodes)
    module_net["title"] = title

    return module_net
