from pathlib import Path

import yaml


APP_FOLDER = Path(__file__).parent
CONFIG_FILE = APP_FOLDER / "phuego_config.yaml"

FALLBACK_NETWORKS = {
    "IntAct phuEGO": {
        "folder": "support_data_phuego",
        "enabled": True,
        "default": True,
        "zenodo_url": "https://zenodo.org/records/19926624/files/support_data_phuego.tar?download=1",
    },
    "String700": {
        "folder": "support_data_string700",
        "enabled": True,
        "zenodo_url": "https://zenodo.org/records/19926624/files/support_data_string700.tar?download=1",
    },
    "IntAct_045_resnik": {
        "folder": "support_data_intact_045_resnik",
        "enabled": False,
        "zenodo_url": "https://zenodo.org/records/19926624/files/support_data_intact_045_resnik.tar?download=1",
    },
}

NETWORK_ZENODO_URLS = {
    "IntAct phuEGO": "https://zenodo.org/records/19926624/files/support_data_phuego.tar?download=1",
    "String700": "https://zenodo.org/records/19926624/files/support_data_string700.tar?download=1",
    "String900": "https://zenodo.org/records/19926624/files/support_data_string900.tar?download=1",
    "IntAct": "https://zenodo.org/records/19926624/files/support_data_intact.tar?download=1",
    "IntAct_045": "https://zenodo.org/records/19926624/files/support_data_intact_045.tar?download=1",
    "IntAct_045_resnik": "https://zenodo.org/records/19926624/files/support_data_intact_045_resnik.tar?download=1",
}


def load_phuego_config():
    if not CONFIG_FILE.exists():
        return {"networks": FALLBACK_NETWORKS}

    with open(CONFIG_FILE) as f:
        config = yaml.safe_load(f) or {}

    if not isinstance(config.get("networks"), dict):
        config["networks"] = FALLBACK_NETWORKS

    return config


def save_phuego_config(config):
    CONFIG_FILE.write_text(yaml.safe_dump(config, sort_keys=False))


def network_zenodo_url(name, meta=None):
    meta = meta or {}
    return meta.get("zenodo_url") or NETWORK_ZENODO_URLS.get(name, "")


def configured_networks(include_disabled=False):
    networks = load_phuego_config().get("networks", {})

    if include_disabled:
        return networks

    enabled = {
        name: meta
        for name, meta in networks.items()
        if meta.get("enabled", True)
        and support_data_path_for_folder(meta.get("folder", "")).exists()
    }

    return enabled or FALLBACK_NETWORKS


def available_network_names():
    return list(configured_networks().keys())


def configured_network_map(include_disabled=False):
    return {
        name: str(meta.get("folder", "")).strip()
        for name, meta in configured_networks(include_disabled=include_disabled).items()
        if str(meta.get("folder", "")).strip()
    }


def default_network_name():
    networks = configured_networks()

    for name, meta in networks.items():
        if meta.get("default"):
            return name

    return next(iter(networks), "IntAct phuEGO")


def support_data_folder_for(network_name):
    folder = configured_network_map(include_disabled=True).get(network_name)
    if not folder:
        folder = configured_network_map().get(default_network_name(), "support_data_phuego")

    return str(support_data_path_for_folder(folder))


def support_data_path_for_folder(folder):
    path = Path(folder)
    if path.is_absolute():
        return path

    if path.parts and path.parts[0] == "support_data":
        return APP_FOLDER / path

    return APP_FOLDER / "support_data" / path


def network_installed(network_name, meta=None):
    path = Path(support_data_folder_for(network_name))
    return path.exists() and path.is_dir()


def configured_network_status():
    networks = load_phuego_config().get("networks", {})
    status = []

    for name, meta in networks.items():
        folder = str(meta.get("folder", "")).strip()
        support_path = Path(support_data_folder_for(name))
        status.append({
            "name": name,
            "folder": folder,
            "enabled": bool(meta.get("enabled", True)),
            "default": bool(meta.get("default", False)),
            "installed": support_path.exists() and support_path.is_dir(),
            "path": str(support_path),
            "zenodo_url": network_zenodo_url(name, meta),
        })

    return status


def setup_required():
    return not any(
        item["enabled"] and item["installed"]
        for item in configured_network_status()
    )
