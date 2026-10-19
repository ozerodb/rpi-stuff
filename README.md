# rpi-stuff

Just two Raspberry Pis running DietPi, everything on Tailscale.

## Boards

| Board | Role | Storage |
| --- | --- | --- |
| RPi Zero 2W (`rpizero2`) | Monitoring — Gatus + ntfy | SD card |
| RPi 5 (`rpi5`) | Services — AdGuard, Paperless, Calibre, etc | NVMe SSD |

## Services

Path-based routing via Caddy. `TAILNET` is the MagicDNS suffix set during firstboot.

### rpizero2

| Service | URL |
| --- | --- |
| Gatus | `https://rpizero2.TAILNET.ts.net` → `:8080` |
| ntfy | `https://rpizero2.TAILNET.ts.net` → `:2586` |

### rpi5

| Service | URL |
| --- | --- |
| Homer | `https://rpi5.TAILNET.ts.net` |
| AdGuard Home | `https://rpi5.TAILNET.ts.net/adguard` |
| Paperless-ngx | `https://rpi5.TAILNET.ts.net/paperless` |
| Calibre-Web | `https://rpi5.TAILNET.ts.net/calibre` |

Caddy handles HTTPS via Tailscale certs.

---

## Flashing

### rpizero2 — SD card

Standard: flash DietPi to SD card with rpi-imager, then copy firstboot files to the boot partition.

### rpi5 — NVMe

The RPi 5 supports USB mass storage mode: the NVMe appears as a drive on your Mac without touching the hat.

#### rpiboot mass storage mode (preferred)

Install rpiboot on Mac:

```bash
brew install libusb
git clone --depth=1 https://github.com/raspberrypi/usbboot
cd usbboot && make && sudo make install
```

Flash and copy firstboot files:

1. Power off rpi5
2. Hold the power button, then plug a USB-C data cable from rpi5 to Mac (use the Pi's power port — must be a data-capable cable)
3. Keep holding until the green LED blinks, then release
4. On Mac: `sudo rpiboot` — the NVMe mounts as a USB drive
5. Flash DietPi to it with rpi-imager (pick the mounted drive as target)
6. After flashing, the boot partition remounts — copy firstboot files:

```bash
python3 utils/firstboot/prepare_firstboot.py \
    --board rpi5 --tailnet <tailnet> --ssh-pubkey --tailscale-authkey

cp rpi5/firstboot/dietpi.txt /Volumes/bootfs/dietpi.txt
cp rpi5/firstboot/Automation_Custom_Script.sh /Volumes/bootfs/Automation_Custom_Script.sh
```

1. Eject, disconnect, boot

#### SD card bootstrap (fallback)

If rpiboot gives trouble: flash any Raspberry Pi OS to a spare SD card, boot rpi5 from it (NVMe hat can stay), then from the running Pi:

```bash
# Write DietPi image to NVMe (download image first)
sudo dd if=DietPi_RPi5-ARMv8-Bookworm.img of=/dev/nvme0n1 bs=4M status=progress conv=fsync

# Mount boot partition and copy firstboot files
sudo mount /dev/nvme0n1p1 /mnt
sudo cp dietpi.txt /mnt/
sudo cp Automation_Custom_Script.sh /mnt/
sudo umount /mnt

# Set NVMe as first boot device
sudo raspi-config nonint do_boot_order B2
sudo shutdown -h now
```

Remove SD card, power on — boots from NVMe.

---

## SD card prep (rpizero2 / rpi5 common)

```bash
pip3 install bcrypt   # rpizero2 only (hashes the ntfy password)

python3 utils/firstboot/prepare_firstboot.py \
    --board rpizero2 \
    --tailnet <tailnet> \
    --ssh-pubkey \
    --tailscale-authkey
```

- `--tailnet` is the MagicDNS tailnet name (without .ts.net).
- `--ssh-pubkey` alone auto-detects `~/.ssh/id_*.pub`.
- `--tailscale-authkey` alone prompts for the key (or set `TS_AUTHKEY`); omit it to run `tailscale up` by hand. Use a **single-use, pre-approved, short-expiry, tagged** key — it sits in plaintext on the boot partition.
- `--password` alone prompts for the root/dietpi password (or set `FIRSTBOOT_PASSWORD`); omit it and a random one is generated and printed once. The DietPi default `dietpi` is no longer used.
- rpizero2 also asks for the ntfy `reader` password (or set `NTFY_READER_PASSWORD`) and renders `rpizero2/firstboot/board.env` — ntfy users, the publisher token and `TAILNET`. It is embedded in the first-boot script and written to `rpizero2/.env` on the Pi.

Secrets passed as flag values still work but end up in shell history, so the script warns.

Copy the two output files to the boot partition (SD card for rpizero2, NVMe for rpi5 — see above), then power on (~10–15 min). First boot:

1. Adds `dietpi` to docker group, clones this repo
2. Configures UFW, hardens SSH (drop-in config, validated with `sshd -t`, refuses to run without an authorized key), sets up fail2ban
3. Joins Tailnet (rpi5 also advertises as exit node)
4. Writes `TAILNET` to `/etc/environment` (persists across reboots)
5. **rpizero2:** writes `rpizero2/.env` and starts the Docker stack — no manual steps needed
6. **rpi5:** does not start Docker — transfer `.env` and start manually

---

## Deploy secrets + start

**rpizero2** — stack starts automatically during first boot; `.env` comes from the first-boot script.

For future updates:

```bash
ssh dietpi@<tailscale-ip> "cd ~/rpi-stuff && ./utils/scripts/update-stack.sh"
```

**rpi5** — transfer `.env` first, then start:

```bash
# Transfer .env (scp unreliable on DietPi — use ssh pipe)
cat local-rpi5.env | ssh dietpi@<tailscale-ip> \
    "cat > ~/rpi-stuff/rpi5/.env && chmod 600 ~/rpi-stuff/rpi5/.env"

# Start stack
ssh dietpi@<tailscale-ip> "cd ~/rpi-stuff && ./utils/scripts/update-stack.sh"
```

`update-stack.sh` also handles future updates: `git pull` + `docker compose up -d`.

### ntfy accounts

Anonymous access is denied. Two accounts are provisioned from `rpizero2/.env` (ACLs in `rpizero2/config/ntfy.yml`):

| Account | Auth | Access | Used by |
| --- | --- | --- | --- |
| `reader` | password | read all topics | phone app |
| `publisher` | token (`NTFY_PUBLISH_TOKEN`) | write all topics | Gatus, backup script, your scripts |

```bash
curl -H "Authorization: Bearer $NTFY_PUBLISH_TOKEN" -d "hello" https://rpizero2.TAILNET.ts.net:2586/alerts
```

Gatus publishes to `http://ntfy:80` inside Docker, so alerts don't depend on Caddy, TLS or tailnet DNS. ntfy itself uses public resolvers, so the ntfy.sh upstream (iOS push) keeps working while rpi5's AdGuard is down.

To rotate credentials, or to update a board that is already running:

```bash
python3 utils/firstboot/prepare_firstboot.py --board rpizero2 --tailnet <tailnet> --env-only
cat rpizero2/firstboot/board.env | ssh dietpi@<tailscale-ip> "umask 077 && cat > ~/rpi-stuff/rpizero2/.env"
ssh dietpi@<tailscale-ip> "cd ~/rpi-stuff && ./utils/scripts/update-stack.sh"
```

Re-run `sudo bash utils/scripts/setup_ufw.sh` on a board provisioned before Caddy moved to host networking, so that 443/8080/2586 are open on `tailscale0`.

---

## Post-boot

**AdGuard Home:** complete setup wizard, then set rpi5 Tailscale IP as global nameserver in Tailscale admin → DNS (enable Override local DNS).

**Exit node:** approve in Tailscale admin → Machines → rpi5 → Edit route settings.

**SFTP (Secure ShellFish):** connect to rpi5 Tailscale IP with `dietpi` user + SSH key, path `/opt/storage/`. Calibre at `/opt/storage/calibre`, Paperless consume at `/opt/storage/paperless/consume`.

**Homer:** `rpi5/config/homer.yml` is tracked in git. `${TAILNET}` is substituted at container startup via `envsubst`.

---

## Backups (rpi5)

Nightly [restic](https://restic.net) backup of `APPDATA`, `STORAGE` and `rpi5/config/` (AdGuard config), with a `pg_dump` of Paperless taken first — the raw Postgres directory is excluded.

```bash
sudo ./utils/backup/install.sh          # installs restic, systemd service + timer, /etc/rpi-backup.env
sudo nano /etc/rpi-backup.env           # repository, password, optional ntfy token + healthchecks URL
sudo systemctl enable --now rpi-backup.timer
sudo systemctl start rpi-backup && journalctl -fu rpi-backup   # first run
```

- Failures go to ntfy (`NTFY_URL` + `NTFY_TOKEN`).
- Set `HC_PING_URL` (e.g. healthchecks.io) for a dead-man's switch: it alerts when a backup *doesn't* run — including when rpizero2, and so ntfy, is down.
- Keep `RESTIC_PASSWORD` in your password manager — without it the backups are unreadable.
- Restore drill: `restic snapshots`, then `restic restore latest --target /tmp/restore` and `psql < /opt/appdata/backup/paperless.sql`.

---

## Firewall

UFW allows SSH from the LAN, and SSH/HTTPS (plus DNS on rpi5, Gatus/ntfy ports on rpizero2) only `in on tailscale0`. Caddy and AdGuard use `network_mode: host`, so these rules actually apply — ports published by Docker would bypass UFW. Everything else listens on `127.0.0.1`.

For isolation *between* tailnet devices, use [Tailscale ACLs](https://tailscale.com/kb/1018/acls) with tags.

## CI

`.github/workflows/ci.yml` runs shellcheck, yamllint, a first-boot render smoke test, `docker compose config` and a Caddyfile check on every push and PR.
