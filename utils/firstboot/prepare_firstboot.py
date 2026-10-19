#!/usr/bin/env python3
"""
prepare_firstboot.py — Render DietPi first-boot files for a given board.

Usage:
    python3 utils/firstboot/prepare_firstboot.py \\
        --board rpizero2|rpi5 \\
        --tailnet NAME \\
        --ssh-pubkey [PATH]           # flag alone = auto-detect ~/.ssh/id_*.pub
        [--username USERNAME]         # default: dietpi
        [--password]                  # flag alone = prompt; omit = generate a random one
        [--tailscale-authkey]         # flag alone = prompt; or set TS_AUTHKEY

    python3 utils/firstboot/prepare_firstboot.py --board rpizero2 --tailnet NAME --env-only

Secrets can also come from the environment, which keeps them out of shell history:
    FIRSTBOOT_PASSWORD     global root/dietpi password
    TS_AUTHKEY             Tailscale auth key
    NTFY_READER_PASSWORD   rpizero2 only: password of the ntfy 'reader' account

Output: {board}/firstboot/   (git-ignored)
    dietpi.txt
    Automation_Custom_Script.sh
    board.env                  (rpizero2 only — also embedded in the script)

Copy dietpi.txt and Automation_Custom_Script.sh to the boot partition before powering on.
--env-only writes just board.env, to update a board that is already running.
"""

import argparse
import getpass
import glob
import os
import re
import secrets
import string
import sys
from pathlib import Path

REPO_URL = "https://github.com/ozerodb/rpi-stuff"

SCRIPT_DIR = Path(__file__).parent
BASE_DIR = SCRIPT_DIR / "base"
DIETPI_BASE = BASE_DIR / "dietpi.txt.base"
SCRIPT_BASE = BASE_DIR / "Automation_Custom_Script.sh.base"

BOARDS = ("rpizero2", "rpi5")
DIETPI_DEFAULT_USER = "dietpi"

PROMPT = object()  # sentinel: flag given without a value → ask interactively


def die(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def random_secret(length: int) -> str:
    # Alphanumeric only: DietPi warns that $"|\. may break some software installs.
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def ntfy_token() -> str:
    # ntfy tokens are "tk_" followed by 29 lowercase alphanumerics.
    alphabet = string.ascii_lowercase + string.digits
    return "tk_" + "".join(secrets.choice(alphabet) for _ in range(29))


def bcrypt_hash(password: str) -> str:
    try:
        import bcrypt
    except ImportError:
        die("the 'bcrypt' package is required for rpizero2 (pip3 install bcrypt).")
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def prompt_secret(label: str, confirm: bool = False) -> str:
    value = getpass.getpass(f"{label}: ")
    if confirm and getpass.getpass(f"{label} (again): ") != value:
        die(f"{label}: values do not match.")
    return value


def resolve_secret(cli_value, env_var: str, label: str, confirm: bool = False) -> str | None:
    """CLI value > prompt (flag alone) > environment variable > None."""
    if cli_value is PROMPT:
        return prompt_secret(label, confirm)
    if cli_value is not None:
        print(f"warning: {label} passed on the command line ends up in shell history; "
              f"prefer the bare flag (prompt) or ${env_var}.", file=sys.stderr)
        return cli_value
    return os.environ.get(env_var) or None


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

    if not key.startswith(("ssh-", "ecdsa-", "sk-")):
        die(f"File does not look like an SSH public key: {path}")

    return key


def render_board_env(board: str, tailnet: str) -> str:
    """Contents of {board}/.env on the Pi. Empty for boards whose .env is transferred by hand."""
    if board != "rpizero2":
        return ""

    reader_password = os.environ.get("NTFY_READER_PASSWORD") or prompt_secret(
        "ntfy 'reader' password (used by the phone app)", confirm=True
    )
    if len(reader_password) < 12:
        die("ntfy reader password must be at least 12 characters.")

    # 'publisher' only ever authenticates with its token; its password is random and discarded.
    publisher_hash = bcrypt_hash(random_secret(32))
    reader_hash = bcrypt_hash(reader_password)
    token = ntfy_token()

    # Single quotes: Compose treats them literally, so the '$' in bcrypt hashes survives.
    return "\n".join([
        "# Rendered by utils/firstboot/prepare_firstboot.py — do not commit.",
        f"TAILNET={tailnet}",
        f"NTFY_AUTH_USERS='reader:{reader_hash}:user,publisher:{publisher_hash}:user'",
        f"NTFY_AUTH_TOKENS='publisher:{token}:gatus and scripts'",
        f"NTFY_PUBLISH_TOKEN={token}",
        "",
    ])


def substitute(template: str, substitutions: dict[str, str]) -> str:
    result = template
    for placeholder, value in substitutions.items():
        result = result.replace(f"{{{{{placeholder}}}}}", value)
    remaining = re.findall(r"\{\{[A-Z_]+\}\}", result)
    if remaining:
        die(f"unsubstituted placeholders remain: {remaining}")
    return result


def write_private(path: Path, content: str, mode: int = 0o600) -> None:
    path.touch(mode=mode, exist_ok=True)
    path.chmod(mode)
    path.write_text(content)


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
        nargs="?",
        const=PROMPT,
        default=None,
        metavar="PASSWORD",
        help="Global root/dietpi password. Flag alone prompts; omitted → $FIRSTBOOT_PASSWORD "
             "or a random one, printed once.",
    )
    parser.add_argument(
        "--tailnet",
        required=True,
        metavar="NAME",
        help="Tailscale tailnet name (MagicDNS suffix). Written to /etc/environment on the board.",
    )
    parser.add_argument(
        "--tailscale-authkey",
        nargs="?",
        const=PROMPT,
        default=None,
        metavar="KEY",
        help="Tailscale auth key. Flag alone prompts; omitted → $TS_AUTHKEY, else authenticate "
             "manually after boot.",
    )
    parser.add_argument(
        "--env-only",
        action="store_true",
        help="Only write {board}/firstboot/board.env (to update a running board).",
    )
    args = parser.parse_args()

    if not re.match(r"^[a-z0-9][a-z0-9-]*$", args.tailnet):
        die(f"Invalid tailnet name: {args.tailnet!r} (expected e.g. 'tail1234' or 'my-tailnet', "
            "without .ts.net)")

    repo_root = SCRIPT_DIR.parent.parent
    out_dir = repo_root / args.board / "firstboot"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_dir.chmod(0o700)

    env_out = out_dir / "board.env"

    if args.env_only:
        board_env = render_board_env(args.board, args.tailnet)
        if not board_env:
            die(f"{args.board} has no rendered .env — copy {args.board}/.env.example instead.")
        write_private(env_out, board_env)
        print(f"\nWritten: {env_out}")
        print("Install it on the running board:")
        print(f"  cat {env_out} | ssh {args.username}@<tailscale-ip> \\")
        print(f"      \"umask 077 && cat > ~/rpi-stuff/{args.board}/.env\"")
        print(f"  ssh {args.username}@<tailscale-ip> \"cd ~/rpi-stuff && ./utils/scripts/update-stack.sh\"")
        return

    if args.ssh_pubkey == "UNSET":
        parser.error("--ssh-pubkey is required (use --ssh-pubkey alone to auto-detect).")

    ssh_pubkey = resolve_ssh_pubkey(args.ssh_pubkey)

    if not DIETPI_BASE.exists():
        die(f"Template not found: {DIETPI_BASE}")
    if not SCRIPT_BASE.exists():
        die(f"Template not found: {SCRIPT_BASE}")

    if not re.match(r"^[a-z_][a-z0-9_-]{0,31}$", args.username):
        die(f"Invalid username: {args.username!r}")

    password = resolve_secret(args.password, "FIRSTBOOT_PASSWORD", "Global password", confirm=True)
    generated_password = password is None
    if generated_password:
        password = random_secret(24)
    elif len(password) < 12:
        die("Global password must be at least 12 characters.")

    authkey = resolve_secret(args.tailscale_authkey, "TS_AUTHKEY", "Tailscale auth key") or ""
    if authkey and not authkey.startswith("tskey-"):
        die("Tailscale auth key should start with 'tskey-'.")

    board_env = render_board_env(args.board, args.tailnet)
    if board_env:
        write_private(env_out, board_env)

    substitutions = {
        "HOSTNAME": args.board,
        "SSH_PUBKEY": ssh_pubkey,
        "REPO_URL": REPO_URL,
        "TAILSCALE_AUTHKEY": authkey,
        "TAILNET": args.tailnet,
        "USERNAME": args.username,
        "GLOBAL_PASSWORD": password,
        "BOARD_ENV": board_env.rstrip("\n"),
    }

    dietpi_out = out_dir / "dietpi.txt"
    script_out = out_dir / "Automation_Custom_Script.sh"

    write_private(dietpi_out, substitute(DIETPI_BASE.read_text(), substitutions))
    write_private(script_out, substitute(SCRIPT_BASE.read_text(), substitutions), mode=0o700)

    print(f"\nOutput written to: {out_dir}/")
    print(f"  Username : {args.username}")
    if generated_password:
        print(f"  Password : {password}  ← generated; save it in your password manager now")
    else:
        print("  Password : (as specified)")
    if board_env:
        print(f"  board.env: embedded in the script (copy also at {env_out})")
    print()
    print("Copy both files to the boot partition:")
    print(f"  cp {out_dir}/dietpi.txt /Volumes/<BOOT>/dietpi.txt")
    print(f"  cp {out_dir}/Automation_Custom_Script.sh /Volumes/<BOOT>/Automation_Custom_Script.sh")
    print()
    if authkey:
        print("Note: the boot partition now holds the Tailscale auth key in plaintext.")
        print("      Use a single-use, pre-approved, short-expiry key with a tag.")
    else:
        print("Note: No Tailscale authkey provided.")
        print("      After first boot, SSH in and run: sudo tailscale up --ssh")
        if args.board == "rpi5":
            print("      Then: sudo tailscale set --advertise-exit-node")
    print()


if __name__ == "__main__":
    main()
