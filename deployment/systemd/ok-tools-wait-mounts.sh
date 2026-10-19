#!/bin/bash
# Wait until every given host path sits on a real mount (NAS / custom mounts),
# so the Docker Compose stack never starts on top of an empty mount point.
#
# Used as ExecStartPre= of ok-tools.service. Unlike RequiresMountsFor=, a mount
# that is not ready yet at boot (NAS still booting, network slow) does not make
# systemd skip the stack for good: this script keeps retrying, and if it gives
# up the unit fails and Restart=on-failure runs it again.
#
# Usage: ok-tools-wait-mounts.sh PATH [PATH...]
# Environment: WAIT_MOUNTS_TIMEOUT (seconds, default 300)

set -u

TIMEOUT="${WAIT_MOUNTS_TIMEOUT:-300}"
INTERVAL=5

# A path counts as mounted when it exists (stat also triggers a systemd
# automount) and the filesystem holding it is neither the root filesystem nor
# a still-untriggered autofs placeholder. Sub-paths of a mount, such as
# /mnt/nas/INBOX, are handled the same way.
is_mounted() {
    local path="$1" target fstype
    # "$path/." forces a lookup inside the directory, which reliably triggers
    # an automount even when the mount point itself is only an autofs stub.
    stat "$path/." >/dev/null 2>&1 || return 1
    target="$(findmnt -n -o TARGET -T "$path" 2>/dev/null | tail -n 1)"
    fstype="$(findmnt -n -o FSTYPE -T "$path" 2>/dev/null | tail -n 1)"
    [ -n "$target" ] && [ "$target" != "/" ] && [ "$fstype" != "autofs" ]
}

if [ "$#" -eq 0 ]; then
    exit 0
fi

deadline=$(( $(date +%s) + TIMEOUT ))
while :; do
    missing=()
    for path in "$@"; do
        is_mounted "$path" || missing+=("$path")
    done
    if [ "${#missing[@]}" -eq 0 ]; then
        echo "All mounts ready: $*"
        exit 0
    fi
    if [ "$(date +%s)" -ge "$deadline" ]; then
        echo "Mounts still not ready after ${TIMEOUT}s: ${missing[*]}" >&2
        exit 1
    fi
    echo "Waiting for mounts: ${missing[*]}"
    sleep "$INTERVAL"
done
