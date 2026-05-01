import json
from pathlib import Path
from .cross_helpers import build_kde_overlap, build_module_similarity

def build_cross_experiment_analysis(
    submission_uuid_dir: Path,
    propagation: str,
    kde_dirname: str,
):
    out_root = submission_uuid_dir / propagation / "cross_experiment"
    for direction in ["increased", "decreased"]:

        kde_net = build_kde_overlap(
            submission_uuid_dir,
            propagation,
            direction,
            kde_dirname
        )

        mod_net, mod_matrix = build_module_similarity(
            submission_uuid_dir,
            propagation,
            direction,
            kde_dirname
        )

        dir_out = out_root / direction
        dir_out.mkdir(parents=True, exist_ok=True)

        if not kde_net and not mod_net:
            continue



        if kde_net:
            (dir_out / "kde_overlap_network.json").write_text(
                json.dumps(kde_net, indent=2)
            )

        if mod_net:
            (dir_out / "module_similarity_network.json").write_text(
                json.dumps(mod_net, indent=2)
            )

        if mod_matrix:
            (dir_out / "module_similarity_matrix.json").write_text(
                json.dumps(mod_matrix, indent=2)
            )
