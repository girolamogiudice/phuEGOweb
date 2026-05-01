import json
from pathlib import Path
from phuego_standalone.io.fs import iter_visible_dirs


def parse_enrichment_table(path: Path):
    rows = []
    if not path.exists():
        return rows

    with path.open() as f:
        next(f, None)
        for line in f:
            cols = line.rstrip().split("\t")
            if len(cols) < 6:
                continue
            rows.append({
                "Description": cols[4]
            })
    return rows

def write_enrichment_heatmap(    
    kde_dir: Path,
    tables_root,
    enrichment_dbs: list[str],):
		
    modules_dir = kde_dir / "modules"
    if not modules_dir.exists():
        return

    heatmap = {}

    for module_path in iter_visible_dirs(modules_dir):
        if not module_path.name.startswith("module_"):
            continue

        module_id = module_path.name.replace("module_", "Module ")

        fisher_dir = module_path / "enrichment"
        if not fisher_dir.exists():
            continue

        for db in enrichment_dbs:
            db_file = fisher_dir / f"{db}fisher.txt"
            rows = parse_enrichment_table(db_file)
            if not rows:
                continue

            heatmap.setdefault(db, {})

            for r in rows:
                desc = r["Description"]
                heatmap[db].setdefault(desc, set()).add(module_id)

    # convert sets → sorted lists + counts
    output = {
        "schema_version": "1.0",
        "databases": {}
    }

    for db, terms in heatmap.items():
        output["databases"][db] = {
            "terms": [
                {
                    "description": desc,
                    "module_count": len(mods),
                    "modules": sorted(mods),
                }
                for desc, mods in sorted(
                    terms.items(),
                    key=lambda x: (-len(x[1]), x[0])
                )
            ]
        }

    out_path = tables_root / "enrichment_heatmap.json"
    out_path.write_text(json.dumps(output, indent=2))
