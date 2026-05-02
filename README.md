# phuEGOweb

phuEGOweb is a local py4web interface for running the phuEGO pipeline and visualising propagation, supernode, module, enrichment, and cross-experiment outputs.

This repository is intended for source code and Docker build/run documentation. Large support-data networks and prebuilt Docker image files are distributed separately through Zenodo.

## Docker Quick Start

The easiest testing workflow is to use the prebuilt Docker bundle from Zenodo, then let the setup page download the support-data networks.

Download:

```text
https://zenodo.org/records/19926624/files/phuEGOweb.tar?download=1
```

Then run:

```bash
tar -xf phuEGOweb.tar
cd phuEGOweb-docker
docker load -i phuegoweb-local.tar
docker compose up
```

Important: `phuEGOweb.tar` is a bundle. Do not run `docker load -i phuEGOweb.tar`. The Docker image inside the bundle is `phuegoweb-local.tar`.

Open:

```text
http://127.0.0.1:8000/phuEGOweb/setup
```

Install at least one network, save the installed network selection, then open phuEGOweb.

## Build Locally

From this repository root:

```bash
docker compose build
docker compose up
```

Then open:

```text
http://127.0.0.1:8000/phuEGOweb/setup
```

## Support Data

Support-data networks are hosted on Zenodo:

```text
https://zenodo.org/records/19926624
```

The setup page downloads and extracts networks into the mounted `support_data` folder.

The same Zenodo record also contains the prebuilt Docker bundle.

## Runtime Folders

Docker mounts these local folders into the container:

```text
support_data
results
databases
uploads
phuego_config.yaml
```

These folders are runtime data and should not be committed to GitHub.

## Status

This is a beta/local workstation distribution suitable for testing, demonstrations, and paper-resource review. It is not yet hardened as a public multi-user web service.

## License

This project is released under the MIT License. See `LICENSE`.
