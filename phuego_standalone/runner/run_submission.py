import json
from pathlib import Path

from phuego_standalone.core import phuego

def run_submission(manifest_path):

    manifest_path = Path(manifest_path)
    
    submission_root = manifest_path.parent

    manifest = json.loads(manifest_path.read_text())
    submission_uuid = manifest["submission_uuid"]
    config = manifest["config"]

    phuego(
        submission_uuid=submission_uuid,
        support_data_folder=config["support_data_folder"],
        res_folder=str(submission_root.parent),
        input_file=str(submission_root / config["input_file"]),
        fisher_geneset=config["fisher_geneset"],
        fisher_threshold=config["fisher_threshold"],
        fisher_background=config["fisher_background"],
        ini_pos=[],
        ini_neg=[],
        damping_seed_propagation=config["damping_seed_propagation"],
        damping_ego_decomposition=config["damping_ego_decomposition"],
        damping_module_detection=config["damping_module_detection"],
        kde_cutoff=config["kde_cutoff"],
        rwr_threshold=config["rwr_threshold"],
        minimum_ego_nodes=config.get("minimum_ego_nodes", 5),
        zscore_semantic_similarity=config.get("zscore_semantic_similarity", 1.64),
        semsim=config["semsim"],
        layer_mode=config["layer_mode"],
        use_existing_rwr=config["use_existing_rwr"],
    )


if __name__ == "__main__":

    import sys

    run_submission(sys.argv[1])
