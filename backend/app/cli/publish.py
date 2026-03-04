"""CLI tool for publishing plugins to marketplace."""

import hashlib
import zipfile
from pathlib import Path
from typing import Optional

import httpx
import typer
import yaml
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm
from rich.table import Table

app = typer.Typer(help="Publish plugins to NetKitX marketplace")
console = Console()


def load_config() -> dict:
    """Load CLI configuration (API URL, token)."""
    config_path = Path.home() / ".netkitx" / "config.yaml"
    if not config_path.exists():
        console.print("[red]Error: No config found. Run 'netkitx login' first.[/red]")
        raise typer.Exit(1)

    with open(config_path) as f:
        return yaml.safe_load(f)


def validate_plugin_structure(plugin_dir: Path) -> dict:
    """Validate plugin directory structure and return metadata."""
    plugin_yaml = plugin_dir / "plugin.yaml"
    if not plugin_yaml.exists():
        console.print(f"[red]Error: No plugin.yaml found in {plugin_dir}[/red]")
        raise typer.Exit(1)

    with open(plugin_yaml) as f:
        config = yaml.safe_load(f)

    # Validate required fields
    required = ["name", "version", "description", "category", "engine"]
    missing = [f for f in required if f not in config]
    if missing:
        console.print(f"[red]Error: Missing required fields: {', '.join(missing)}[/red]")
        raise typer.Exit(1)

    # Check for main entry point
    engine = config["engine"]
    if engine == "python":
        if not (plugin_dir / "main.py").exists():
            console.print("[red]Error: Python plugin must have main.py[/red]")
            raise typer.Exit(1)
    elif engine == "javascript":
        if not (plugin_dir / "main.js").exists():
            console.print("[red]Error: JavaScript plugin must have main.js[/red]")
            raise typer.Exit(1)

    return config


def create_package(plugin_dir: Path, output_dir: Path) -> Path:
    """Create zip package from plugin directory."""
    config = validate_plugin_structure(plugin_dir)
    plugin_name = config["name"]
    version = config["version"]

    zip_name = f"{plugin_name}-{version}.zip"
    zip_path = output_dir / zip_name

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in plugin_dir.rglob("*"):
            if file_path.is_file():
                # Skip hidden files and __pycache__
                if file_path.name.startswith(".") or "__pycache__" in str(file_path):
                    continue

                arcname = file_path.relative_to(plugin_dir.parent)
                zf.write(file_path, arcname)

    return zip_path


@app.command()
def pack(
    plugin_dir: Path = typer.Argument(..., help="Plugin directory to package"),
    output: Optional[Path] = typer.Option(None, help="Output directory for zip file"),
):
    """Package a plugin into a zip file."""
    if not plugin_dir.exists() or not plugin_dir.is_dir():
        console.print(f"[red]Error: {plugin_dir} is not a valid directory[/red]")
        raise typer.Exit(1)

    output_dir = output or Path.cwd()
    output_dir.mkdir(parents=True, exist_ok=True)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Packaging plugin...", total=None)
        zip_path = create_package(plugin_dir, output_dir)

    # Calculate hash
    sha256 = hashlib.sha256()
    with open(zip_path, "rb") as f:
        while chunk := f.read(8192):
            sha256.update(chunk)

    console.print(f"[green]✓[/green] Package created: {zip_path}")
    console.print(f"[dim]SHA256: {sha256.hexdigest()}[/dim]")
    console.print(f"[dim]Size: {zip_path.stat().st_size:,} bytes[/dim]")


@app.command()
def publish(
    plugin_dir: Path = typer.Argument(..., help="Plugin directory to publish"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate without publishing"),
):
    """Publish a plugin to the marketplace."""
    if not plugin_dir.exists() or not plugin_dir.is_dir():
        console.print(f"[red]Error: {plugin_dir} is not a valid directory[/red]")
        raise typer.Exit(1)

    # Load config
    config = load_config()
    api_url = config.get("api_url", "http://localhost:8000")
    token = config.get("token")

    if not token:
        console.print("[red]Error: Not logged in. Run 'netkitx login' first.[/red]")
        raise typer.Exit(1)

    # Validate plugin
    console.print("[bold]Validating plugin...[/bold]")
    plugin_config = validate_plugin_structure(plugin_dir)

    # Display info
    table = Table(title="Plugin Information")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Name", plugin_config["name"])
    table.add_row("Version", plugin_config["version"])
    table.add_row("Description", plugin_config.get("description", ""))
    table.add_row("Category", plugin_config.get("category", ""))
    table.add_row("Engine", plugin_config["engine"])

    if plugin_config.get("dependencies"):
        deps = ", ".join(d["name"] for d in plugin_config["dependencies"])
        table.add_row("Dependencies", deps)

    console.print(table)

    if dry_run:
        console.print("[green]✓[/green] Validation passed (dry run)")
        return

    # Confirm
    if not Confirm.ask("Publish this plugin to marketplace?"):
        console.print("[yellow]Cancelled[/yellow]")
        raise typer.Exit(0)

    # Create package
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Creating package...", total=None)

        temp_dir = Path("/tmp/netkitx_publish")
        temp_dir.mkdir(exist_ok=True)
        zip_path = create_package(plugin_dir, temp_dir)

        progress.update(task, description="Uploading to marketplace...")

        # Upload
        try:
            with open(zip_path, "rb") as f:
                response = httpx.post(
                    f"{api_url}/api/v1/marketplace/publish",
                    files={"file": (zip_path.name, f, "application/zip")},
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=60.0,
                )

            response.raise_for_status()
            result = response.json()

            progress.update(task, description="[green]✓ Published successfully[/green]")

        except httpx.HTTPStatusError as e:
            console.print(f"[red]Error: {e.response.json().get('detail', str(e))}[/red]")
            raise typer.Exit(1)
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(1)
        finally:
            # Cleanup
            if zip_path.exists():
                zip_path.unlink()

    console.print(f"[green]✓[/green] {result['message']}")
    console.print(f"[dim]Plugin: {result['plugin_name']} v{result['version']}[/dim]")


@app.command()
def yank(
    plugin_name: str = typer.Argument(..., help="Plugin name"),
    version: str = typer.Argument(..., help="Version to yank"),
):
    """Yank a published version (mark as unavailable)."""
    config = load_config()
    api_url = config.get("api_url", "http://localhost:8000")
    token = config.get("token")

    if not token:
        console.print("[red]Error: Not logged in. Run 'netkitx login' first.[/red]")
        raise typer.Exit(1)

    # Confirm
    if not Confirm.ask(f"Yank {plugin_name} version {version}? This cannot be undone."):
        console.print("[yellow]Cancelled[/yellow]")
        raise typer.Exit(0)

    try:
        response = httpx.delete(
            f"{api_url}/api/v1/marketplace/plugins/{plugin_name}/versions/{version}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30.0,
        )
        response.raise_for_status()
        result = response.json()

        console.print(f"[green]✓[/green] {result['message']}")

    except httpx.HTTPStatusError as e:
        console.print(f"[red]Error: {e.response.json().get('detail', str(e))}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
