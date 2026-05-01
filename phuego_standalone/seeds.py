"""
Seed loading abstraction layer.

Currently wraps load_seeds_generic, but centralizing this now allows
future support for:
    - multi-layer seeds
    - phosphosite-level seeds
    - GNN-ready seed representations
"""

"""
Seed loading abstraction layer.
"""

from .load_seeds_generic import load_seeds_batch


def load_seed_data(cfg, paths, graph_nodes, ini_pos, ini_neg):

    return load_seeds_batch(
        input_file=cfg.input_file,
        layer_mode=cfg.layer_mode,
        support_data_folder=str(paths.support_folder),
        sim_mean_std_path=str(paths.sim_mean_std_path),
        sim_all_folder_path=str(paths.sim_all_folder_path),
        graph_nodes=graph_nodes,
    )
