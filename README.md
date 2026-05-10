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
| Gatus | `https://rpizero2.TAILNET.ts.net` |
| ntfy | `https://rpizero2.TAILNET.ts.net/ntfy` |

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
    --board rpi5 --tailnet <tailnet> --ssh-pubkey --tailscale-authkey "tskey-auth-..."

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
python3 utils/firstboot/prepare_firstboot.py \
    --board rpizero2 \
    --tailnet <tailnet> \
    --ssh-pubkey \
    --tailscale-authkey "tskey-auth-..."
```

`--tailnet` is the MagicDNS tailnet name (without .ts.net). `--ssh-pubkey` alone auto-detects `~/.ssh/id_*.pub`. `--tailscale-authkey` optional.

Copy the two output files to the boot partition (SD card for rpizero2, NVMe for rpi5 — see above), then power on (~10–15 min). First boot:

1. Adds `dietpi` to docker group, clones this repo
2. Configures UFW, hardens SSH, sets up fail2ban
3. Joins Tailnet (rpi5 also advertises as exit node)
4. Writes `TAILNET` to `/etc/environment` (persists across reboots)
5. **rpizero2:** starts Docker stack automatically — no manual steps needed
6. **rpi5:** does not start Docker — transfer `.env` and start manually

---

## Deploy secrets + start

**rpizero2** — stack starts automatically during first boot, no `.env` needed.

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

### ntfy subscriber hash

ntfy on rpizero2 has one reader account for subscribing to topics. Fill in the hash in `rpizero2/config/ntfy.yml`:

```bash
python3 -c "import bcrypt, getpass; print(bcrypt.hashpw(getpass.getpass().encode(), bcrypt.gensalt()).decode())"
```

Replace `<bcrypt-hash>` in `rpizero2/config/ntfy.yml` with the output.

---

## Post-boot

**AdGuard Home:** complete setup wizard, then set rpi5 Tailscale IP as global nameserver in Tailscale admin → DNS (enable Override local DNS).

**Exit node:** approve in Tailscale admin → Machines → rpi5 → Edit route settings.

**SFTP (Secure ShellFish):** connect to rpi5 Tailscale IP with `dietpi` user + SSH key, path `/opt/storage/`. Calibre at `/opt/storage/calibre`, Paperless consume at `/opt/storage/paperless/consume`.

**Homer:** `rpi5/config/homer.yml` is tracked in git. `${TAILNET}` is substituted at container startup via `envsubst`.
