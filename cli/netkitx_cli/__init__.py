"""NetKitX CLI — command-line interface for the NetKitX toolkit."""

import argparse
import json
import os
import sys
import time
import zipfile
from pathlib import Path

try:
    import httpx
except ImportError:
    print("Error: httpx not installed. Run: pip install netkitx-cli")
    sys.exit(1)

CONFIG_DIR = os.path.expanduser("~/.netkitx")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
DEFAULT_API = "http://127.0.0.1:8000"


# ── config helpers ──────────────────────────────────────────────────────────

def load_config() -> dict:
    cfg = {"api": DEFAULT_API, "token": None}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            cfg.update(json.load(f))
    if os.environ.get("NETKITX_API"):
        cfg["api"] = os.environ["NETKITX_API"]
    if os.environ.get("NETKITX_TOKEN"):
        cfg["token"] = os.environ["NETKITX_TOKEN"]
    return cfg


def save_config(cfg: dict):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


def get_headers(cfg: dict) -> dict:
    if not cfg.get("token"):
        print("Not logged in. Run: netkitx login -u USER -p PASS")
        sys.exit(1)
    return {"Authorization": f"Bearer {cfg['token']}"}


# ── commands ────────────────────────────────────────────────────────────────

def cmd_login(args, cfg):
    resp = httpx.post(
        f"{cfg['api']}/api/v1/auth/login",
        json={"username": args.username, "password": args.password},
        timeout=10,
    )
    if resp.status_code != 200:
        print(f"Login failed: {resp.text}")
        sys.exit(1)
    cfg["token"] = resp.json()["access_token"]
    save_config(cfg)
    print(f"Logged in as {args.username}")


def cmd_plugins(args, cfg):
    resp = httpx.get(
        f"{cfg['api']}/api/v1/plugins",
        headers=get_headers(cfg),
        timeout=10,
    )
    if resp.status_code != 200:
        print(f"Error: {resp.text}")
        sys.exit(1)
    plugins = resp.json()
    if not plugins:
        print("No plugins installed.")
        return
    print(f"{'NAME':<20} {'DISPLAY':<28} {'VERSION':<10} STATUS")
    print("-" * 70)
    for p in plugins:
        status = "enabled" if p.get("enabled") else "disabled"
        print(f"{p['name']:<20} {p.get('display_name',''):<28} {p.get('version',''):<10} {status}")


def cmd_run(args, cfg):
    params = {}
    if args.params:
        it = iter(args.params)
        for k in it:
            key = k.lstrip("-")
            try:
                val = next(it)
            except StopIteration:
                val = "true"
            params[key] = val

    resp = httpx.post(
        f"{cfg['api']}/api/v1/tasks",
        headers=get_headers(cfg),
        json={"plugin": args.plugin, "params": params},
        timeout=10,
    )
    if resp.status_code == 404:
        print(f"Plugin '{args.plugin}' not found. Run 'netkitx plugins' to list available plugins.")
        sys.exit(1)
    if resp.status_code not in (200, 201):
        print(f"Error {resp.status_code}: {resp.text}")
        sys.exit(1)

    task = resp.json()
    task_id = task["id"]
    print(f"Task started: {task_id}")

    if args.no_wait:
        print(f"Run 'netkitx result {task_id}' to check results.")
        return

    print("Waiting for result", end="", flush=True)
    for _ in range(120):
        time.sleep(2)
        print(".", end="", flush=True)
        r = httpx.get(
            f"{cfg['api']}/api/v1/tasks/{task_id}",
            headers=get_headers(cfg),
            timeout=10,
        )
        if r.status_code != 200:
            continue
        t = r.json()
        if t.get("status") in ("done", "error", "failed"):
            print()
            _print_result(t)
            return
    print("\nTimeout. Run 'netkitx result " + task_id + "' later.")


def cmd_result(args, cfg):
    resp = httpx.get(
        f"{cfg['api']}/api/v1/tasks/{args.task_id}",
        headers=get_headers(cfg),
        timeout=10,
    )
    if resp.status_code != 200:
        print(f"Error: {resp.text}")
        sys.exit(1)
    _print_result(resp.json())


def cmd_tasks(args, cfg):
    resp = httpx.get(
        f"{cfg['api']}/api/v1/tasks",
        headers=get_headers(cfg),
        timeout=10,
    )
    if resp.status_code != 200:
        print(f"Error: {resp.text}")
        sys.exit(1)
    tasks = resp.json()
    if not tasks:
        print("No tasks.")
        return
    print(f"{'ID':<38} {'PLUGIN':<20} {'STATUS':<10} CREATED")
    print("-" * 85)
    for t in tasks[:20]:
        print(f"{t['id']:<38} {t.get('plugin',''):<20} {t.get('status',''):<10} {t.get('created_at','')[:19]}")


def cmd_config(args, cfg):
    if args.api:
        cfg["api"] = args.api.rstrip("/")
        save_config(cfg)
        print(f"API set to {cfg['api']}")
    else:
        print(f"API: {cfg['api']}")
        print(f"Token: {'set' if cfg.get('token') else 'not set'}")


def cmd_pack(args, cfg):
    """Pack a plugin directory into a zip archive for publishing."""
    plugin_dir = Path(args.directory).resolve()

    # Validate
    yaml_path = plugin_dir / "plugin.yaml"
    if not yaml_path.exists():
        print(f"Error: plugin.yaml not found in {plugin_dir}")
        sys.exit(1)

    # Read name + version from plugin.yaml (no PyYAML dep — simple parse)
    name, version = _read_yaml_fields(yaml_path, ["name", "version"])
    if not name:
        print("Error: 'name' field missing in plugin.yaml")
        sys.exit(1)
    version = version or "0.0.1"

    out_name = args.output or f"{name}-{version}.zip"
    out_path = Path(out_name).resolve()

    # Collect files to pack
    exclude = {".git", "__pycache__", "*.pyc", ".DS_Store", "*.egg-info"}
    files = []
    for f in plugin_dir.rglob("*"):
        if f.is_file() and not any(
            f.name == pat or f.name.endswith(pat.lstrip("*"))
            for pat in exclude
        ):
            files.append(f)

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            arcname = f.relative_to(plugin_dir.parent)
            zf.write(f, arcname)

    print(f"Packed {len(files)} files → {out_path.name}")
    print(f"  Plugin : {name}")
    print(f"  Version: {version}")
    print(f"\nTo publish: netkitx publish {out_path.name}")


def cmd_publish(args, cfg):
    """Upload a plugin zip to the NetKitX Marketplace."""
    zip_path = Path(args.file)
    if not zip_path.exists():
        print(f"Error: file not found: {zip_path}")
        sys.exit(1)

    print(f"Publishing {zip_path.name} to {cfg['api']} ...")
    with open(zip_path, "rb") as f:
        resp = httpx.post(
            f"{cfg['api']}/api/v1/marketplace/publish",
            headers=get_headers(cfg),
            files={"file": (zip_path.name, f, "application/zip")},
            timeout=60,
        )

    if resp.status_code in (200, 201):
        data = resp.json()
        print(f"Published successfully!")
        print(f"  {data.get('message', '')}")
    else:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        print(f"Publish failed ({resp.status_code}): {detail}")
        sys.exit(1)


def cmd_yank(args, cfg):
    """Yank (unpublish) a specific version from the Marketplace."""
    resp = httpx.post(
        f"{cfg['api']}/api/v1/marketplace/plugins/{args.name}/yank",
        headers=get_headers(cfg),
        json={"version": args.version},
        timeout=10,
    )
    if resp.status_code in (200, 204):
        print(f"Yanked {args.name} v{args.version}")
    else:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        print(f"Yank failed ({resp.status_code}): {detail}")
        sys.exit(1)


def _print_result(task: dict):
    status = task.get("status")
    plugin = task.get("plugin", "")
    print(f"Plugin : {plugin}")
    print(f"Status : {status}")
    result = task.get("result")
    if result is None:
        print("No result yet.")
        return
    if isinstance(result, str):
        print(result)
    elif isinstance(result, dict):
        output = result.get("output") or result.get("stdout") or result.get("data")
        if output:
            if isinstance(output, list):
                print(json.dumps(output, indent=2, ensure_ascii=False))
            else:
                print(output)
        else:
            print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))


def _read_yaml_fields(path: Path, fields: list[str]) -> list[str | None]:
    """Minimal YAML field reader — no PyYAML dependency."""
    values = {f: None for f in fields}
    with open(path) as fh:
        for line in fh:
            for field in fields:
                if line.startswith(f"{field}:"):
                    val = line.split(":", 1)[1].strip().strip('"').strip("'")
                    values[field] = val or None
    return [values[f] for f in fields]


# ── main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="netkitx",
        description="NetKitX CLI — network security toolkit",
    )
    sub = parser.add_subparsers(dest="command")

    # login
    p_login = sub.add_parser("login", help="Authenticate with a NetKitX instance")
    p_login.add_argument("-u", "--username", required=True)
    p_login.add_argument("-p", "--password", required=True)

    # plugins
    sub.add_parser("plugins", help="List installed plugins")

    # run
    p_run = sub.add_parser("run", help="Run a plugin")
    p_run.add_argument("plugin", help="Plugin name")
    p_run.add_argument("--no-wait", action="store_true", help="Don't wait for result")
    p_run.add_argument("params", nargs=argparse.REMAINDER, help="Plugin params: --key value ...")

    # result
    p_result = sub.add_parser("result", help="Get task result")
    p_result.add_argument("task_id")

    # tasks
    sub.add_parser("tasks", help="List recent tasks")

    # config
    p_cfg = sub.add_parser("config", help="Show or set config")
    p_cfg.add_argument("--api", help="Set API base URL (e.g. http://wql.me)")

    # pack
    p_pack = sub.add_parser("pack", help="Pack a plugin directory into a zip archive")
    p_pack.add_argument("directory", help="Path to plugin directory")
    p_pack.add_argument("-o", "--output", help="Output filename (default: <name>-<version>.zip)")

    # publish
    p_pub = sub.add_parser("publish", help="Publish a plugin zip to the Marketplace")
    p_pub.add_argument("file", help="Path to the plugin zip file")

    # yank
    p_yank = sub.add_parser("yank", help="Yank a plugin version from the Marketplace")
    p_yank.add_argument("name", help="Plugin name")
    p_yank.add_argument("version", help="Version to yank (e.g. 1.0.0)")

    args = parser.parse_args()
    cfg = load_config()

    commands = {
        "login":   cmd_login,
        "plugins": cmd_plugins,
        "run":     cmd_run,
        "result":  cmd_result,
        "tasks":   cmd_tasks,
        "config":  cmd_config,
        "pack":    cmd_pack,
        "publish": cmd_publish,
        "yank":    cmd_yank,
    }

    if args.command in commands:
        commands[args.command](args, cfg)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
