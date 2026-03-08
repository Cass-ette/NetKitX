# netkitx-cli

Command-line interface for the [NetKitX](https://github.com/Cass-ette/NetKitX) network security toolkit.

## Install

```bash
pip install netkitx-cli
```

## Quick Start

```bash
# Point at your NetKitX instance
netkitx config --api http://your-server

# Log in
netkitx login -u admin -p password

# List installed plugins
netkitx plugins

# Run a plugin
netkitx run nmap --target 192.168.1.1

# Check recent tasks
netkitx tasks

# Get a specific task result
netkitx result <task-id>
```

## Commands

| Command | Description |
|---------|-------------|
| `login -u USER -p PASS` | Authenticate with a NetKitX instance |
| `plugins` | List installed plugins |
| `run PLUGIN [params...]` | Run a plugin (waits for result by default) |
| `run PLUGIN --no-wait [params...]` | Submit a task without waiting |
| `result TASK_ID` | Fetch task result by ID |
| `tasks` | List recent tasks |
| `config [--api URL]` | Show or set config |
| `pack DIRECTORY [-o output.zip]` | Pack a plugin directory into a zip |
| `publish ZIPFILE` | Publish a plugin zip to the Marketplace |
| `yank NAME VERSION` | Yank (unpublish) a plugin version |

## Plugin Development

Install the SDK for local plugin development and testing:

```bash
pip install netkitx-sdk
```

Develop → pack → publish workflow:

```bash
# Pack your plugin
netkitx pack ./my-plugin

# Publish to Marketplace
netkitx publish my-plugin-1.0.0.zip
```

See full developer docs at [wql.me/developers](http://wql.me/developers).

## Configuration

Config is stored in `~/.netkitx/config.json`. Environment variables override config file:

- `NETKITX_API` — API base URL
- `NETKITX_TOKEN` — Bearer token

## License

MIT
