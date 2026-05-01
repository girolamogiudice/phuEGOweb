from pathlib import Path
import json
import math
from phuego_standalone.io.fs import iter_visible_dirs

def _parse_fisher_file(path: Path):
    rows = []

    if not path.exists():
        return rows

    with path.open() as f:
        next(f, None)

        for line in f:
            parts = line.rstrip().split("\t")

            if len(parts) < 6:
                continue

            genes = [g for g in parts[5:] if g]

            rows.append({
                "Id": parts[0],
                "Pvalue": float(parts[1]),
                "Proteins in Network": int(parts[2]),
                "Starting Proteins": int(parts[3]),
                "Description": parts[4],
                "Genes": genes
            })

    rows.sort(key=lambda x: x["Pvalue"])
    return rows



def _rows_to_gene_term(rows):

    term_to_data = {}

    for row in rows:
        term = row["Description"]
        genes = row.get("Genes", [])
        pval = max(row.get("Pvalue", 1.0), 1e-300)  # avoid log(0)

        score = -math.log10(pval)

        if term not in term_to_data:
            term_to_data[term] = {
                "genes": set(),
                "score": score
            }

        term_to_data[term]["genes"].update(g for g in genes if g)

        # keep strongest signal
        if score > term_to_data[term]["score"]:
            term_to_data[term]["score"] = score

    result = [
        {
            "term": term,
            "genes": sorted(list(data["genes"])),
            "score": data["score"]
        }
        for term, data in term_to_data.items()
    ]

    result.sort(key=lambda x: -x["score"])

    return result


def write_enrichment_json(kde_dir: Path, tables_root: Path, enrichment_dbs):
    enrichment = {}
    enrichment_gene_term = {}

    # ---------------------------------------------------------
    # Supernodes
    # ---------------------------------------------------------
    enrichment["__supernodes__"] = {}
    enrichment_gene_term["__supernodes__"] = {}

    super_dir = kde_dir / "supernodes" / "enrichment"

    for db in enrichment_dbs:
        file = super_dir / f"{db}fisher.txt"
        rows = _parse_fisher_file(file)

        enrichment["__supernodes__"][db] = rows
        enrichment_gene_term["__supernodes__"][db] = _rows_to_gene_term(rows)

    # ---------------------------------------------------------
    # Modules
    # ---------------------------------------------------------
    modules_dir = kde_dir / "modules"

    if modules_dir.exists():
        module_dirs = sorted(
            [p for p in iter_visible_dirs(modules_dir) if p.name.startswith("module_")],
            key=lambda p: int(p.name.split("_")[1])
        )

        for mod_dir in module_dirs:
            mid = mod_dir.name.split("_")[1]
            key = f"Module {mid}"

            enrichment[key] = {}
            enrichment_gene_term[key] = {}

            enrich_dir = mod_dir / "enrichment"

            for db in enrichment_dbs:
                file = enrich_dir / f"{db}fisher.txt"
                rows = _parse_fisher_file(file)

                enrichment[key][db] = rows
                enrichment_gene_term[key][db] = _rows_to_gene_term(rows)

    # ---------------------------------------------------------
    # Write full enrichment.json
    # ---------------------------------------------------------
    enrichment_payload = {
        "schema_version": "1.0",
        "databases": enrichment_dbs,
        "enrichment": enrichment
    }

    (tables_root / "enrichment.json").write_text(
        json.dumps(enrichment_payload, indent=2)
    )

    # ---------------------------------------------------------
    # Write full enrichment_gene_term.json
    # ---------------------------------------------------------
    gene_term_payload = {
        "schema_version": "1.0",
        "databases": enrichment_dbs,
        "gene_term": enrichment_gene_term
    }

    (tables_root / "enrichment_gene_term.json").write_text(
        json.dumps(gene_term_payload, indent=2)
    )
