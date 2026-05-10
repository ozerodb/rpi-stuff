#!/usr/bin/env python3
"""
prepare_firstboot.py — Render DietPi first-boot files for a given board.

Usage:
    python3 utils/firstboot/prepare_firstboot.py \\
        --board rpizero2|rpi5 \\
        --tailnet NAME \\
        --ssh-pubkey [PATH]           # flag alone = auto-detect ~/.ssh/id_*.pub
        [--username USERNAME]         # default: dietpi
        [--password PASSWORD]         # default: dietpi (DietPi default)
        [--tailscale-authkey KEY]

Output: {board}/firstboot/   (git-ignored)
    dietpi.txt
    Automation_Custom_Script.sh

Copy both files to the SD card boot partition before powering on.
"""

import argparse
import glob
import os
import re
import stat
import sys
from pathlib import Path

REPO_URL = "https://github.com/ozerodb/rpi-stuff"

SCRIPT_DIR = Path(__file__).parent
BASE_DIR = SCRIPT_DIR / "base"
DIETPI_BASE = BASE_DIR / "dietpi.txt.base"
SCRIPT_BASE = BASE_DIR / "Automation_Custom_Script.sh.base"

BOARDS = ("rpizero2", "rpi5")
DIETPI_DEFAULT_USER = "dietpi"
DIETPI_DEFAULT_PASSWORD = "dietpi"


def die(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def resolve_ssh_pubkey(value: str | None) -> str:
    """Return the SSH public key string. value=None means auto-detect."""
    if value is None:
        candidates = sorted(glob.glob(os.path.expanduser("~/.ssh/id_*.pub")))
        if not candidates:
            die("No public key found in ~/.ssh/. Use --ssh-pubkey PATH to specify one.")
        if len(candidates) > 1:
            print(f"Multiple keys found; using {candidates[0]}.", file=sys.stderr)
            print("Use --ssh-pubkey PATH to pick a specific one.", file=sys.stderr)
        path = candidates[0]
    else:
        path = value

    try:
        key = Path(path).read_text().strip()
    except FileNotFoundError:
        die(f"SSH public key not found: {path}")

    if not key.startswith("ssh-"):
        die(f"File does not look like an SSH public key: {path}")

    return key


def substitute(template: str, substitutions: dict[str, str]) -> str:
    result = template
    for placeholder, value in substitutions.items():
        result = result.replace(f"{{{{{placeholder}}}}}", value)
    remaining = re.findall(r"\{\{[A-Z_]+\}\}", result)
    if remaining:
        print(f"warning: unsubstituted placeholders remain: {remaining}", file=sys.stderr)
    return result


def write_executable(path: Path, content: str) -> None:
    path.write_text(content)
    path.chmod(0o700)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render DietPi first-boot files for a board.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--board",
        required=True,
        choices=BOARDS,
        help="Target board (rpizero2 or rpi5)",
    )
    parser.add_argument(
        "--ssh-pubkey",
        nargs="?",
        const=None,       # flag with no value → auto-detect
        default="UNSET",  # flag absent → error
        metavar="PATH",
        help="Path to SSH public key. Omit the value to auto-detect from ~/.ssh/id_*.pub.",
    )
    parser.add_argument(
        "--username",
        default=DIETPI_DEFAULT_USER,
        metavar="USERNAME",
        help=f"DietPi username (default: {DIETPI_DEFAULT_USER})",
    )
    parser.add_argument(
        "--password",
        default=DIETPI_DEFAULT_PASSWORD,
        metavar="PASSWORD",
        help=f"DietPi global password (default: {DIETPI_DEFAULT_PASSWORD!r} — DietPi default)",
    )
    parser.add_argument(
        "--tailnet",
        required=True,
        metavar="NAME",
        help="Tailscale tailnet name (MagicDNS suffix). Written to /etc/environment on the board.",
    )
    parser.add_argument(
        "--tailscale-authkey",
        default="",
        metavar="KEY",
        help="Tailscale auth key (optional). Leave out to authenticate manually after boot.",
    )
    args = parser.parse_args()

    if args.ssh_pubkey == "UNSET":
        parser.error("--ssh-pubkey is required (use --ssh-pubkey alone to auto-detect).")

    ssh_pubkey = resolve_ssh_pubkey(args.ssh_pubkey)

    if not DIETPI_BASE.exists():
        die(f"Template not found: {DIETPI_BASE}")
    if not SCRIPT_BASE.exists():
        die(f"Template not found: {SCRIPT_BASE}")

    if not re.match(r"^[a-z_][a-z0-9_-]{0,31}$", args.username):
        die(f"Invalid username: {args.username!r}")

    substitutions = {
        "HOSTNAME": args.board,
        "SSH_PUBKEY": ssh_pubkey,
        "REPO_URL": REPO_URL,
        "TAILSCALE_AUTHKEY": args.tailscale_authkey,
        "TAILNET": args.tailnet,
        "USERNAME": args.username,
        "GLOBAL_PASSWORD": args.password,
    }

    repo_root = SCRIPT_DIR.parent.parent
    out_dir = repo_root / args.board / "firstboot"
    out_dir.mkdir(parents=True, exist_ok=True)

    dietpi_out = out_dir / "dietpi.txt"
    script_out = out_dir / "Automation_Custom_Script.sh"

    dietpi_content = substitute(DIETPI_BASE.read_text(), substitutions)
    script_content = substitute(SCRIPT_BASE.read_text(), substitutions)

    dietpi_out.write_text(dietpi_content)
    write_executable(script_out, script_content)

    using_defaults = args.username == DIETPI_DEFAULT_USER and args.password == DIETPI_DEFAULT_PASSWORD

    print(f"\nOutput written to: {out_dir}/")
    print(f"  Username : {args.username}")
    if using_defaults:
        print(f"  Password : {args.password!r}  ← DietPi default, consider --password")
    else:
        print(f"  Password : (as specified)")
    print()
    print("Copy both files to the boot partition:")
    print(f"  cp {out_dir}/dietpi.txt /Volumes/<BOOT>/dietpi.txt")
    print(f"  cp {out_dir}/Automation_Custom_Script.sh /Volumes/<BOOT>/Automation_Custom_Script.sh")
    print()
    if not args.tailscale_authkey:
        print("Note: No Tailscale authkey provided.")
        print(f"      After first boot, SSH in and run: tailscale up --ssh")
        if args.board == "rpi5":
            print("      Then: tailscale set --advertise-exit-node")
        print()


if __name__ == "__main__":
    main()
