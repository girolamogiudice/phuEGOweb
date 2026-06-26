
# -*- coding: utf-8 -*-

import os
from pathlib import Path

from .domain import RunConfig
from .domain_utils import attach_runtime_paths, load_networks, resolve_support_paths
from .ego import ego_filtering
from .ego2module import merge_egos
from .generate_net import generate_nets
from .seeds import load_seed_data
from .network_rwr import pvalue_split, rwr_values_batch
from .paths import ExperimentPaths
from .io.export_sigma_supernodes import export_supernodes_sigma
from .io.export_sigma_module_meta import export_module_meta_sigma
from .io.export_sigma_modules import export_modules_sigma
from .io.summary_stats import write_summary_stats, write_summary_stats_file
from .io.manifest import write_manifest
from .io.enrichment_heatmap import write_enrichment_heatmap
from .io.enrichment_export import write_enrichment_json
from .io.cross_experiment import build_cross_experiment_analysis
from .io.opentargets import load_opentargets_lookup
from .io.progress import update_progress
from .io.cancel import raise_if_cancelled

from .utils import (
    add_trailing_slash,
    load_gene_names,
    write_start_seeds,
)

def _normalize_kde(kde):
    if str(kde).lower() == "optimal":
        return "optimal"
    return f"{float(kde):.2f}".rstrip("0").rstrip(".")
    
def compute_seed_graph_stats(
    seeds_pos,
    seeds_neg,
    graph_nodes,
    uniprot_to_gene,
    excluded_pos=None,
    excluded_neg=None,
):
    pos = set(seeds_pos.keys())
    neg = set(seeds_neg.keys())
    graph_nodes = set(graph_nodes)

    pos_in = pos & graph_nodes
    neg_in = neg & graph_nodes

    pos_missing = (pos - graph_nodes) | set(excluded_pos or [])
    neg_missing = (neg - graph_nodes) | set(excluded_neg or [])

    def annotate(proteins):
        return {p: uniprot_to_gene.get(p, p) for p in proteins}

    return {
        "pos": {
            "total": len(pos),
            "in_graph": len(pos_in),
            "missing": annotate(pos_missing),
        },
        "neg": {
            "total": len(neg),
            "in_graph": len(neg_in),
            "missing": annotate(neg_missing),
        }
    }


def compute_kde_stats(nodes_kde, seeds_in_graph, uniprot_to_gene=None):
    stats = {}
    uniprot_to_gene = uniprot_to_gene or {}

    for kde, seed_dict in (nodes_kde or {}).items():
        supernodes = {s for s, m in seed_dict.items() if len(m) >= 2}
        low_degree = set(seeds_in_graph) - supernodes

        low_degree_missing = {
            p: uniprot_to_gene.get(p, p)
            for p in sorted(low_degree)
        }

        stats[str(kde)] = {
            "supernodes_count": len(supernodes),
            "low_degree_count": len(low_degree),
            "low_degree_missing": low_degree_missing,
        }

    return stats


def compute_supernode_module_overlap(supernodes_file, modules_root):
    from pathlib import Path
    from .io.fs import iter_visible_dirs

    supernodes = set()

    if Path(supernodes_file).exists():
        with open(supernodes_file) as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 2:
                    supernodes.add(parts[0])
                    supernodes.add(parts[1])

    module_seeds = set()

    modules_root = Path(modules_root)
    if modules_root.exists():
        for module_dir in iter_visible_dirs(modules_root):
            f = module_dir / "module_egos.txt"
            if not f.exists():
                continue

            with open(f) as fh:
                for line in fh:
                    seed = line.strip().split("\t")[0]
                    module_seeds.add(seed)

    return {
        "supernodes_count": len(supernodes),
        "in_modules": len(supernodes & module_seeds),
    }
    

def phuego(    
    submission_uuid,
    support_data_folder,
    res_folder,
    input_file,
    fisher_geneset,
    fisher_threshold,
    fisher_background,
    ini_pos,
    ini_neg,
    damping_seed_propagation,
    damping_ego_decomposition,
    damping_module_detection,
    kde_cutoff,
    rwr_threshold,
    semsim,
    minimum_ego_nodes=5,
    zscore_semantic_similarity=1.64,
    use_existing_rwr=False,
    rwr_random_folder=None,
    convert2folder=False,
    include_isolated_egos_in_KDE_net=False,
    net_format="ncol",
    enforce_unique_direction=True,
    layer_mode="custom",
):

    # --------------------------------------------------
    # Input formatting
    # --------------------------------------------------

    support_data_folder = add_trailing_slash(str(support_data_folder))
    res_folder = add_trailing_slash(str(res_folder))
    os.makedirs(res_folder, exist_ok=True)

    shared_root = Path(support_data_folder).parent
    ot_path = shared_root / "opentargets_lookup.pkl"
    ot_lookup = load_opentargets_lookup(ot_path)

    try:
        rwr_threshold = float(rwr_threshold)
    except Exception:
        raise ValueError("rwr_threshold must be numeric (e.g. 0.05)")

    if rwr_threshold > 0.1 or rwr_threshold < 0.01:
        raise ValueError("rwr_threshold should be within range [0.01, 0.1]")

    fisher_geneset_list = (
        fisher_geneset.split(",")
        if isinstance(fisher_geneset, str)
        else list(fisher_geneset)
    )

    cfg = RunConfig(
        result_folder=res_folder,
        submission_uuid=submission_uuid,
        support_data_folder=support_data_folder,
        input_file=input_file,
        fisher_geneset=fisher_geneset_list,
        fisher_threshold=float(fisher_threshold),
        fisher_background=str(fisher_background),
        ini_pos=list(ini_pos),
        ini_neg=list(ini_neg),
        damping_seed_propagation=float(damping_seed_propagation),
        damping_ego_decomposition=float(damping_ego_decomposition),
        damping_module_detection=float(damping_module_detection),
        kde_cutoff=kde_cutoff,
        rwr_threshold=float(rwr_threshold),
        minimum_ego_nodes=int(minimum_ego_nodes),
        zscore_semantic_similarity=float(zscore_semantic_similarity),
        semsim=str(semsim),
        enforce_unique_direction=bool(enforce_unique_direction),
        layer_mode=str(layer_mode),
    )
    propagation_value = float(cfg.damping_seed_propagation)

    # --------------------------------------------------
    # Support paths + networks
    # --------------------------------------------------

    paths = resolve_support_paths(cfg)
    paths = attach_runtime_paths(paths, cfg.result_folder)

    nets = load_networks(paths)

    network = nets.network
    network_raw = nets.network_raw
    graph_nodes = nets.graph_nodes

    uniprot_to_gene = load_gene_names(paths.gene_name_path)

    # --------------------------------------------------
    # Seeds (batch aware)
    # --------------------------------------------------

    seed_batches = load_seed_data(cfg, paths, graph_nodes, ini_pos, ini_neg)

    # ==================================================
    # RUN RWR ONCE FOR ALL EXPERIMENTS
    # ==================================================

    print("[phuego] Running batch RWR")


    submission_root = Path(cfg.result_folder) / cfg.submission_uuid
    raise_if_cancelled(submission_root)
    
    rwr_exists = True
    
    for exp_name in seed_batches:
        rwr_file = submission_root / exp_name / "rwr_scores.txt"
        if not rwr_file.exists():
            rwr_exists = False
            break
    if use_existing_rwr and rwr_exists:
        print("[phuego] Using existing RWR results")
    else:
        print("[phuego] Running batch RWR")
    
        rwr_values_batch(
            network=network,
            graph_nodes=graph_nodes,
            seed_batches=seed_batches,
            network_random_path=paths.network_random_path,
            damping_seed_propagation=propagation_value,
            res_folder=str(submission_root),
            run_dir=submission_root,
        )

    results = {}
    raise_if_cancelled(submission_root)

    # ==================================================
    # LOOP EXPERIMENTS
    # ==================================================
    total_experiments = len(seed_batches)
    finished_experiments = 0

    update_progress(
        submission_root,
        status="running",
        step="batch_start",
        message="Starting batch analysis",
        batch={
            "finished_experiments": 0,
            "total_experiments": total_experiments,
        }
    )


    for exp_name, seed_data in seed_batches.items():
        raise_if_cancelled(submission_root)

        print(f"[phuego] Processing experiment: {exp_name}")

        update_progress(
            submission_root,
            status="running",
            step="experiment_start",
            message=f"Starting experiment {exp_name}",
            batch={
                "current_experiment": exp_name,
                "finished_experiments": finished_experiments,
                "total_experiments": total_experiments,
            }
        )


        paths_runtime = ExperimentPaths(
            submission_root=submission_root,
            experiment_name=exp_name,
            propagation=propagation_value,
        )

        paths_runtime.ensure()

        run_out_folder = paths_runtime.prop_root


        layout = seed_data.layout
        seeds = seed_data.seeds_layers
        seeds_pos = seed_data.seeds_pos
        seeds_neg = seed_data.seeds_neg
    
        seed_graph_stats = compute_seed_graph_stats(
            seeds_pos,
            seeds_neg,
            graph_nodes,
            uniprot_to_gene,
            excluded_pos=seed_data.excluded_pos,
            excluded_neg=seed_data.excluded_neg,
        )
    
        zscores_global = seed_data.zscores_global
        ssim = seed_data.ssim

        # --------------------------------------------------
        # Write seeds
        # --------------------------------------------------

        write_start_seeds(
            res_folder=str(run_out_folder),
            seeds_pos=seeds_pos,
            seeds_neg=seeds_neg,
            seeds_layers=seed_data.seeds_layers,
            layout=layout,
        )
       
        # --------------------------------------------------
        # P-value split
        # --------------------------------------------------

        pvalues_pos, pvalues_neg, raw_overlap = pvalue_split(
            res_folder=str(Path(cfg.result_folder) / cfg.submission_uuid / exp_name),
            seeds_pos=seeds_pos,
            seeds_neg=seeds_neg,
            graph_nodes=graph_nodes,
            rwr_threshold=cfg.rwr_threshold,
            fisher_threshold=cfg.fisher_threshold,
            fisher_geneset=cfg.fisher_geneset,
            uniprot_to_gene=uniprot_to_gene,
            geneset_path=paths.geneset_path,
            layout=layout,
            enforce_unique=cfg.enforce_unique_direction,
        )
        
        rwr_stats = {
        "pos_count": len(pvalues_pos),
        "neg_count": len(pvalues_neg),
        "overlap_count": len(raw_overlap)}

        raise_if_cancelled(submission_root)


        # --------------------------------------------------
        # Ego filtering
        # --------------------------------------------------

        update_progress(
            submission_root,
            status="running",
            step="ego_filtering",
            message=f"{exp_name}: ego filtering",
            batch={
                "current_experiment": exp_name,
                "finished_experiments": finished_experiments,
                "total_experiments": total_experiments,
            }
        )



        nodes_kde_pos, all_nodes_pos = ego_filtering(
            network,
            pvalues_pos,
            seeds_pos,
            ssim,
            zscores_global,
            cfg.kde_cutoff,
            "increased",
            uniprot_to_gene,
            paths,
            paths.geneset_path,
            cfg.fisher_geneset,
            cfg.fisher_threshold,
            cfg.damping_ego_decomposition,
            propagation_value,
            min_ego_nodes=cfg.minimum_ego_nodes,
            z_threshold=cfg.zscore_semantic_similarity,
            runtime_paths=paths_runtime,
        )

        raise_if_cancelled(submission_root)



        nodes_kde_neg, all_nodes_neg = ego_filtering(
            network,
            pvalues_neg,
            seeds_neg,
            ssim,
            zscores_global,
            cfg.kde_cutoff,
            "decreased",
            uniprot_to_gene,
            paths,
            paths.geneset_path,
            cfg.fisher_geneset,
            cfg.fisher_threshold,
            cfg.damping_ego_decomposition,
            propagation_value,
            min_ego_nodes=cfg.minimum_ego_nodes,
            z_threshold=cfg.zscore_semantic_similarity,
            runtime_paths=paths_runtime,
        )
        seeds_in_graph_pos = set(seeds_pos.keys()) & set(graph_nodes)
        seeds_in_graph_neg = set(seeds_neg.keys()) & set(graph_nodes)
        
        kde_stats = {
            "increased": compute_kde_stats(nodes_kde_pos, seeds_in_graph_pos, uniprot_to_gene),
            "decreased": compute_kde_stats(nodes_kde_neg, seeds_in_graph_neg, uniprot_to_gene),
        }

        raise_if_cancelled(submission_root)
   
        # --------------------------------------------------
        # Module detection
        # --------------------------------------------------

        update_progress(
            submission_root,
            status="running",
            step="module_detection",
            message=f"{exp_name}: module detection",
            batch={
                "current_experiment": exp_name,
                "finished_experiments": finished_experiments,
                "total_experiments": total_experiments,
            }
        )

        if all_nodes_pos:

            merge_egos(
                network=network_raw,
                kde_cutoff=cfg.kde_cutoff,
                paths=paths,
                uniprot_to_gene=uniprot_to_gene,
                supernodes=nodes_kde_pos,
                all_nodes=all_nodes_pos,
                direction="increased",
                geneset_path=paths.geneset_path,
                fisher_geneset=cfg.fisher_geneset,
                fisher_threshold=cfg.fisher_threshold,
                damping_module_detection=cfg.damping_module_detection,
                propagation_value=propagation_value,
                runtime_paths=paths_runtime,
            )

        raise_if_cancelled(submission_root)

        if all_nodes_neg:

            merge_egos(
                network=network_raw,
                kde_cutoff=cfg.kde_cutoff,
                paths=paths,
                uniprot_to_gene=uniprot_to_gene,
                supernodes=nodes_kde_neg,
                all_nodes=all_nodes_neg,
                direction="decreased",
                geneset_path=paths.geneset_path,
                fisher_geneset=cfg.fisher_geneset,
                fisher_threshold=cfg.fisher_threshold,
                damping_module_detection=cfg.damping_module_detection,
                propagation_value=propagation_value,
                runtime_paths=paths_runtime,
            )

        raise_if_cancelled(submission_root)

        # -------------------------
        # Generate network objects
        # -------------------------


        net_results = generate_nets(
            paths=paths,
            base_network=network_raw,
            seeds_increase=nodes_kde_pos,
            seeds_decrease=nodes_kde_neg,
            kde_cutoff=cfg.kde_cutoff,
            include_isolated_egos_in_KDE_net=include_isolated_egos_in_KDE_net,
            uniprot_to_gene=uniprot_to_gene,
            propagation_value=propagation_value,
            runtime_paths=paths_runtime,
        )
        results[exp_name] = net_results
        raise_if_cancelled(submission_root)
        # -------------------------
        # Finalize for web: export sigma JSONs
        # -------------------------
        kde_label = _normalize_kde(cfg.kde_cutoff)
        kde_dirname = f"KDE_{kde_label}"
        
        inc_stats = None
        dec_stats = None
        module_overlap_stats = {}
        kde_dir_ref=None
        
        for direction in ["increased", "decreased"]:
            raise_if_cancelled(submission_root)

            direction_dir = Path(run_out_folder) / direction
            if not direction_dir.exists():
                continue
        
            kde_dir = direction_dir / kde_dirname
            if not kde_dir.exists():
                continue
            if kde_dir_ref is None:
                kde_dir_ref = kde_dir
                

            tables_root = kde_dir / "tables"
            export_supernodes_sigma(
                kde_dir=kde_dir,
                tables_root=tables_root,
                direction_dir=direction_dir,
                base_network=network_raw,
                uniprot_to_gene=uniprot_to_gene,
                opentargets_lookup=ot_lookup,
            )
            
        
            export_module_meta_sigma(kde_dir)
        
            modules_len = net_results["modules_len"].get((direction, kde_label), 0)
            export_modules_sigma(
                kde_dir=kde_dir,
                tables_root=tables_root,
                direction_dir=direction_dir,
                base_network=network_raw,
                uniprot_to_gene=uniprot_to_gene,
                modules_len=modules_len,
                opentargets_lookup=ot_lookup,
            )
           
            supernodes_file = kde_dir / "networks" / "supernodes_net.txt"
            modules_root = kde_dir / "modules"
            
            
            update_progress(
                submission_root,
                status="running",
                step="export",
                message=f"{exp_name}: exporting results",
                batch={
                    "current_experiment": exp_name,
                    "finished_experiments": finished_experiments,
                    "total_experiments": total_experiments,
                }
            )

            
            if modules_root.exists():
                module_overlap_stats[direction] = compute_supernode_module_overlap(
                    supernodes_file,
                    modules_root,
                )

            write_enrichment_json(
                kde_dir=kde_dir,
                tables_root=tables_root,   # ✅ NEW
                enrichment_dbs=cfg.fisher_geneset,
            )
        
            write_enrichment_heatmap(
                kde_dir=kde_dir,
                tables_root=tables_root,   # ✅ NEW
                enrichment_dbs=cfg.fisher_geneset,
            )
        
            if direction == "increased":
                inc_stats = write_summary_stats(
                    kde_dir=kde_dir,
                    direction_dir=direction_dir,
                    direction=direction,
                    graph_nodes=set(graph_nodes),
                    pvalues_set=set(pvalues_pos),
                )
            else:
                dec_stats = write_summary_stats(
                    kde_dir=kde_dir,
                    direction_dir=direction_dir,
                    direction=direction,
                    graph_nodes=set(graph_nodes),
                    pvalues_set=set(pvalues_neg),
                )
        if kde_dir_ref is not None:
            write_summary_stats_file(
                kde_dir=run_out_folder,
                inc_stats=inc_stats or {},
                dec_stats=dec_stats or {},
                pvalues_pos=set(pvalues_pos),
                pvalues_neg=set(pvalues_neg),
            )
        else:
            print(f"⚠ No KDE directory found for stats writing in experiment: {exp_name}")
        advanced_stats = {
            "seeds": seed_graph_stats,
            "rwr": rwr_stats,
            "kde": kde_stats,
            "modules": module_overlap_stats,
        }


        write_manifest(
            run_out_folder=Path(run_out_folder),
            submission_uuid=cfg.submission_uuid,
            experiment_name=exp_name,
            propagation_value=propagation_value,
            kde_dirname=kde_dirname,
            seed_nodes=list(seeds_pos) + list(seeds_neg),
            input_parameters=cfg.__dict__,
            pvalues_pos=pvalues_pos,
            pvalues_neg=pvalues_neg,
            advanced_stats=advanced_stats,
        )
        
        build_cross_experiment_analysis(
            submission_uuid_dir=paths_runtime.submission_root,
            propagation=str(propagation_value),
            kde_dirname=kde_dirname,
        )

        raise_if_cancelled(submission_root)
        
        finished_experiments += 1
        
        # experiment-level file
        update_progress(
            run_out_folder,
            status="completed",
            step="done",
            message="Analysis completed successfully",
        )
        
        # submission-level file
        update_progress(
            submission_root,
            status="completed" if finished_experiments == total_experiments else "running",
            step="batch_progress",
            message=f"Finished {exp_name}",
            batch={
                "current_experiment": exp_name,
                "finished_experiments": finished_experiments,
                "total_experiments": total_experiments,
            }
        )
    
    update_progress(
    submission_root,
    status="completed",
    step="done",
    message="All experiments completed",
    batch={
        "finished_experiments": total_experiments,
        "total_experiments": total_experiments,
    }
   )
    
    return results
