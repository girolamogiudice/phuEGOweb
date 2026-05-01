# phuEGOweb Docker beta

This repository contains the phuEGOweb code and Docker files needed to build or run the phuEGOweb beta interface.

phuEGOweb runs the phuEGO pipeline from a local Docker container and stores large support-data networks, results, databases, and uploads outside the image. The first setup screen can download the selected support-data network from Zenodo.

## Quick Start

### Option A: use the prebuilt image from Zenodo

Download the Docker image tar from Zenodo and place it in the repository root as `phuegoweb-local.tar`, then run:

```bash
docker load -i phuegoweb-local.tar
docker compose up
```

Open:

```text
http://127.0.0.1:8000/phuEGOweb/setup
```

On the setup page, install at least one network from Zenodo, choose which installed networks should appear in the phuEGOweb form, then open phuEGOweb.

### Option B: build the image locally

From the phuEGOweb repository root:

```bash
docker compose build
docker compose up
```

Then open:

```text
http://127.0.0.1:8000/phuEGOweb/setup
```

## Folder Layout

The Docker compose file uses relative host paths:

```text
./support_data        -> /opt/py4web/apps/phuEGOweb/support_data
./results             -> /opt/py4web/apps/phuEGOweb/results
./databases           -> /opt/py4web/apps/phuEGOweb/databases
./uploads             -> /opt/py4web/apps/phuEGOweb/uploads
./phuego_config.yaml  -> /opt/py4web/apps/phuEGOweb/phuego_config.yaml
```

This means the folder can be placed anywhere on the user's computer. Docker resolves `./support_data`, `./results`, and the other paths relative to the `docker-compose.yml` file.

For the source repository, use the root `docker-compose.yml`. The additional `docker/docker-compose.tester.yml` is a portable launcher for a minimal runtime folder containing only the compose file, `phuego_config.yaml`, runtime folders, and a prebuilt image tar.

## Support Data

Support-data networks are hosted on Zenodo. The setup page downloads and extracts the selected network automatically into the mounted `support_data` folder.

```text
https://zenodo.org/records/19926624
```

The Docker image can also be hosted on Zenodo as a separate file. GitHub should contain the code and documentation; large binaries should stay on Zenodo.

## Notes

This is a beta/local workstation distribution. It is suitable for testing, demonstrations, and paper-resource review. It is not yet hardened as a public multi-user web service.
