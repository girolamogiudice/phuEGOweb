# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class RunConfig:
    # experiment root folder (e.g. results/<submission_uuid>/EGFR/)
    submission_uuid:str
    result_folder: str
    support_data_folder: str
    input_file: str

    fisher_geneset: List[str]
    fisher_threshold: float
    fisher_background: str

    ini_pos: List[str]
    ini_neg: List[str]

    damping_seed_propagation: float
    damping_ego_decomposition: float
    damping_module_detection: float

    kde_cutoff: List[Any]          # floats and/or "optimal"
    rwr_threshold: float
    minimum_ego_nodes: int
    zscore_semantic_similarity: float
    semsim: str

    enforce_unique_direction: bool = True
    layer_mode: str = "custom"     # custom | kinases | tf_rc


@dataclass(frozen=True)
class SupportPaths:
    # support-data paths
    support_folder: Path
    network_ncol_path: Path
    network_raw_path: Path
    network_random_path: Path
    gene_name_path: Path
    geneset_path: Path
    sim_mean_std_path: Path
    sim_all_folder_path: Path

    # runtime (experiment) root — used as anchor for KDE output dirs
    results_root: Path


@dataclass(frozen=True)
class Networks:
    network: Any
    network_raw: Any
    graph_nodes: List[str]


@dataclass(frozen=True)
class SeedLayout:
    directions: tuple[str, ...] = ("pos", "neg")
    layers_per_direction: Dict[str, int] = field(default_factory=lambda: {"pos": 3, "neg": 3})

    def total_slots(self) -> int:
        return sum(int(self.layers_per_direction.get(d, 0)) for d in self.directions)

    def slice_for(self, direction: str) -> slice:
        if direction not in self.layers_per_direction:
            raise KeyError(direction)
        start = 0
        for d in self.directions:
            n = int(self.layers_per_direction.get(d, 0))
            if d == direction:
                return slice(start, start + n)
            start += n
        raise KeyError(direction)


@dataclass(frozen=True)
class SeedData:
    seeds_pos: Dict[str, float]
    seeds_neg: Dict[str, float]
    seeds_layers: List[List[str]]
    zscores_global: Dict[str, Any]
    ssim: Dict[str, Dict[str, float]]
    layout: SeedLayout
    layer_names: Optional[List[str]] = None
    excluded_pos: Optional[List[str]] = None
    excluded_neg: Optional[List[str]] = None
