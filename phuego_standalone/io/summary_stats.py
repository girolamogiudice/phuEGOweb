import json
from pathlib import Path
from phuego_standalone.io.fs import iter_visible_dirs


def _read_seed_nodes(direction_dir: Path) -> set[str]:
    f = direction_dir / "seed_nodes.txt"
    if not f.exists():
        return set()
    return {line.strip() for line in f.open() if line.strip()}


def _read_module_members(modules_dir: Path) -> dict[str, set[str]]:
    """
    modules/module_0/module_egos.txt etc.
    Returns dict: "Module 0" -> set(proteins)
    """
    out = {}
    if not modules_dir.exists():
        return out

    for mdir in sorted([p for p in iter_visible_dirs(modules_dir) if p.name.startswith("module_")]):
        module_id = mdir.name.replace("module_", "Module ")
        ego_file = mdir / "module_egos.txt"
        if not ego_file.exists():
            continue

        members = set()
        with ego_file.open() as f:
            for line in f:
                parts = [x for x in line.strip().split("\t") if x]
                members.update(parts)

        out[module_id] = members

    return out


def write_summary_stats(
    *,
    kde_dir: Path,
    direction_dir: Path,
    direction: str,               # "increased" or "decreased"
    graph_nodes: set[str],
    pvalues_set: set[str],        # pvalues_pos or pvalues_neg (already unique-resolved)
) -> dict:
    """
    Returns a dict (direction stats). Caller merges increased+decreased+overlap and writes JSON.
    """
    seeds = _read_seed_nodes(direction_dir)

    seeds_in_network = seeds & graph_nodes
    seeds_missing = sorted(seeds - graph_nodes)

    modules_dir = kde_dir / "modules"
    module_members = _read_module_members(modules_dir)

    module_details = []
    for mid, members in module_members.items():
        n_nodes = len(members & graph_nodes)  # membership present in network
        n_seeds = len((members & graph_nodes) & seeds)
        module_details.append({
            "module_id": mid,
            "n_nodes": int(n_nodes),
            "n_seeds": int(n_seeds),
        })

    module_details.sort(key=lambda x: (-x["n_nodes"], x["module_id"]))

    return {
        "direction": direction,
        "seed_total": int(len(seeds)),
        "seed_in_network": int(len(seeds_in_network)),
        "seed_missing_from_network": {
            "count": int(len(seeds_missing)),
            "items": seeds_missing,  # keep lightweight; if too big later we can cap to first N
        },
        "rwr_pass_threshold": int(len(pvalues_set)),
        "rwr_pass_threshold_seeds": int(len(pvalues_set & seeds)),
        "modules": {
            "count": int(len(module_members)),
            "module_details": module_details,  # counts only, as requested
        },
    }


def write_summary_stats_file(
    *,
    kde_dir: Path,
    inc_stats: dict,
    dec_stats: dict,
    pvalues_pos: set[str],
    pvalues_neg: set[str],
) -> None:
    overlap = pvalues_pos & pvalues_neg

    payload = {
        "schema_version": "1.0",
        "increased": inc_stats,
        "decreased": dec_stats,
        "rwr_overlap": {
            "pvalues_pos": int(len(pvalues_pos)),
            "pvalues_neg": int(len(pvalues_neg)),
            "intersection": int(len(overlap)),
        },
    }
   
    out = kde_dir / "stats" / "summary_stats.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2))
