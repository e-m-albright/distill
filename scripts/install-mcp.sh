#!/usr/bin/env bash
# Install Distillation MCP server in Claude Desktop.
# Run from project root: ./scripts/install-mcp.sh
#
# Uses uv run python -m app.mcp_server with cwd set to project root.
# This avoids fastmcp run's file-path loading, which breaks app.* imports.

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

CONFIG_DIR="$HOME/Library/Application Support/Claude"
CONFIG="$CONFIG_DIR/claude_desktop_config.json"

echo "Installing Distillation MCP server in Claude Desktop..."
echo "  Project: $REPO_ROOT"

# Validate .env and GOOGLE_API_KEY (required for distill, summarize, organize)
ENV_FILE="$REPO_ROOT/.env"
if [[ ! -f "$ENV_FILE" ]]; then
    echo ""
    echo "Warning: .env not found. Create it from .env.example and set GOOGLE_API_KEY."
    echo "  cp .env.example .env"
    echo "  # Edit .env and add your key from https://aistudio.google.com/apikey"
    echo ""
    read -r -p "Continue anyway? [y/N] " resp
    [[ "$resp" =~ ^[yY] ]] || exit 1
elif ! grep -q '^GOOGLE_API_KEY=.\+' "$ENV_FILE" 2>/dev/null; then
    echo ""
    echo "Warning: GOOGLE_API_KEY not set in .env. Distill, summarize, and organize will fail."
    echo "  Add: GOOGLE_API_KEY=your-key-from-https-aistudio.google.com-apikey"
    echo ""
    read -r -p "Continue anyway? [y/N] " resp
    [[ "$resp" =~ ^[yY] ]] || exit 1
fi

mkdir -p "$CONFIG_DIR"

# Merge or create config. --env-file ensures .env is loaded when Claude Desktop spawns the MCP
# process (avoids cwd/env inheritance issues that can prevent pydantic-settings from finding it).
python3 - "$CONFIG" "$REPO_ROOT" <<'PY'
import json
import sys

config_path = sys.argv[1]
repo_root = sys.argv[2]

try:
    with open(config_path) as f:
        cfg = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    cfg = {}

servers = cfg.setdefault("mcpServers", {})

# Project is installable (pyproject build-system); uv run uses project venv.
# --env-file loads .env into the process (Claude Desktop may spawn with minimal env).
servers["distillation"] = {
    "command": "uv",
    "args": ["run", "--project", repo_root, "--env-file", f"{repo_root}/.env", "python", "-m", "app.mcp_server"],
    "cwd": repo_root,
}

with open(config_path, "w") as f:
    json.dump(cfg, f, indent=2)

print("Updated claude_desktop_config.json")
PY

echo ""
echo "Done. Restart Claude Desktop to use Distillation."
echo ""
echo "Usage: In Claude, say:"
echo "  'Ingest my bookmarks from ~/Downloads/bookmarks.html'"
echo "  'List my bookmarks'"
echo "  'Distill the first 50 bookmarks'"
echo "  'Summarize https://example.com/article'"
echo "  'Discard bookmark 42'"
