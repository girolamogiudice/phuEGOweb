# -*- coding: utf-8 -*-

from __future__ import annotations

from pathlib import Path

import igraph as ig
import numpy as np
from scipy import sparse
from tqdm import tqdm
from phuego_standalone.io.progress import update_progress
from phuego_standalone.io.cancel import raise_if_cancelled


# --------------------------------------------------
# Utilities
# --------------------------------------------------

def flatten_seed_layers(seeds_layers, direction, layout):
    """
    Flatten seed layers for a given direction ("pos" or "neg").
    """
    sl = layout.slice_for(direction)
    return [gene for layer in seeds_layers[sl] for gene in layer]


def _build_reset_vectors(
    graph: ig.Graph,
    seeds_layers,
    seeds_pos,
    seeds_neg,
    layout,
) -> tuple[np.ndarray, list[str]]:
    """
    Build reset vectors for all slots as a dense matrix of shape:
        (n_slots, n_nodes)

    The weights come from:
      - seeds_pos for positive slots
      - seeds_neg for negative slots
    """
    names = graph.vs["name"]
    name_to_idx = {n: i for i, n in enumerate(names)}

    n_slots = layout.total_slots()
    n_nodes = graph.vcount()
    resets = np.zeros((n_slots, n_nodes), dtype=np.float32)

    npos = int(layout.layers_per_direction["pos"])

    for slot_idx, layer_seeds in enumerate(seeds_layers):
        if not layer_seeds:
            continue

        weights = seeds_pos if slot_idx < npos else seeds_neg

        for s in layer_seeds:
            j = name_to_idx.get(s)
            if j is not None:
                resets[slot_idx, j] = float(weights.get(s, 0.0))

    # normalize each reset vector
    row_sums = resets.sum(axis=1, keepdims=True)
    nonzero = row_sums[:, 0] > 0
    resets[nonzero] /= row_sums[nonzero]

    return resets, names


def _graph_to_transition_t(graph: ig.Graph) -> sparse.csr_matrix:
    """
    Build sparse transition transpose matrix M such that:
        R_next = damping * (M @ R) + (1 - damping) * reset

    For an undirected weighted graph:
      each edge (u, v, w) contributes:
        v <- u with prob w / deg[u]
        u <- v with prob w / deg[v]

    Returns
    -------
    scipy.sparse.csr_matrix of shape (n_nodes, n_nodes)
    """
    n = graph.vcount()
    edges = graph.get_edgelist()

    weights_attr = graph.es["weight"] if "weight" in graph.es.attributes() else None
    if weights_attr is None:
        weights = np.ones(len(edges), dtype=np.float32)
    else:
        weights = np.asarray(weights_attr, dtype=np.float32)

    deg = np.zeros(n, dtype=np.float64)

    for (u, v), w in zip(edges, weights):
        deg[u] += w
        deg[v] += w

    deg[deg == 0] = 1.0

    rows = []
    cols = []
    data = []

    for (u, v), w in zip(edges, weights):
        rows.append(v)
        cols.append(u)
        data.append(w / deg[u])

        rows.append(u)
        cols.append(v)
        data.append(w / deg[v])

    mat = sparse.csr_matrix(
        (np.asarray(data, dtype=np.float32), (rows, cols)),
        shape=(n, n),
        dtype=np.float32,
    )
    return mat


def _pagerank_multi_slot_power(
    graph: ig.Graph,
    resets: np.ndarray,
    damping: float,
    max_iter: int = 200,
    tol: float = 1e-8,
) -> np.ndarray:
    """
    Compute personalized PageRank for all slots simultaneously.
    Returns array of shape (n_slots, n_nodes)
    """
    n_slots, n_nodes = resets.shape
    if n_slots == 0 or n_nodes == 0:
        return np.zeros_like(resets, dtype=np.float32)

    reset_mat = resets.T.astype(np.float32, copy=False)  # (n_nodes, n_slots)
    M = _graph_to_transition_t(graph)

    R = reset_mat.copy()

    for _ in range(max_iter):
        R_new = damping * (M @ R) + (1.0 - damping) * reset_mat
        diff = np.max(np.abs(R_new - R))
        R = R_new
        if diff < tol:
            break

    return R.T.astype(np.float32, copy=False)


# --------------------------------------------------
# RWR
# --------------------------------------------------

def rwr_values(
    network,
    graph_nodes,
    ini_pos,
    ini_neg,
    seeds,
    seeds_pos,
    seeds_neg,
    network_path,
    network_random_path,
    damping_seed_propagation,
    res_folder,
    layout=None,
    n_permutations=1000,
):
    seed_batches = {
        "exp": type("SeedData", (), {
            "seeds_layers": seeds,
            "seeds_pos": seeds_pos,
            "seeds_neg": seeds_neg,
            "layout": layout
        })()
    }

    rwr_values_batch(
        network=network,
        graph_nodes=graph_nodes,
        seed_batches=seed_batches,
        network_random_path=network_random_path,
        damping_seed_propagation=damping_seed_propagation,
        res_folder=res_folder,
        n_permutations=n_permutations,
    )


# --------------------------------------------------
# P-value split
# --------------------------------------------------

def pvalue_split(
    res_folder,
    seeds_pos,
    seeds_neg,
    graph_nodes,
    rwr_threshold,
    fisher_threshold,
    fisher_geneset,
    uniprot_to_gene,
    geneset_path,
    layout,
    *,
    enforce_unique=True,
):
    """
    Reads pvalues.txt and selects genes with p <= rwr_threshold.
    Also returns raw overlap BEFORE enforcing uniqueness.
    """
    res_folder = Path(res_folder)

    pvalues_pos = set(seeds_pos.keys())
    pvalues_neg = set(seeds_neg.keys())

    threshold = float(rwr_threshold)

    pos_slice = layout.slice_for("pos")
    neg_slice = layout.slice_for("neg")

    with open(res_folder / "pvalues.txt") as f:
        next(f)
        for line in f:
            gene, *vals = line.strip().split("\t")
            vals = np.asarray(vals, dtype=float)

            if vals[pos_slice].min() < threshold:
                pvalues_pos.add(gene)

            if vals[neg_slice].min() < threshold:
                pvalues_neg.add(gene)

    # 🔥 capture overlap BEFORE filtering
    raw_overlap = pvalues_pos.intersection(pvalues_neg)

    if enforce_unique:
        rwr_pos = {}
        rwr_neg = {}

        with open(res_folder / "rwr_scores.txt") as f:
            next(f)
            for line in f:
                gene, *vals = line.strip().split("\t")
                vals = np.asarray(vals, dtype=float)

                rwr_pos[gene] = float(np.mean(vals[pos_slice]))
                rwr_neg[gene] = float(np.mean(vals[neg_slice]))

        overlap = raw_overlap

        remove_from_pos = set()
        remove_from_neg = set()

        for g in overlap:
            if rwr_pos.get(g, 0.0) < rwr_neg.get(g, 0.0):
                remove_from_pos.add(g)
            elif rwr_neg.get(g, 0.0) < rwr_pos.get(g, 0.0):
                remove_from_neg.add(g)

        pvalues_pos -= remove_from_pos
        pvalues_neg -= remove_from_neg

    graph_nodes = set(graph_nodes)
    pvalues_pos &= graph_nodes
    pvalues_neg &= graph_nodes

    return pvalues_pos, pvalues_neg, raw_overlap

def rwr_values_batch(
    network,
    graph_nodes,
    seed_batches,
    network_random_path,
    damping_seed_propagation,
    res_folder,
    n_permutations=1000,
    run_dir=None,   # ✅ ADD THIS
):
    res_folder = Path(res_folder)
    res_folder.mkdir(parents=True, exist_ok=True)
    run_dir = Path(run_dir or res_folder)

    network_random_path = Path(network_random_path)

    # --------------------------------------------------
    # Use empirical network ordering as reference
    # --------------------------------------------------

    aligned_nodes = list(network.vs["name"])
    n_nodes = len(aligned_nodes)

    # --------------------------------------------------
    # Flatten seeds across experiments
    # --------------------------------------------------

    resets_list = []
    exp_slot_counts = []

    for exp_name, seed_data in seed_batches.items():
        resets, _ = _build_reset_vectors(
            graph=network,
            seeds_layers=seed_data.seeds_layers,
            seeds_pos=seed_data.seeds_pos,
            seeds_neg=seed_data.seeds_neg,
            layout=seed_data.layout,
        )

        resets_list.append(resets)
        exp_slot_counts.append((exp_name, seed_data, resets.shape[0]))

    resets_all = np.vstack(resets_list).astype(np.float32)
    n_slots = resets_all.shape[0]

    # --------------------------------------------------
    # Empirical RWR
    # --------------------------------------------------

    empirical_rwr = _pagerank_multi_slot_power(
        graph=network,
        resets=resets_all,
        damping=float(damping_seed_propagation),
    )

    # --------------------------------------------------
    # Permutation counts
    # --------------------------------------------------

    pcount = np.zeros((n_slots, n_nodes), dtype=np.int32)

    # --------------------------------------------------
    # Random networks (pickle + ordered)
    # --------------------------------------------------
    submission_root = run_dir
    update_progress(
        submission_root,
        status="running",
        step="rwr_permutations",
        message="Starting RWR permutations",
    )


    for ii in tqdm(range(int(n_permutations)), desc="RWR permutations", unit="perm"):
        if ii % 10 == 0:
            raise_if_cancelled(submission_root)

        if ii % 100 == 0 or ii == n_permutations:
        
            update_progress(
                submission_root,
                status="running",
                step="rwr_permutations",
                progress={
                    "current": ii,
                    "total": n_permutations,
                    "unit": "permutations"
                },
                message=f"Permutation {ii}/{n_permutations}",
            )
        
        rand_file = network_random_path / f"{ii}.pickle"

        net_rand = ig.Graph.Read_Pickle(str(rand_file))

        # Safety check: if you generated ordered pickles correctly,
        # this should always pass.
        if net_rand.vs["name"] != aligned_nodes:
            raise RuntimeError(
                f"Random network node order mismatch in {rand_file}. "
                "Regenerate/reorder pickle files so they match gic_raw/gic."
            )

        rand_rwr = _pagerank_multi_slot_power(
            graph=net_rand,
            resets=resets_all,
            damping=float(damping_seed_propagation),
        )

        # POC-equivalent logic: count how often empirical > random
        pcount += (empirical_rwr > rand_rwr).astype(np.int32)

    # --------------------------------------------------
    # Convert to p-values
    # --------------------------------------------------

    pvals = 1.0 - (pcount.astype(np.float32) / float(n_permutations))

    # --------------------------------------------------
    # Write per experiment
    # --------------------------------------------------

    slot_idx = 0

    for exp_name, seed_data, n_slots_exp in exp_slot_counts:
        rwr_slice = empirical_rwr[slot_idx:slot_idx + n_slots_exp]
        pval_slice = pvals[slot_idx:slot_idx + n_slots_exp]

        exp_folder = Path(res_folder) / exp_name
        exp_folder.mkdir(parents=True, exist_ok=True)
        header = "uniprotid\t" + "\t".join(
            f"slot_{i}" for i in range(n_slots_exp)
        ) + "\n"

        with open(exp_folder / "rwr_scores.txt", "w") as f:
            f.write(header)
            for j, name in enumerate(aligned_nodes):
                vals = rwr_slice[:, j]
                f.write(name + "\t" + "\t".join(map(str, vals)) + "\n")

        with open(exp_folder / "pvalues.txt", "w") as f:
            f.write(header)
            for j, name in enumerate(aligned_nodes):
                vals = pval_slice[:, j]
                f.write(name + "\t" + "\t".join(map(str, vals)) + "\n")

        slot_idx += n_slots_exp
    update_progress(
        submission_root,
        status="completed",
        step="rwr_permutations",
        message="RWR completed",
    )
