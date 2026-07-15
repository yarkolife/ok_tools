# systemd autostart for the OK Tools stack

Runs the production Docker Compose stack as a systemd service so it starts on
boot **and only after** its NAS / custom bind-mount host paths are mounted.

Why this matters: if Docker starts the containers before `/mnt/nas` (or another
NAS/export path) is mounted, Docker creates an empty directory at the mount
point and the app silently reads/writes the wrong location. `RequiresMountsFor=`
makes systemd wait for those mounts (and pull in automount units) first.

## Files

- `ok-tools.service` — unit template. `__PRODUCTION_DIR__` and `__DOCKER_BIN__`
  are substituted at install time. `Type=oneshot` + `RemainAfterExit=yes` wraps
  `docker compose up -d` / `down`.
- `../scripts/install-systemd.sh` — renders the unit into
  `/etc/systemd/system/ok-tools.service`, generates the mount dependency drop-in
  from `.env`, then `daemon-reload` + `enable`.

## Install

```bash
sudo deployment/scripts/install-systemd.sh
# or start it right away:
sudo systemctl start ok-tools
```

The main `install.sh` also offers to run this at the end of a fresh install.

### Where the mount paths come from

`install-systemd.sh` reads the production `.env` and collects:

- `NAS_MOUNT_PATH`
- `CUSTOM_MOUNT_1_PATH` … `CUSTOM_MOUNT_10_PATH`

and writes them into
`/etc/systemd/system/ok-tools.service.d/10-mounts.conf` as:

```ini
[Unit]
RequiresMountsFor=/mnt/nas /mnt/austausch_export
```

If a required path is not modelled in `.env` (e.g. an austausch export target),
pass it explicitly:

```bash
sudo EXTRA_MOUNTS="/mnt/austausch_export" deployment/scripts/install-systemd.sh
```

Re-run the script after changing mount paths in `.env`.

### Overrides

- `PRODUCTION_DIR` — production dir (default: `../ok_tools_production`)
- `SERVICE_NAME` — unit name (default: `ok-tools`)
- `EXTRA_MOUNTS` — extra space-separated paths to require

## Verify / operate

```bash
systemctl status ok-tools
systemctl show ok-tools -p RequiresMountsFor -p After   # confirm deps
sudo systemctl start ok-tools
sudo systemctl stop ok-tools
```

> While the unit manages the stack, don't also run the `start.sh` / `stop.sh`
> helpers by hand — both call `docker compose up -d` / `down` and will fight
> over container state.
