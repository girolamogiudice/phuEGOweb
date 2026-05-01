# -*- coding: utf-8 -*-

from pathlib import Path

import numpy as np
from scipy.spatial.distance import jensenshannon

from .utils import denoise_square, calc_kde, fisher_test
from .kde_optimization import KDEoptimization
from .domain_utils import get_kde_result_dirs


def _safe_kde_threshold(cdf, grid, target):
    cdf = np.asarray(cdf)
    grid = np.asarray(grid)
    if len(cdf) == 0:
        return grid[0] if len(grid) else 0.0
    pos = int(np.searchsorted(cdf, target))
    if pos <= 0:
        return grid[0]
    if pos >= len(cdf):
        return grid[-1]
    if abs(target - cdf[pos]) < abs(target - cdf[pos - 1]):
        return grid[pos]
    return grid[pos - 1]


def ego_friends(
    subnet,
    position_nodes,
    seed_nodes,
    sim,
    zscores,
    kde_cutoff,
    damping_ego_decomposition,
    min_ego_nodes=5,
    z_threshold=1.64,
):
    nodes_kde = {float(k): {} for k in kde_cutoff}
    for seed in sorted(seed_nodes):
        ego = subnet.induced_subgraph(
            subnet.neighborhood(vertices=position_nodes[seed], order=2, mode="all", mindist=0),
            implementation="create_from_scratch",
        )
        nodes = ego.vs["name"]
        if len(nodes) < min_ego_nodes:
            continue

        position_ego = {k: v for v, k in enumerate(nodes)}
        functional_nodes = [position_ego[seed]]

        for node in nodes:
            num = sim[seed][node] - float(zscores[node][0])
            den = float(zscores[node][1])
            if den > 0 and (num / den) > z_threshold and seed != node:
                functional_nodes.append(position_ego[node])
        ego = ego.induced_subgraph(functional_nodes, implementation="copy_and_delete")
        ego = ego.induced_subgraph(
            ego.neighborhood(vertices=ego.vs.find(seed), order=2, mode="all", mindist=0),
            implementation="copy_and_delete",
        )
        ego.vs.select(_degree=0).delete()

        nodes = ego.vs["name"]
        
        if seed not in nodes or len(nodes) <= min_ego_nodes:
            continue

        position_ego = {k: v for v, k in enumerate(nodes)}

        # Keep component containing seed
        if len(ego.connected_components(mode="strong")) > 1 and seed in position_ego:
            ego = ego.induced_subgraph(
                ego.subcomponent(position_ego[seed], mode="all"),
                implementation="copy_and_delete",
            )
            ego.vs.select(_degree=0).delete()
            nodes = ego.vs["name"]
            position_ego = {k: v for v, k in enumerate(nodes)}

        if seed not in position_ego or len(nodes) <= min_ego_nodes:
            continue

        # shell distances
        first_shell = ego.neighbors(position_ego[seed], mode="all")
        distances = dict.fromkeys(first_shell, 1)

        nodes_id = ego.vs.indices
        second_shell = list(set(nodes_id).difference(set(first_shell + [position_ego[seed]])))
        for j in second_shell:
            distances[j] = 2
        distances[position_ego[seed]] = 0

        for e in ego.es:
            node_A, node_B = e.tuple
            distA = distances[node_A]
            distB = distances[node_B]
            if (distA == 1 and distB == 1) or (distA == 2 and distB == 2):
                ego_sim = (sim[seed][nodes[node_A]] + sim[seed][nodes[node_B]]) / 2.0
                e["weight"] = ego_sim
            elif distA == 1 and distB == 2:
                e["weight"] = sim[seed][nodes[node_B]]
            elif distA == 2 and distB == 1:
                e["weight"] = sim[seed][nodes[node_A]]

        ego = denoise_square(ego)
        # seed-centric pagerank
        n_nodes = ego.vcount()
        reset_vertex = np.zeros(n_nodes)
        reset_vertex[position_ego[seed]] = 1.0

        ego_rwr = np.array(
            ego.personalized_pagerank(
                reset=reset_vertex,
                directed=False,
                damping=damping_ego_decomposition,
                weights="weight",
                implementation="prpack",
            )
        )

        ssim_vals = []
        dist_vals = []

        for v in ego.vs:
            reset_vertex = np.zeros(n_nodes)
            reset_vertex[v.index] = 1.0

            ego_node = np.array(
                ego.personalized_pagerank(
                    reset=reset_vertex,
                    directed=False,
                    damping=damping_ego_decomposition,
                    weights="weight",
                    implementation="prpack",
                )
            )

            if seed == v["name"]:
                dist_vals.append(1.0)
            else:
                dist_vals.append(1.0 - jensenshannon(ego_node, ego_rwr))

            ssim_vals.append(sim[seed][v["name"]])

        ssim_vals = np.asarray(ssim_vals)
        dist_vals = np.asarray(dist_vals)

        # legacy scaling
        ssim_vals = 1000 * np.log2(1 + ssim_vals)
        dist_vals = 1000 * np.log2(1 + dist_vals)

        cdf_dist, grid_dist = calc_kde(dist_vals)
        cdf_ssim, grid_ssim = calc_kde(ssim_vals)
        for kde in kde_cutoff:
            kde=float(kde)
            position = np.searchsorted(cdf_dist, kde)
            position = min(position, len(cdf_dist) - 1)
            
            interp = np.argmin([
                abs(kde - cdf_dist[position]),
                abs(kde - cdf_dist[position - 1])
            ])
            thr_dist = grid_dist[position - interp]
            
            position = np.searchsorted(cdf_ssim, kde)
            position = min(position, len(cdf_ssim) - 1)
            
            interp = np.argmin([
                abs(kde - cdf_ssim[position]),
                abs(kde - cdf_ssim[position - 1])
            ])
            thr_ssim = grid_ssim[position - interp]

            nodes_sim = [seed]
            nodes_dist = [seed]
		    
            for idx, node in enumerate(nodes):
                if ssim_vals[idx] > thr_ssim:
                    nodes_sim.append(node)
                if dist_vals[idx] > thr_dist:
                    nodes_dist.append(node)
            
            nodes_kde[float(kde)][seed] = list(set(nodes_sim).intersection(nodes_dist))
    return nodes_kde


def write_results(
    nodes_kde,
    seed_nodes,
    kde_cutoff,
    direction,
    uniprot_to_gene,
    geneset_path,
    fisher_geneset,
    fisher_threshold,
    propagation_value,
    runtime_paths,
):
    all_nodes = {}
    supernodes = {}

    if isinstance(kde_cutoff, str) and kde_cutoff == "optimal":
        kde_key = "optimal"
        nodes_kde_lookup = nodes_kde.get("optimal", {})
    else:
        kde_value = float(kde_cutoff)
        kde_key = f"{kde_value}".rstrip("0").rstrip(".")
        nodes_kde_lookup = nodes_kde.get(kde_value, {})
    print ('direction:', direction)
    print("kde_cutoff:", kde_cutoff)
    print("nodes_kde_lookup size:", len(nodes_kde_lookup))

    dirs = get_kde_result_dirs(runtime_paths, direction, kde_key)
    supernodes[kde_key] = {}
    fisher_proteins = set()
    kde_egos_file = dirs["supernodes"] / "KDE_supernodes_egos.txt"

    with open(kde_egos_file, "w") as f2:
        for seed, members in nodes_kde_lookup.items():
            f2.write(seed + "\t" + "\t".join(members) + "\n")
            if len(members) >= 2:
                supernodes[kde_key][seed] = members
                fisher_proteins.update(members)

    all_nodes[kde_key] = list(fisher_proteins)

    if fisher_proteins:
        fisher_test(
            protein_list=fisher_proteins,
            starting_proteins=seed_nodes,
            fname="",
            threshold=fisher_threshold,
            component=fisher_geneset,
            path_def=str(dirs["enrichment_supernodes"]) + "/",
            uniprot_to_gene=uniprot_to_gene,
            geneset_path=str(geneset_path) + ("" if str(geneset_path).endswith("/") else "/"),
        )

    return supernodes, all_nodes

def ego_filtering(
    network,
    pval,
    seeds,
    sim,
    zscores_global,
    kde_cutoff,
    direction,
    uniprot_to_gene,
    paths,
    geneset_path,
    fisher_geneset,
    fisher_threshold,
    damping_ego_decomposition,
    propagation_value,
    min_ego_nodes=5,
    z_threshold=1.64,
    runtime_paths=None,):
		
    subnet = network.induced_subgraph(
        list(network.vs.select(name_in=pval)),
        implementation="create_from_scratch",
    )
    subnet.vs.select(_degree=0).delete()

    nodes = subnet.vs["name"]
    
    position_nodes = {k: v for v, k in enumerate(nodes)}

    seed_set = set(seeds.keys()) if isinstance(seeds, dict) else set(seeds)
    seed_nodes = list(seed_set.intersection(set(nodes)))
    
    if isinstance(kde_cutoff, str) and kde_cutoff == "optimal":
        kde_values_to_run = list(np.arange(0, 1, 0.01).round(2))
    else:
        kde_values_to_run = [kde_cutoff]
    
    nodes_kde = ego_friends(
        subnet=subnet,
        position_nodes=position_nodes,
        seed_nodes=seed_nodes,
        sim=sim,
        zscores=zscores_global,
        kde_cutoff=kde_values_to_run,
        damping_ego_decomposition=damping_ego_decomposition,
        min_ego_nodes=min_ego_nodes,
        z_threshold=z_threshold,
    )

    if isinstance(kde_cutoff, str) and kde_cutoff == "optimal":
        kde_signature_nodes = {}
        kde_isolated_nodes = {}
    
        for kde, kde_dict in nodes_kde.items():
            signature = []
            isolated = []
    
            for seed, members in kde_dict.items():
                if len(members) == 1:
                    isolated.append(seed)
                else:
                    signature.extend(members)
    
            kde_signature_nodes[kde] = signature
            kde_isolated_nodes[kde] = isolated
    
        kdeopt = KDEoptimization(
            signatures_dict=kde_signature_nodes,
            isolated_nodes_dict=kde_isolated_nodes,
        )
    
        kdeopt.calculate_pagerank_vectors(subnet, isolated_nodes_weight="adjustable")
        new_start = kdeopt.update_start_point()
        W, comp = kdeopt.nmf_worker(start_point=new_start)
        optimal_kde = W.iloc[W.iloc[:, comp].argmax()].name
    
        print(f"[phuego] Optimal KDE detected: {optimal_kde}")
    
        nodes_kde = {"optimal": nodes_kde[float(optimal_kde)]}
        kde_cutoff = "optimal"


    supernodes, all_nodes = write_results(
        nodes_kde=nodes_kde,
        seed_nodes=seed_nodes,
        kde_cutoff=kde_cutoff,
        direction=direction,
        uniprot_to_gene=uniprot_to_gene,
        geneset_path=geneset_path,
        fisher_geneset=fisher_geneset,
        fisher_threshold=fisher_threshold,
        propagation_value=propagation_value,
        runtime_paths=runtime_paths,
    )

    return supernodes, all_nodes
