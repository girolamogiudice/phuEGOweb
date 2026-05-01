# phuEGOweb Local Docker

This Docker setup is intended for a single laptop or workstation. The image contains the py4web code, phuEGOweb, and Python dependencies. Large runtime folders stay outside the image and are mounted from the host.

## Folder Mounts

The compose file mounts folders that sit next to `docker-compose.yml` into the container. Because the paths start with `./`, users can put the tester package anywhere and Docker will resolve the folders from that location.

```text
./support_data        -> /opt/py4web/apps/phuEGOweb/support_data
./results             -> /opt/py4web/apps/phuEGOweb/results
./databases           -> /opt/py4web/apps/phuEGOweb/databases
./uploads             -> /opt/py4web/apps/phuEGOweb/uploads
./phuego_config.yaml  -> /opt/py4web/apps/phuEGOweb/phuego_config.yaml
```

This means the Docker image stays small and users can install only the support-data network bundles they need. Inside the app, downloads always write to `/opt/py4web/apps/phuEGOweb/support_data`, which Docker maps to the user's host `support_data` folder.

## Network Selection

Edit:

```text
phuego_config.yaml
```

Example:

```yaml
networks:
  IntAct phuEGO:
    folder: support_data_phuego
    enabled: true
    default: true

  String700:
    folder: support_data_string700
    enabled: true
```

Only enabled networks appear in the submission forms. You can edit this file directly or use the phuEGOweb Setup page.

## Install Support Data

Each support-data tar contains one network folder plus the small shared files required at the root of `support_data`.

The easiest path is to open:

```text
http://127.0.0.1:8000/phuEGOweb/setup
```

Then click "Install from Zenodo" for the networks you want. phuEGOweb downloads each tar into the mounted `support_data` folder, extracts it, removes the downloaded tar after extraction, and updates `phuego_config.yaml`.

Manual extraction is still possible.

Extract only the networks you want, for example:

```bash
cd phuEGOweb-docker
tar -xf support_data_string700.tar -C support_data
tar -xf support_data_phuego.tar -C support_data
```

Make sure `phuego_config.yaml` enables only the networks you extracted, or open `/phuEGOweb/setup` and click "Save Installed Networks" after extraction.

## Build and Run

From the folder that contains `docker-compose.yml`:

```bash
cd phuEGOweb-docker
docker load -i phuegoweb-local.tar
docker compose up
```

Then open:

```text
http://127.0.0.1:8000/phuEGOweb
```

Stop the app with:

```bash
docker compose down
```

## Save the Image as a Tar File

After building:

```bash
docker save phuegoweb-local:latest -o phuegoweb-local.tar
```

Load it on another machine:

```bash
docker load -i phuegoweb-local.tar
```

The target machine only needs these files and folders next to `docker-compose.yml`: `phuegoweb-local.tar`, `phuego_config.yaml`, `support_data`, `results`, `databases`, and `uploads`.
