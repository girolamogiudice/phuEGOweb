# -*- coding: utf-8 -*-
"""Utilities to construct :mod:`phuego.domain` objects.

The aim of the "domain" refactor is to keep the CLI and outputs stable while
making the internal objects explicit and easier to reason about.

These helpers:

* normalise folder paths
* parse/expand KDE cutoff specification
* resolve support data paths based on the chosen options
* load reference networks
"""

from __future__ import annotations

from pathlib import Path

from typing import List, Set, Any

import igraph as ig

from .domain import Networks, RunConfig, SupportPaths
from .utils import add_trailing_slash, translate_kde_field


def parse_kde_cutoff(kde_cutoff_spec: str) -> List[Any]:
    """
    Parse a CLI KDE cutoff spec:
      - "optimal"
      - comma-separated floats
      - ranges like "0.82-0.95"
    Returns list containing floats and/or the string "optimal".
    """
    kde_cutoff_spec = str(kde_cutoff_spec).replace(" ", "")
    fields = kde_cutoff_spec.split(",") if kde_cutoff_spec else []
    values: Set[Any] = set()
    for field in fields:
        for v in translate_kde_field(field):
            values.add(v)
    # keep "optimal" if present; sort floats
    floats = sorted([v for v in values if isinstance(v, (float, int))])
    out: List[Any] = floats
    if "optimal" in values:
        out.append("optimal")
    
    return out


def resolve_support_paths(cfg: RunConfig) -> SupportPaths:
    """
    Resolve ONLY support-data paths + the experiment root anchor.
    Do NOT create legacy runtime folders here (modules/enrichment/networks).
    """
    support = Path(add_trailing_slash(cfg.support_data_folder))
    results_root = Path(add_trailing_slash(cfg.result_folder))

    # ---- Update these filenames if your support folder differs ----
    # (I am aligning them to what your current code expects.)
    networks_folder = support / "networks"

    return SupportPaths(
        support_folder=support,
        network_ncol_path=networks_folder / "gic.pickle",
        network_raw_path=networks_folder / "gic_raw.pickle",
        network_random_path=networks_folder / "gic_random",
        gene_name_path=support / "uniprot_to_gene.tab",
        geneset_path=support / "genesets",
        sim_mean_std_path=support / "semsim_mean_std.txt",
        sim_all_folder_path=support / "gic_sim",
        results_root=results_root,
    )


def attach_runtime_paths(paths: SupportPaths, results_root: str) -> SupportPaths:
    """
    Keep for backwards compatibility: ensures results_root exists and returns
    a new SupportPaths with results_root overwritten.
    """
    rr = Path(add_trailing_slash(results_root))
    rr.mkdir(parents=True, exist_ok=True)
    return SupportPaths(
        support_folder=paths.support_folder,
        network_ncol_path=paths.network_ncol_path,
        network_raw_path=paths.network_raw_path,
        network_random_path=paths.network_random_path,
        gene_name_path=paths.gene_name_path,
        geneset_path=paths.geneset_path,
        sim_mean_std_path=paths.sim_mean_std_path,
        sim_all_folder_path=paths.sim_all_folder_path,
        results_root=rr,
    )


def load_networks(paths: SupportPaths) -> Networks:
    network = ig.Graph.Read_Pickle(str(paths.network_ncol_path))
    network_raw = ig.Graph.Read_Pickle(str(paths.network_raw_path))
    graph_nodes = list(network.vs["name"])
    return Networks(network=network, network_raw=network_raw, graph_nodes=graph_nodes)




def _normalize_kde(kde):
    if isinstance(kde, (float, int)):
        return f"{kde}".rstrip("0").rstrip(".")

    if isinstance(kde, str):
        kde = kde.strip()
        try:
            val = float(kde)
            return f"{val}".rstrip("0").rstrip(".")
        except ValueError:
            if kde.isalpha():
                return kde

    raise ValueError(f"Invalid KDE value: {kde}")


def get_kde_result_dirs(runtime_paths, direction: str, kde):
    if isinstance(kde, (list, tuple, set)):
        raise TypeError(f"KDE must be a single value, got iterable: {kde}")

    kde_norm = _normalize_kde(kde)

    propagation_root = runtime_paths.prop_root
    direction_root = propagation_root / direction
    kde_root = direction_root / f"KDE_{kde_norm}"

    dirs = {
        "propagation_root": propagation_root,
        "direction_root": direction_root,
        "kde_root": kde_root,

        # keep current algorithm-facing layout
        "modules": kde_root / "modules",
        "supernodes": kde_root / "supernodes",
        "enrichment_supernodes": kde_root / "supernodes" / "enrichment",

        "networks": kde_root / "networks",

        # new table separation
        "tables": kde_root / "tables",
        "supernodes_tables": kde_root / "tables" / "supernodes",
        "modules_tables": kde_root / "tables" / "modules",

        }

    for p in dirs.values():
        p.mkdir(parents=True, exist_ok=True)

    return dirs
