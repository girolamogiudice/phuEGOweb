# ------------------------------------------------------------------------------
# Phuego 2.2 Controller
# Manifest-driven architecture
# Lazy module loading
# ------------------------------------------------------------------------------

from pathlib import Path
import json
import uuid as uuidlib
import shutil
import tarfile
import time
import urllib.request

from py4web import action, URL, abort, redirect, response, request
from py4web.utils.form import Form, FormStyleBulma
from pydal.validators import IS_IN_SET
from pydal import Field
import threading
import sys
from .common import T, auth, session, db
from .app_config import (
    configured_network_map,
    configured_network_status,
    default_network_name,
    load_phuego_config,
    save_phuego_config,
    setup_required as phuego_setup_required,
    support_data_folder_for,
)
import traceback

# ------------------------------------------------------------------------------
# Paths
# ------------------------------------------------------------------------------

APP_FOLDER = Path(__file__).parent

if str(APP_FOLDER) not in sys.path:
    sys.path.insert(0, str(APP_FOLDER))

from phuego_standalone.runner.run_submission import run_submission as phuego_run_submission
from phuego_standalone.io.cancel import RunCancelled, clear_cancel, request_cancel

RESULTS_ROOT = APP_FOLDER / "results"
SUPPORT_DATA_ROOT = APP_FOLDER / "support_data"

SETUP_DOWNLOADS = {}
SETUP_DOWNLOADS_LOCK = threading.Lock()

RESNIK_KDE_NETWORK = "IntAct_045_resnik"
KDE_FIXED_OPTIONS = ["0.5", "0.55", "0.6", "0.65", "0.7", "0.75", "0.80", "0.85", "0.9", "0.95"]
KDE_ALL_OPTIONS = ["Optimal", *KDE_FIXED_OPTIONS]

REANALYSIS_OPTIONS = {
    "first_propagation_significance": [0.01, 0.05, 0.1],
    "kde_probability": KDE_ALL_OPTIONS,
    "zscore": [1.04, 1.28, 1.64, 2.33],
    "second_propagation_damping": [0.3, 0.4, 0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95],
    "minimum_ego_nodes": list(range(1, 10)),
    "third_propagation_damping": [0.3, 0.4, 0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95],
    "fisher_significance": [0.01, 0.05, 0.1],
}

# ------------------------------------------------------------------------------
# Utilities
# ------------------------------------------------------------------------------

def write_progress(
    uuid,
    status="running",
    step="",
    message="",
    error_type=None,
    traceback_text=None,
    context=None,
):
    progress_file = RESULTS_ROOT / uuid / "progress.json"
    progress_file.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "status": status,
        "step": step,
        "message": message,
    }

    if error_type is not None:
        payload["error_type"] = error_type

    if traceback_text is not None:
        payload["traceback"] = traceback_text

    if context is not None:
        payload["context"] = context

    progress_file.write_text(json.dumps(payload, indent=2))

def load_json_safe(path: Path, default=None):
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            return default
    return default


def is_hidden_metadata_path(path: Path) -> bool:
    return path.name.startswith("._") or path.name in {".DS_Store"}


def iter_visible_children(path: Path):
    for child in path.iterdir():
        if is_hidden_metadata_path(child):
            continue
        yield child


def experiment_root(uuid, experiment):
    return RESULTS_ROOT / uuid / experiment


def propagation_root(uuid, experiment, prop):
    return RESULTS_ROOT / uuid / experiment / prop


def load_experiment_manifest(uuid, experiment):
    path = experiment_root(uuid, experiment) / "experiment_manifest.json"
    return load_json_safe(path, {})


def load_propagation_manifest(uuid, experiment, prop):
    path = propagation_root(uuid, experiment, prop) / "manifest.json"
    return load_json_safe(path, {})


def get_kde_from_manifest(manifest):
    return manifest.get("run_metadata", {}).get("kde")


def safe_result_path(base: Path, relative_path: str) -> Path:
    base_resolved = base.resolve()
    target = (base / relative_path).resolve()

    if target != base_resolved and base_resolved not in target.parents:
        abort(403)

    return target


@action("results_file/<uuid>/<experiment>/<prop>/<path:path>")
def results_files(uuid, experiment, prop, path):

    base = RESULTS_ROOT / uuid / experiment / prop
    full_path = safe_result_path(base, path)

    if not full_path.is_file():
        abort(404)

    # 🔥 auto content type
    if full_path.suffix == ".json":
        response.headers["Content-Type"] = "application/json"
        return full_path.read_text()

    if full_path.suffix == ".txt":
        response.headers["Content-Type"] = "text/plain"
        return full_path.read_text()

    if full_path.suffix == ".graphml":
        response.headers["Content-Type"] = "application/xml"
        return full_path.read_text()

    return full_path.read_bytes()

import re

def sanitize_experiment_name(name):
    """
    Convert experiment names to safe folder names.
    """
    name = name.strip()
    name = re.sub(r"\s+", "_", name)
    name = re.sub(r"[^A-Za-z0-9_\-]", "", name)
    return name

GENE_MAP_FILE = Path(__file__).parent / "uploads/gene_to_uniprot.tsv"
UNIPROT_GENE_FILE = Path(__file__).parent / "uploads/uniprot_to_gene.tab"


# ---------------------------------------------------------
# Load gene → uniprot mapping
# ---------------------------------------------------------

def load_gene_map():

    gene_to_uniprot = {}

    if not GENE_MAP_FILE.exists():
        return gene_to_uniprot

    with open(GENE_MAP_FILE) as f:

        for line_num, raw in enumerate(f, 1):

            line = raw.strip()

            if not line:
                continue

            parts = line.split("\t")

            if len(parts) < 2:
                # skip malformed lines safely
                continue

            uniprot = parts[0]
            genes = parts[1]

            for g in genes.split(";"):
                gene_to_uniprot[g.upper()] = uniprot

    return gene_to_uniprot


GENE_MAP = load_gene_map()


def load_uniprot_gene_map():
    uniprot_to_gene = {}

    if not UNIPROT_GENE_FILE.exists():
        return uniprot_to_gene

    with open(UNIPROT_GENE_FILE) as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue

            parts = line.split("\t")
            if len(parts) < 2 or parts[0].lower() == "entry":
                continue

            uniprot = parts[0].strip()
            gene = parts[1].strip()
            if uniprot and gene:
                uniprot_to_gene[uniprot.upper()] = gene

    return uniprot_to_gene


UNIPROT_GENE_MAP = load_uniprot_gene_map()


@action("gene_names_json")
def gene_names_json():
    ids = request.query.get("ids", "")
    proteins = [
        item.strip()
        for item in ids.split(",")
        if item.strip()
    ][:1000]

    return {
        "genes": {
            protein: UNIPROT_GENE_MAP.get(protein.upper(), protein)
            for protein in proteins
        }
    }


# ---------------------------------------------------------
# Detect identifier type
# ---------------------------------------------------------

def detect_identifier_type(ids):

    gene_count = 0
    uniprot_count = 0

    for x in ids:

        if x.upper() in GENE_MAP:
            gene_count += 1
        else:
            uniprot_count += 1

    if gene_count > uniprot_count:
        return "gene"

    return "uniprot"


# ---------------------------------------------------------
# Parse experiments
# ---------------------------------------------------------

def parse_experiment_text(text, layer_mode=None):

    experiments = {}
    current_exp = None

    for line_num, raw in enumerate(text.splitlines(), 1):

        raw_line = raw.rstrip("\r\n")
        line = raw_line.strip()

        if not line:
            continue

        # -------------------------
        # Experiment header
        # -------------------------
        if line.startswith(">"):

            exp_header = raw_line[1:].strip()
            exp_name = exp_header.split("\t", 1)[0].strip()

            if not exp_name:
                raise ValueError(f"Line {line_num}: empty experiment name")

            if exp_name in experiments:
                raise ValueError(f"Duplicate experiment name: {exp_name}")

            experiments[exp_name] = []
            current_exp = exp_name
            continue

        if current_exp is None:
            raise ValueError("First line must start with >experiment_name")

        if layer_mode == "custom":
            tab_parts = raw_line.split("\t")
            if (
                len(tab_parts) >= 3
                and not tab_parts[0].strip()
                and not tab_parts[1].strip()
                and tab_parts[2].strip()
            ):
                continue

        parts = line.split()

        # ------------------------------------------------
        # CUSTOM MODE (ID LFC LAYER)
        # ------------------------------------------------
        if layer_mode == "custom":

            if len(parts) != 3:
                raise ValueError(
                    f"Line {line_num}: expected 'ID LFC LAYER'"
                )

            identifier, lfc_str, layer_str = parts

            try:
                lfc = float(lfc_str)
            except:
                raise ValueError(
                    f"Line {line_num}: invalid LFC value"
                )

            try:
                layer = int(layer_str)
            except:
                raise ValueError(
                    f"Line {line_num}: invalid layer value"
                )

            if layer not in [1, 2, 3]:
                raise ValueError(
                    f"Line {line_num}: layer must be 1,2,3"
                )

            experiments[current_exp].append((identifier, lfc, layer))

        # ------------------------------------------------
        # STANDARD MODE (ID LFC)
        # ------------------------------------------------
        else:

            if len(parts) != 2:
                raise ValueError(
                    f"Line {line_num}: expected 'ID LFC'"
                )

            identifier, lfc_str = parts

            try:
                lfc = float(lfc_str)
            except:
                raise ValueError(
                    f"Line {line_num}: invalid LFC value"
                )

            experiments[current_exp].append((identifier, lfc))

    if not experiments:
        raise ValueError("No experiments detected")

    if len(experiments) > 10:
        raise ValueError("Maximum 10 experiments allowed")

    return experiments
    
# ---------------------------------------------------------
# Main validation function
# ---------------------------------------------------------

def validate_input_text(text, layer_mode=None):

    experiments = parse_experiment_text(text, layer_mode)

    # collect identifiers
    ids = []

    for rows in experiments.values():
        ids.extend([r[0] for r in rows])

    id_type = detect_identifier_type(ids)

    if id_type == "gene":

        converted = {}

        for exp, rows in experiments.items():

            new_rows = []

            for row in rows:

                identifier = row[0]
                gene = identifier.upper()

                if gene not in GENE_MAP:
                    raise ValueError(f"Unknown gene: {identifier}")

                uniprot = GENE_MAP[gene]

                if len(row) == 3:
                    new_rows.append((uniprot, row[1], row[2]))
                else:
                    new_rows.append((uniprot, row[1]))

            converted[exp] = new_rows

        experiments = converted

    return experiments
    

def write_submission_files(uuid, experiments, form_vars, layer_mode):

    uuid_root = RESULTS_ROOT / uuid
    uuid_root.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------
    # Batch input file (all experiments)
    # -------------------------------------------------

    batch_input = uuid_root / "input.txt"

    with open(batch_input, "w") as f:

        for exp_name, rows in experiments.items():

            exp_id = sanitize_experiment_name(exp_name)

            f.write(f">{exp_id}\n")

            for row in rows:

                if len(row) == 3:
                    uniprot, lfc, layer = row
                    f.write(f"{uniprot}\t{lfc}\t{layer}\n")

                else:
                    uniprot, lfc = row
                    f.write(f"{uniprot}\t{lfc}\n")

            f.write("\n")
    # -------------------------------------------------
    # Submission-level config
    # -------------------------------------------------

    config = {

        "submission_uuid": uuid,

        "results_root": "results",

        "input_file": "input.txt",

        "support_data_folder": str(
            support_data_folder_for(form_vars["network_type"])
        ),


        "layer_mode": layer_mode,

        "use_existing_rwr": False,

        "damping_seed_propagation": float(form_vars["first_propagation"]),

        "damping_ego_decomposition": float(form_vars["second_propagation_damping"]),

        "damping_module_detection": float(form_vars["third_propagation_damping"]),

        "kde_cutoff": str(form_vars["kde_probability"]).lower(),

        "rwr_threshold": float(
            form_vars.get("first_propagation_significance", 0.05)
        ),

        "minimum_ego_nodes": int(
            form_vars.get("minimum_ego_nodes", 5)
        ),

        "fisher_geneset": ['C','F','P','K','RT','R'],

        "fisher_threshold": float(
            form_vars.get("fisher_significance", 0.05)
        ),

        "fisher_background": "Network",

        "semsim": "gic",

        "zscore_semantic_similarity": float(
            form_vars.get("zscore", 1.645)
        )
    }

    # -------------------------------------------------
    # Submission manifest
    # -------------------------------------------------

    submission_manifest = {
        "submission_uuid": uuid,
        "n_experiments": len(experiments),
        "experiments": [
            sanitize_experiment_name(exp) for exp in experiments
        ],
        "config": config
    }

    manifest_path = uuid_root / "submission_manifest.json"

    manifest_path.write_text(json.dumps(submission_manifest, indent=2))

    # -------------------------------------------------
    # Create empty experiment folders
    # -------------------------------------------------

    for exp_name in experiments:

        exp_id = sanitize_experiment_name(exp_name)

        exp_folder = uuid_root / exp_id

        exp_folder.mkdir(exist_ok=True)


def kde_options_for_network(network_type):
    if str(network_type) == RESNIK_KDE_NETWORK:
        return KDE_ALL_OPTIONS
    return KDE_FIXED_OPTIONS


def default_kde_for_network(network_type):
    return "Optimal" if str(network_type) == RESNIK_KDE_NETWORK else "0.85"


def validate_kde_for_network(form_vars):
    network_type = str(form_vars.get("network_type", ""))
    kde = str(form_vars.get("kde_probability", ""))
    if kde not in set(kde_options_for_network(network_type)):
        raise ValueError(
            "KDE Optimal is currently available only for IntAct_045_resnik. "
            "Please select a fixed KDE probability for the selected network."
        )


def network_label_from_config(config):
    support_path = str(config.get("support_data_folder", ""))
    support_name = Path(support_path).name

    for label, folder in configured_network_map(include_disabled=True).items():
        if folder == support_name:
            return label

    return support_name or "Unknown"


def normalize_support_data_folder(config):
    support_value = str(config.get("support_data_folder", "")).strip()
    support_path = Path(support_value)

    if support_path.is_absolute():
        return str(support_path)

    parts = support_path.parts
    if len(parts) >= 2 and parts[0] == "support_data":
        return str(APP_FOLDER / support_path)

    if support_path.name:
        return str(APP_FOLDER / "support_data" / support_path.name)

    return support_data_folder_for(default_network_name())


def reanalysis_form_values(config):
    kde_value = str(config.get("kde_cutoff", "optimal"))
    if kde_value.lower() == "optimal":
        kde_value = "Optimal"
    else:
        kde_float = float(kde_value)
        kde_value = "0.80" if kde_float == 0.8 else f"{kde_float:.2f}".rstrip("0").rstrip(".")

    return {
        "first_propagation_significance": str(config.get("rwr_threshold", 0.05)),
        "kde_probability": kde_value,
        "zscore": str(config.get("zscore_semantic_similarity", 1.64)),
        "second_propagation_damping": str(config.get("damping_ego_decomposition", 0.85)),
        "minimum_ego_nodes": str(config.get("minimum_ego_nodes", 5)),
        "third_propagation_damping": str(config.get("damping_module_detection", 0.85)),
        "fisher_significance": str(config.get("fisher_threshold", 0.05)),
    }


def parse_reanalysis_config(request_vars, original_config):
    values = {}

    def require_option(field, cast):
        raw = str(request_vars.get(field, "")).strip()
        allowed = REANALYSIS_OPTIONS[field]
        allowed_strings = {str(v) for v in allowed}

        if raw not in allowed_strings:
            raise ValueError(f"Invalid value for {field}: {raw}")

        return cast(raw)

    values["rwr_threshold"] = require_option("first_propagation_significance", float)

    network_type = network_label_from_config(original_config)
    kde = str(request_vars.get("kde_probability", "")).strip()
    if kde not in set(kde_options_for_network(network_type)):
        raise ValueError(f"Invalid value for kde_probability: {kde}")
    values["kde_cutoff"] = kde.lower()

    values["zscore_semantic_similarity"] = require_option("zscore", float)
    values["damping_ego_decomposition"] = require_option("second_propagation_damping", float)
    values["minimum_ego_nodes"] = require_option("minimum_ego_nodes", int)
    values["damping_module_detection"] = require_option("third_propagation_damping", float)
    values["fisher_threshold"] = require_option("fisher_significance", float)

    new_config = dict(original_config)
    new_config.update(values)
    new_config["support_data_folder"] = normalize_support_data_folder(new_config)
    return new_config


def create_reanalysis_submission(source_uuid, new_config):
    source_root = RESULTS_ROOT / source_uuid
    source_manifest = load_json_safe(source_root / "submission_manifest.json", {})

    if not source_manifest:
        raise ValueError("Original submission_manifest.json not found")

    experiments = source_manifest.get("experiments") or []
    if not experiments:
        raise ValueError("Original submission has no experiments")

    new_uuid = str(uuidlib.uuid4())
    new_root = RESULTS_ROOT / new_uuid
    new_root.mkdir(parents=True, exist_ok=True)

    source_input = source_root / source_manifest.get("config", {}).get("input_file", "input.txt")
    if not source_input.exists():
        raise ValueError("Original input.txt not found")

    shutil.copy2(source_input, new_root / "input.txt")

    copied_all_rwr = True
    for exp_name in experiments:
        src_exp = source_root / exp_name
        dst_exp = new_root / exp_name
        dst_exp.mkdir(parents=True, exist_ok=True)

        for filename in ("rwr_scores.txt", "pvalues.txt", "permutation_counts.txt"):
            src_file = src_exp / filename
            if src_file.exists():
                shutil.copy2(src_file, dst_exp / filename)
            else:
                copied_all_rwr = False

    new_config = dict(new_config)
    new_config["submission_uuid"] = new_uuid
    new_config["input_file"] = "input.txt"
    new_config["support_data_folder"] = normalize_support_data_folder(new_config)
    new_config["use_existing_rwr"] = copied_all_rwr
    new_config["fisher_geneset"] = ["C", "F", "P", "K", "RT", "R"]
    new_config["fisher_background"] = "Network"

    new_manifest = {
        "submission_uuid": new_uuid,
        "parent_submission_uuid": source_uuid,
        "reanalysis_of": source_uuid,
        "n_experiments": len(experiments),
        "experiments": experiments,
        "config": new_config,
    }

    (new_root / "submission_manifest.json").write_text(
        json.dumps(new_manifest, indent=2)
    )

    return new_uuid, copied_all_rwr


# ------------------------------------------------------------------------------
# INDEX
# ------------------------------------------------------------------------------

def setup_network_key(name):
    return (
        name.lower()
        .replace(" ", "_")
        .replace("-", "_")
        .replace(".", "_")
    )


def refresh_network_form_options():
    choices = [
        item["name"]
        for item in configured_network_status()
        if item["enabled"] and item["installed"]
    ]
    default = next(
        (
            item["name"]
            for item in configured_network_status()
            if item["enabled"] and item["installed"] and item["default"]
        ),
        choices[0] if choices else default_network_name(),
    )

    for table_name in ("submissions", "scsubmissions", "custom_submissions"):
        network_field = db[table_name].network_type
        network_field.requires = IS_IN_SET(choices or [default])
        network_field.default = default

        kde_field = db[table_name].kde_probability
        kde_field.requires = IS_IN_SET(KDE_ALL_OPTIONS, zero=None)
        kde_field.default = default_kde_for_network(default)


def setup_network_by_key(key):
    for item in configured_network_status():
        if setup_network_key(item["name"]) == key:
            return item
    return None


def setup_download_snapshot():
    with SETUP_DOWNLOADS_LOCK:
        return {
            key: dict(value)
            for key, value in SETUP_DOWNLOADS.items()
        }


def update_setup_download(key, **values):
    with SETUP_DOWNLOADS_LOCK:
        current = SETUP_DOWNLOADS.setdefault(key, {})
        current.update(values)
        current["updated_at"] = time.time()


def activate_network_after_download(network_name):
    config = load_phuego_config()
    networks = config.get("networks", {})

    if network_name not in networks:
        return

    enabled_installed = [
        item for item in configured_network_status()
        if item["enabled"] and item["installed"]
    ]

    networks[network_name]["enabled"] = True
    if not enabled_installed:
        for name, meta in networks.items():
            meta["default"] = name == network_name

    config["networks"] = networks
    save_phuego_config(config)
    refresh_network_form_options()


def safe_extract_tar(tar_path, destination):
    destination = Path(destination).resolve()
    with tarfile.open(tar_path) as archive:
        for member in archive.getmembers():
            if member.issym() or member.islnk():
                raise ValueError(f"Archive links are not allowed: {member.name}")
            target = (destination / member.name).resolve()
            if target != destination and destination not in target.parents:
                raise ValueError(f"Unsafe path in archive: {member.name}")
        archive.extractall(destination)


def download_and_install_network(key):
    item = setup_network_by_key(key)
    if not item:
        update_setup_download(
            key,
            status="failed",
            message="Unknown network.",
            error="Unknown network.",
        )
        return

    url = item.get("zenodo_url")
    if not url:
        update_setup_download(
            key,
            status="failed",
            message="No download URL configured.",
            error="No download URL configured.",
        )
        return

    SUPPORT_DATA_ROOT.mkdir(parents=True, exist_ok=True)
    download_dir = SUPPORT_DATA_ROOT / ".downloads"
    download_dir.mkdir(parents=True, exist_ok=True)
    tar_path = download_dir / f"{item['folder']}.tar"
    partial_path = download_dir / f"{item['folder']}.tar.part"

    try:
        update_setup_download(
            key,
            status="downloading",
            message=f"Downloading {item['name']} from Zenodo...",
            received=0,
            total=None,
            percent=0,
        )

        request_obj = urllib.request.Request(url, headers={"User-Agent": "phuEGOweb setup"})
        with urllib.request.urlopen(request_obj, timeout=60) as response_obj:
            total = response_obj.headers.get("Content-Length")
            total = int(total) if total and total.isdigit() else None
            received = 0

            with open(partial_path, "wb") as out:
                while True:
                    chunk = response_obj.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
                    received += len(chunk)
                    percent = round(received * 100 / total, 1) if total else None
                    update_setup_download(
                        key,
                        status="downloading",
                        message=f"Downloading {item['name']} from Zenodo...",
                        received=received,
                        total=total,
                        percent=percent,
                    )

        partial_path.replace(tar_path)

        update_setup_download(
            key,
            status="extracting",
            message=f"Extracting {item['name']} into support_data...",
        )
        safe_extract_tar(tar_path, SUPPORT_DATA_ROOT)
        tar_path.unlink(missing_ok=True)

        activate_network_after_download(item["name"])
        update_setup_download(
            key,
            status="complete",
            message=f"{item['name']} installed and enabled.",
            percent=100,
        )

    except Exception as e:
        partial_path.unlink(missing_ok=True)
        update_setup_download(
            key,
            status="failed",
            message=f"Download failed for {item['name']}.",
            error=str(e),
        )


def activate_installed_networks(form_data):
    config = load_phuego_config()
    networks = config.get("networks", {})
    status_by_name = {
        item["name"]: item
        for item in configured_network_status()
    }

    selected = set()
    for name in networks:
        if form_data.get(f"network_{setup_network_key(name)}"):
            selected.add(name)

    selected = [
        name
        for name in networks
        if name in selected and status_by_name.get(name, {}).get("installed")
    ]

    if not selected:
        return "No installed network was selected. Download and extract at least one network first.", False

    default_name = form_data.get("default_network")
    if default_name not in selected:
        default_name = selected[0]

    for name, meta in networks.items():
        meta["enabled"] = name in selected
        meta["default"] = name == default_name

    config["networks"] = networks
    save_phuego_config(config)
    refresh_network_form_options()

    return "Network configuration updated.", True


@action("setup/download/<key>", method=["POST"])
def setup_download(key):
    item = setup_network_by_key(key)
    if not item:
        abort(404)

    current = setup_download_snapshot().get(key, {})
    if current.get("status") in {"queued", "downloading", "extracting"}:
        return dict(status=current["status"], message=current.get("message", "Already running."))

    update_setup_download(
        key,
        status="queued",
        message=f"Queued {item['name']} download.",
        received=0,
        total=None,
        percent=0,
    )
    thread = threading.Thread(target=download_and_install_network, args=(key,), daemon=True)
    thread.start()

    return dict(status="queued", message=f"Queued {item['name']} download.")


@action("setup/download_status")
def setup_download_status():
    return dict(downloads=setup_download_snapshot(), networks=configured_network_status())


@action("setup", method=["GET", "POST"])
@action.uses("setup.html", session)
def setup():
    message = None
    error = None

    if request.method == "POST":
        message, ok = activate_installed_networks(request.forms)
        if not ok:
            error = message
            message = None

    network_status = configured_network_status()
    installed_enabled = [
        item for item in network_status
        if item["installed"] and item["enabled"]
    ]

    return dict(
        network_status=network_status,
        installed_enabled=installed_enabled,
        setup_complete=bool(installed_enabled),
        message=message,
        error=error,
        setup_network_key=setup_network_key,
        downloads=setup_download_snapshot(),
    )


@action("index")
@action.uses("index.html", auth, T)
def index():
    if phuego_setup_required():
        return redirect(URL("setup"))

    user = auth.get_user()
    return dict()


# ------------------------------------------------------------------------------
# ABOUT
# ------------------------------------------------------------------------------

@action("about")
@action.uses("about.html", auth, T)
def about():

    user = auth.get_user()

    return dict()


# ------------------------------------------------------------------------------
# RETRIEVE RESULTS
# ------------------------------------------------------------------------------

@action("retrieve", method=["GET", "POST"])
@action.uses("retrieve.html")
def retrieve():

    form = Form(
        [Field("uuid", label="Run UUID")],
        formstyle=FormStyleBulma,
        submit_button="Retrieve results",
    )

    if form.accepted:

        uuid_value = form.vars["uuid"]

        if (RESULTS_ROOT / uuid_value).exists():
            return redirect(URL("retrieve", uuid_value))

        form.errors["uuid"] = "Run not found."

    return dict(
        form=form,
        message="Enter a previous run UUID."
    )


@action("retrieve/<uuid>", method=["GET", "POST"])
@action.uses("retrieve_detail.html", db, session)
def retrieve_detail(uuid):
    uuid_root = RESULTS_ROOT / uuid

    if not uuid_root.exists():
        abort(404)

    manifest = load_json_safe(uuid_root / "submission_manifest.json", {})
    if not manifest:
        abort(404)

    config = manifest.get("config", {})
    form_values = reanalysis_form_values(config)
    options = dict(REANALYSIS_OPTIONS)
    options["kde_probability"] = kde_options_for_network(network_label_from_config(config))
    if form_values["kde_probability"] not in options["kde_probability"]:
        form_values["kde_probability"] = default_kde_for_network(network_label_from_config(config))
    message = "Review the previous submission or launch a reanalysis."
    error = None

    if request.method == "POST":
        try:
            new_config = parse_reanalysis_config(request.forms, config)
            new_uuid, reused_rwr = create_reanalysis_submission(uuid, new_config)

            if reused_rwr:
                message = "Reanalysis submitted using existing RWR and p-values."
            else:
                message = "Reanalysis submitted; RWR will be recomputed because cached files were incomplete."

            launch_submission_runner(new_uuid)
            return redirect(URL("results", new_uuid))

        except Exception as e:
            error = str(e)
            message = f"Reanalysis failed: {e}"
            form_values = {
                **form_values,
                **{k: str(request.forms.get(k)) for k in REANALYSIS_OPTIONS if request.forms.get(k) is not None}
            }

    input_text = ""
    input_file = uuid_root / config.get("input_file", "input.txt")
    if input_file.exists():
        input_text = input_file.read_text()

    return dict(
        uuid=uuid,
        manifest=manifest,
        config=config,
        network_type=network_label_from_config(config),
        experiments=manifest.get("experiments", []),
        input_text=input_text,
        form_values=form_values,
        options=options,
        message=message,
        error=error,
        json=json,
    )


# ------------------------------------------------------------------------------
# phospho PHUEGO SUBMISSION
# ------------------------------------------------------------------------------
@action("submit", method=["GET", "POST"])
@action.uses("submit.html", db, session)
def submit():
    if phuego_setup_required():
        return redirect(URL("setup"))

    refresh_network_form_options()

    form = Form(
        db.submissions,
        dbio=True,
        csrf_session=session,
        formstyle=FormStyleBulma,
    )

    if form.accepted:
        try:
            experiments = validate_input_text(
                form.vars["protein_lfc_text"],
                layer_mode="kinases"
            )
        except Exception as e:
            form.errors["protein_lfc_text"] = str(e)
            return dict(
                form=form,
                message=f"Input validation failed: {e}"
            )

        try:
            validate_kde_for_network(form.vars)
        except ValueError as e:
            form.errors["kde_probability"] = str(e)
            return dict(form=form, message=str(e))

        new_uuid = str(uuidlib.uuid4())

        try:
            write_submission_files(
                new_uuid,
                experiments,
                form.vars,
                layer_mode="kinases"
            )

            db.uuid_mapping.insert(
                form_id=form.vars["id"],
                uuid=new_uuid
            )
            db.commit()

            launch_submission_runner(new_uuid)

        except Exception as e:
            db.rollback()
            write_progress(
                new_uuid,
                "failed",
                "submission_error",
                str(e),
                error_type=type(e).__name__,
            )
            form.errors["protein_lfc_text"] = f"Submission failed: {e}"
            return dict(
                form=form,
                message="Submission failed"
            )
    

        return redirect(URL("results", new_uuid))

    return dict(
        form=form,
        message="Please fill in the parameters below."
    )
    

# ------------------------------------------------------------------------------
# SC PHUEGO SUBMIT
# ------------------------------------------------------------------------------

@action("sc_phuego_submit", method=["GET", "POST"])
@action.uses("sc_phuego_submit.html", db, session)
def sc_submit():
    if phuego_setup_required():
        return redirect(URL("setup"))

    refresh_network_form_options()

    form = Form(
        db.scsubmissions,
        dbio=True,
        csrf_session=session,
        formstyle=FormStyleBulma,
    )

    if form.accepted:
        try:
            experiments = validate_input_text(
                form.vars["lfc_text"],
                layer_mode="tf_rc"
            )
        except Exception as e:
            form.errors["lfc_text"] = str(e)
            return dict(
                form=form,
                message="Input validation failed"
            )

        try:
            validate_kde_for_network(form.vars)
        except ValueError as e:
            form.errors["kde_probability"] = str(e)
            return dict(form=form, message=str(e))

        new_uuid = str(uuidlib.uuid4())

        try:
            write_submission_files(
                new_uuid,
                experiments,
                form.vars,
                layer_mode="tf_rc"
            )

            db.uuid_mapping.insert(
                form_id=form.vars["id"],
                uuid=new_uuid
            )
            db.commit()

            launch_submission_runner(new_uuid)

        except Exception as e:
            db.rollback()
            write_progress(
                new_uuid,
                "failed",
                "submission_error",
                str(e),
                error_type=type(e).__name__,
            )
            form.errors["lfc_text"] = f"Submission failed: {e}"
            return dict(
                form=form,
                message="Submission failed"
            )

        return redirect(URL("results", new_uuid))

    return dict(
        form=form,
        message="Please fill in the parameters below."
    )
    

# ------------------------------------------------------------------------------
# CUSTOM PHUEGO SUBMIT
# ------------------------------------------------------------------------------

@action("custom_phuego_submit", method=["GET", "POST"])
@action.uses("custom_phuego_submit.html", db, session)
def custom_submit():
    if phuego_setup_required():
        return redirect(URL("setup"))

    refresh_network_form_options()

    form = Form(
        db.custom_submissions,
        dbio=True,
        csrf_session=session,
        formstyle=FormStyleBulma,
    )

    if form.accepted:
        try:
            experiments = validate_input_text(
                form.vars["protein_lfc_text"],
                layer_mode="custom"
            )
        except Exception as e:
            form.errors["protein_lfc_text"] = str(e)
            return dict(
                form=form,
                message="Input validation failed"
            )

        try:
            validate_kde_for_network(form.vars)
        except ValueError as e:
            form.errors["kde_probability"] = str(e)
            return dict(form=form, message=str(e))

        new_uuid = str(uuidlib.uuid4())

        try:
            write_submission_files(
                new_uuid,
                experiments,
                form.vars,
                layer_mode="custom"
            )

            db.uuid_mapping.insert(
                form_id=form.vars["id"],
                uuid=new_uuid
            )
            db.commit()

            launch_submission_runner(new_uuid)

        except Exception as e:
            db.rollback()
            write_progress(
                new_uuid,
                "failed",
                "submission_error",
                str(e),
                error_type=type(e).__name__,
            )
            form.errors["protein_lfc_text"] = f"Submission failed: {e}"
            return dict(
                form=form,
                message="Submission failed"
            )

        return redirect(URL("results", new_uuid))

    return dict(
        form=form,
        message="Please fill in the parameters below."
    )
    

def launch_submission_runner(uuid):

    manifest_path = RESULTS_ROOT / uuid / "submission_manifest.json"
    clear_cancel(RESULTS_ROOT / uuid)

    def runner():
        try:
            write_progress(
                uuid,
                "running",
                "queued",
                "Job started",
                context={"manifest_path": str(manifest_path)}
            )

            phuego_run_submission(str(manifest_path))

            write_progress(uuid, "completed", "finished", "Analysis completed") 

        except RunCancelled as e:
            write_progress(
                uuid,
                "cancelled",
                "cancelled",
                str(e),
                error_type=type(e).__name__,
                context={"manifest_path": str(manifest_path)}
            )

        except Exception as e:
            write_progress(
                uuid,
                "failed",
                "error",
                str(e),
                error_type=type(e).__name__,
                traceback_text=traceback.format_exc(),
                context={"manifest_path": str(manifest_path)}
            )
    
    thread = threading.Thread(target=runner, daemon=True)
    
    thread.start()


@action("cancel_run/<uuid>", method=["POST"])
@action.uses(session, db)
def cancel_run(uuid):
    uuid_root = RESULTS_ROOT / uuid

    if not uuid_root.exists():
        abort(404)

    request_cancel(uuid_root)
    write_progress(
        uuid,
        "cancelled",
        "cancel_requested",
        "Cancellation requested. The analysis will stop at the next safe checkpoint.",
    )

    return dict(
        status="cancelled",
        message="Cancellation requested"
    )
    

# ------------------------------------------------------------------------------
# RESULTS ENTRY PAGE
# ------------------------------------------------------------------------------
@action("results/<uuid>")
@action.uses("results.html", session, db)
def results(uuid):

    uuid_root = RESULTS_ROOT / uuid

    if not uuid_root.exists():
        abort(404)

    # First choice: standalone already wrote experiment manifests
    experiments = []
    for d in iter_visible_children(uuid_root):
        try:
            if d.is_dir() and (d / "experiment_manifest.json").exists():
                experiments.append(d.name)
        except PermissionError:
            continue

    # Fallback: use submission_manifest.json immediately after submission
    if not experiments:
        submission_manifest = load_json_safe(uuid_root / "submission_manifest.json", {})
        experiments = submission_manifest.get("experiments", [])

    return dict(
        uuid=uuid,
        experiments=sorted(experiments),
        json=json
    )
# ------------------------------------------------------------------------------
# RESULTS METADATA
# ------------------------------------------------------------------------------

@action("results_json/<uuid>/<experiment>")
@action.uses(session, db)
def results_json(uuid, experiment):

    exp_manifest = load_experiment_manifest(uuid, experiment)

    if not exp_manifest:
        return dict(
            pending=True,
            manifest={},
            run_metadata=None,
            network_summary=None,
            directions={},
            propagation=None,
        )

    propagation = exp_manifest.get("default_propagation")
    manifest = load_propagation_manifest(uuid, experiment, propagation)

    if not manifest:
        return dict(
            pending=True,
            manifest={},
            run_metadata=exp_manifest.get("run_metadata"),
            network_summary=None,
            directions={},
            propagation=propagation,
        )

    return dict(
        pending=False,
        manifest=manifest,
        run_metadata=manifest.get("run_metadata"),
        network_summary=manifest.get("network_summary"),
        directions=manifest.get("directions"),
        propagation=propagation,
    )
# ------------------------------------------------------------------------------
# STATUS
# ------------------------------------------------------------------------------

@action("status_json/<uuid>")
@action.uses()


def status_json(uuid):

    import json
    from pathlib import Path

  


    progress_file = RESULTS_ROOT / uuid / "progress.json"
    
    # --------------------------------------------------
    # No file yet → submitted
    # --------------------------------------------------
    if not progress_file.exists():
        return dict(status="submitted")

    # --------------------------------------------------
    # Try reading JSON safely
    # --------------------------------------------------
    try:
        text = progress_file.read_text()

        # handle partially written file
        if not text.strip():
            return dict(status="running", message="Initializing...")

        data = json.loads(text)

        # ensure minimal fields always exist
        data.setdefault("status", "running")
        data.setdefault("step", "")
        data.setdefault("message", "")

        return data

    except json.JSONDecodeError:
        # file being written → retry next poll
        return dict(status="running", message="Updating progress...")

    except Exception as e:
        return dict(status="running", message=f"Error reading progress: {e}")
        

# ------------------------------------------------------------------------------
# NETWORK ENDPOINTS
# ------------------------------------------------------------------------------

@action("network_supernodes/<uuid>/<experiment>/<prop>/<direction>")
def network_supernodes(uuid, experiment, prop, direction):

    manifest = load_propagation_manifest(uuid, experiment, prop)

    kde = get_kde_from_manifest(manifest)

    path = propagation_root(uuid, experiment, prop) / direction / kde / "networks" / "supernodes_sigma.json"

    return load_json_safe(path, {"nodes": [], "edges": []})


@action("network_module_meta/<uuid>/<experiment>/<prop>/<direction>")
def network_module_meta(uuid, experiment, prop, direction):

    manifest = load_propagation_manifest(uuid, experiment, prop)

    kde = get_kde_from_manifest(manifest)

    path = propagation_root(uuid, experiment, prop) / direction / kde / "networks" / "module_meta_sigma.json"

    return load_json_safe(path, {"nodes": [], "edges": []})


@action("network_module/<uuid>/<experiment>/<prop>/<direction>/<module_id>")
def network_module(uuid, experiment, prop, direction, module_id):

    manifest = load_propagation_manifest(uuid, experiment, prop)

    kde = get_kde_from_manifest(manifest)

    path = (
        propagation_root(uuid, experiment, prop)
        / direction
        / kde
        / "networks"
        / "modules_sigma"
        / f"module_{module_id}.json"
    )

    return load_json_safe(path, {"nodes": [], "edges": []})

# ------------------------------------------------------------------------------
# CROSS EXPERIMENT NETWORKS
# ------------------------------------------------------------------------------

@action("cross_json/<uuid>/<prop>")
def cross_json(uuid, prop):

    uuid_root = RESULTS_ROOT / uuid

    cross_root = uuid_root / prop / "cross_experiment"

    if not cross_root.exists():
        return dict(exists=False)

    data = {
        "exists": True,
        "increased": {},
        "decreased": {}
    }

    for direction in ["increased", "decreased"]:

        dir_path = cross_root / direction

        data[direction] = {
            "kde_overlap": load_json_safe(dir_path / "kde_overlap_network.json"),
            "module_similarity": load_json_safe(dir_path / "module_similarity_network.json"),
            "module_matrix": load_json_safe(dir_path / "module_similarity_matrix.json")
        }

    return data
    
# ------------------------------------------------------------------------------
# SUPER NODES (frontend compatible route)
# ------------------------------------------------------------------------------

@action("results/<uuid>/<experiment>/<prop>/<direction>/supernodes")
def results_supernodes(uuid, experiment, prop, direction):

    manifest = load_propagation_manifest(uuid, experiment, prop)
    kde = manifest["run_metadata"]["kde"]

    path = (
        RESULTS_ROOT
        / uuid
        / experiment
        / prop
        / direction
        / kde
        / "networks"
        / "supernodes_sigma.json"
    )

    data = load_json_safe(path, {})

    return {
        "nodes": data.get("nodes", []),
        "edges": data.get("edges", [])
    }
    
# ------------------------------------------------------------------------------
# MODULE META NETWORK
# ------------------------------------------------------------------------------

@action("results/<uuid>/<experiment>/<prop>/<direction>/module_meta")
def results_module_meta(uuid, experiment, prop, direction):

    manifest = load_propagation_manifest(uuid, experiment, prop)

    kde = manifest["run_metadata"]["kde"]

    path = (
        RESULTS_ROOT
        / uuid
        / experiment
        / prop
        / direction
        / kde
        / "networks"
        / "module_meta_sigma.json"
    )

    return load_json_safe(path, {"nodes": [], "edges": []})
    
# ------------------------------------------------------------------------------
# MODULE NETWORK
# ------------------------------------------------------------------------------

@action("results/<uuid>/<experiment>/<prop>/<direction>/module/<module_id>")
def results_module(uuid, experiment, prop, direction, module_id):

    manifest = load_propagation_manifest(uuid, experiment, prop)

    kde = manifest["run_metadata"]["kde"]

    path = (
        RESULTS_ROOT
        / uuid
        / experiment
        / prop
        / direction
        / kde
        / "networks"
        / "modules_sigma"
        / f"module_{module_id}.json"
    )

    return load_json_safe(path, {"nodes": [], "edges": []})

# ------------------------------------------------------------------------------
# ENRICHMENT
# ------------------------------------------------------------------------------

@action("enrichment/<uuid>/<experiment>/<prop>/<direction>")
def enrichment(uuid, experiment, prop, direction):

    manifest = load_propagation_manifest(uuid, experiment, prop)

    kde = get_kde_from_manifest(manifest)

    path = propagation_root(uuid, experiment, prop) / direction / kde / "tables/enrichment.json"

    return load_json_safe(path, {})


# ------------------------------------------------------------------------------
# HEATMAP
# ------------------------------------------------------------------------------

@action("module_heatmap/<uuid>/<experiment>/<prop>/<direction>")
def module_heatmap_json(uuid, experiment, prop, direction):

    manifest = load_propagation_manifest(uuid, experiment, prop)
    kde = get_kde_from_manifest(manifest)

    path = propagation_root(uuid, experiment, prop) / direction / kde / "tables/enrichment_heatmap.json"
    return load_json_safe(path, {})


# ------------------------------------------------------------------------------
# FILE DOWNLOAD (TXT)
# ------------------------------------------------------------------------------

@action("download/<uuid>/<experiment>/<prop>/<path:path>")
def download(uuid, experiment, prop, path):

    base = propagation_root(uuid, experiment, prop)
    file_path = safe_result_path(base, path)

    if not file_path.is_file():
        abort(404)

    response.headers["Content-Type"] = "text/plain"
    response.headers["Content-Disposition"] = f'attachment; filename="{file_path.name}"'

    return file_path.read_text()


@action("download/supernodes/<uuid>/<experiment>/<prop>/<direction>/<fmt>")
def download_supernodes(uuid, experiment, prop, direction, fmt):

    manifest = load_propagation_manifest(uuid, experiment, prop)
    kde = get_kde_from_manifest(manifest)

    base = (
        RESULTS_ROOT
        / uuid
        / experiment
        / prop
        / direction
        / kde
        / "networks"
    )

    if fmt == "graphml":
        path = base / "supernodes_sigma.graphml"

    elif fmt == "json":
        path = base / "supernodes_sigma.json"

    else:
        abort(400)

    if not path.exists():
        abort(404)

    if fmt == "graphml":
        content_type = "application/xml"
    else:
        content_type = "application/json"

    response.headers["Content-Type"] = content_type
    response.headers["Content-Disposition"] = f'attachment; filename="{path.name}"'

    return path.read_bytes()
    

@action("download/module/<uuid>/<experiment>/<prop>/<direction>/<module>/<fmt>")
def download_module(uuid, experiment, prop, direction, module, fmt):
    manifest = load_propagation_manifest(uuid, experiment, prop)
    kde = get_kde_from_manifest(manifest)
    base = (
        RESULTS_ROOT
        / uuid
        / experiment
        / prop
        / direction
        / kde
        / "networks"
        / "modules_sigma"
    )

    if fmt == "graphml":
        path = base / f"module_{module}.graphml"

    elif fmt == "json":
        path = base / f"module_{module}.json"

    else:
        abort(400)

    if not path.exists():
        abort(404)

    if fmt == "graphml":
        content_type = "application/xml"
    else:
        content_type = "application/json"

    response.headers["Content-Type"] = content_type
    response.headers["Content-Disposition"] = f'attachment; filename="{path.name}"'

    return path.read_bytes()
    
   
