# -*- coding: utf-8 -*-

from itertools import combinations
from pathlib import Path

import igraph as ig
import leidenalg as la
import numpy as np
from scipy.spatial.distance import jensenshannon

from .utils import denoise_square, fisher_test
from .domain_utils import get_kde_result_dirs


def merge_egos(
    network,
    kde_cutoff,
    paths,
    uniprot_to_gene,
    supernodes,
    all_nodes,
    direction,
    geneset_path,
    fisher_geneset,
    fisher_threshold,
    damping_module_detection,
    propagation_value,
    runtime_paths=None,
):
    kde_key = str(kde_cutoff).rstrip("0").rstrip(".") if str(kde_cutoff) != "optimal" else "optimal"
    dirs = get_kde_result_dirs(runtime_paths, direction, kde_key)
    modules_root = dirs["modules"]
    networks_root = dirs["networks"]

    if kde_key not in all_nodes or kde_key not in supernodes:
        (networks_root / "supernodes_net.txt").write_text("")
        return
        å
    
    node_pool = all_nodes.get(kde_key) or []
    snodes = supernodes.get(kde_key) or {}

    if not node_pool or not snodes:
        (networks_root / "supernodes_net.txt").write_text("")
        return

    graph_names = set(network.vs["name"])
    node_pool = list(set(node_pool).intersection(graph_names))
    if not node_pool:
        (networks_root / "supernodes_net.txt").write_text("")
        return

    kde_net = network.induced_subgraph(
        network.vs.select(name_in=node_pool),
        implementation="copy_and_delete",
    )

    sn_keys = list(snodes.keys())
    if len(sn_keys) < 2:
        (networks_root / "supernodes_net.txt").write_text("")
        return

    edges = []
    for a, b in combinations(sn_keys, 2):
        members = set(snodes.get(a, [])).union(snodes.get(b, []))
        members = list(members.intersection(set(kde_net.vs["name"])))
        if len(members) < 2:
            continue

        subnet = kde_net.induced_subgraph(
            kde_net.vs.select(name_in=members),
            implementation="copy_and_delete",
        )
        subnet.vs.select(_degree=0).delete()
        if subnet.vcount() < 2:
            continue

        subnet = denoise_square(subnet)

        nodes = subnet.vs["name"]
        index_net = {k: v for v, k in enumerate(nodes)}
        if a not in index_net or b not in index_net:
            continue

        comps = subnet.connected_components()
        if comps.membership[index_net[a]] != comps.membership[index_net[b]]:
            continue

        n_nodes = subnet.vcount()

        reset = np.zeros(n_nodes)
        reset[index_net[a]] = 1.0
        prA = np.array(
            subnet.personalized_pagerank(
                reset=reset, directed=False, damping=damping_module_detection,
                weights="weight", implementation="prpack"
            )
        )

        reset = np.zeros(n_nodes)
        reset[index_net[b]] = 1.0
        prB = np.array(
            subnet.personalized_pagerank(
                reset=reset, directed=False, damping=damping_module_detection,
                weights="weight", implementation="prpack"
            )
        )

        js = float(jensenshannon(prA, prB))
        if np.isnan(js):
            continue


        if js > 0:
            edges.append((a, b, js))

    supernodes_file = dirs["networks"] / "supernodes_net.txt"
    if not edges:
        supernodes_file.write_text("")
        return

    supernodes_net = ig.Graph.TupleList(edges, weights="weight", directed=False)
    supernodes_net.write(f=str(supernodes_file), format="ncol")
    # module detection
    components = supernodes_net.connected_components()
    modules = []
    for comp in components:
        if len(comp) >= 4:
            cc_net = supernodes_net.induced_subgraph(comp)
            cluster = la.find_partition(
                cc_net,
                la.ModularityVertexPartition,
                weights="weight",
                n_iterations=-1,
                seed=42,
            )
            for part in cluster:
                modules.append(cc_net.vs.select(part)["name"])
        elif 2 <= len(comp) < 4:
            sm_net = supernodes_net.induced_subgraph(comp)
            modules.append(sm_net.vs["name"])

    write_modules(
        clustering=modules,
        nodes=snodes,
        modules_root=modules_root,
        geneset_path=str(geneset_path),
        fisher_geneset=fisher_geneset,
        fisher_threshold=fisher_threshold,
        uniprot_to_gene=uniprot_to_gene,
    )


def write_modules(
    clustering,
    nodes,
    modules_root,
    geneset_path,
    fisher_geneset,
    fisher_threshold,
    uniprot_to_gene,
):
    geneset_path = geneset_path if geneset_path.endswith("/") else geneset_path + "/"

    for idx, module_seeds in enumerate(clustering):
        module_dir = Path(modules_root) / f"module_{idx+1}"
        enrich_dir = module_dir / "enrichment"
        module_dir.mkdir(parents=True, exist_ok=True)
        enrich_dir.mkdir(exist_ok=True)

        module_file = module_dir / "module_egos.txt"
        fisher_proteins = set()

        with open(module_file, "w") as f:
            for seed in module_seeds:
                members = nodes.get(seed, [])
                f.write(seed + "\t" + "\t".join(members) + "\n")
                fisher_proteins.update(members)
        if fisher_proteins:
            fisher_test(
                protein_list=fisher_proteins,
                starting_proteins=module_seeds,
                threshold=fisher_threshold,
                component=fisher_geneset,
                path_def=str(enrich_dir) + "/",
                uniprot_to_gene=uniprot_to_gene,
                geneset_path=geneset_path,
                fname="",
            )
