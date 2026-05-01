from pathlib import Path

from .graph.build import build_kde_signature_network, build_module_network
from .graph.annotate import annotate_module_membership, annotate_module_labels_and_colors
from .graph.export import graph_to_df
from .domain_utils import get_kde_result_dirs
from .io.fs import iter_visible_dirs


def _read_signature_nodes(sig_file, include_isolated):
    nodes = set()
    with open(sig_file) as f:
        for line in f:
            parts = line.strip().split("\t")
            if not parts or parts == [""]:
                continue
            if include_isolated:
                nodes.update(parts)
            else:
                if len(parts) > 2:
                    nodes.update(parts)
    return nodes


def _read_modules(modules_dir):
    nodes_by_module = {}
    modules = []

    for module_dir in iter_visible_dirs(modules_dir):
        ego_file = module_dir / "module_egos.txt"
        if not ego_file.exists():
            continue

        module_name = module_dir.name
        modules.append(module_name)

        nodes = set()
        with open(ego_file) as f:
            for line in f:
                parts = line.strip().split("\t")
                if len(parts) >= 2:
                    nodes.update(parts[1:])

        nodes_by_module[module_name] = nodes

    return modules, nodes_by_module


def generate_nets(
    paths,
    base_network,
    seeds_increase,
    seeds_decrease,
    kde_cutoff,
    include_isolated_egos_in_KDE_net,
    uniprot_to_gene,
    propagation_value,
    runtime_paths,
):
    results = {"kde_networks": {}, "module_networks": {}, "module_tables": {},    "modules_len": {}}

    # all seeds for export highlighting
    seed_all = set()
    for d in (seeds_increase, seeds_decrease):
        for kde_dict in d.values():
            for nodes in kde_dict.values():
                seed_all.update(nodes)

    for direction, seeds in {"increased": seeds_increase, "decreased": seeds_decrease}.items():
        kde = kde_cutoff
        kde_key = str(kde)
        
        dirs = get_kde_result_dirs(runtime_paths, direction, kde_key)
        sig_file = dirs["supernodes"] / "KDE_supernodes_egos.txt"
        modules_dir = dirs["modules"]
        
        if not sig_file.exists():
            continue
        
        signature_nodes = _read_signature_nodes(sig_file, include_isolated_egos_in_KDE_net)
        
        kde_network = build_kde_signature_network(
            base_network,
            signature_nodes,
            f"KDE_{direction}_net",
        )
        results["kde_networks"][(direction, kde_key)] = kde_network
        
        if not modules_dir.exists():
            continue
        
        modules, nodes_by_module = _read_modules(modules_dir)
        results["modules_len"][(direction, kde_key)] = len(modules)

        if not nodes_by_module:
            continue
        
        annotate_module_membership(kde_network, nodes_by_module)
        
        module_net = build_module_network(
            kde_network,
            nodes_by_module,
            f"Module_{direction}_net",
        )
        annotate_module_labels_and_colors(module_net, modules)
        
        for v in module_net.vs:
            v["Gene_name"] = uniprot_to_gene.get(v["name"], v["name"])
        
        results["module_networks"][(direction, kde_key)] = module_net
        
        df_edges, df_nodes = graph_to_df(module_net, seed_all, nodes_by_module)
        results["module_tables"][(direction, kde_key)] = (df_edges, df_nodes)

    return results
