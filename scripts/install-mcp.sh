#!/usr/bin/env bash
# Install Distillation MCP server in Claude Desktop.
# Run from project root: ./scripts/install-mcp.sh

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Ensure .env exists for GOOGLE_API_KEY
if [[ -f .env ]]; then
  ENV_FILE=".env"
else
  ENV_FILE=""
fi

echo "Installing Distillation MCP server in Claude Desktop..."
echo "  Project: $REPO_ROOT"
[[ -n "$ENV_FILE" ]] && echo "  Env file: $ENV_FILE"

if [[ -n "$ENV_FILE" ]]; then
  uv run fastmcp install claude-desktop app/mcp_server.py:mcp \
    --project . \
    --name distillation \
    --env-file .env
else
  uv run fastmcp install claude-desktop app/mcp_server.py:mcp \
    --project . \
    --name distillation
fi

# Remove duplicate mcp_server entry if it points to distillation (macOS)
CONFIG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
if [[ -f "$CONFIG" ]]; then
  python3 - "$CONFIG" <<'PY'
import json, sys
path = sys.argv[1]
with open(path) as f:
    cfg = json.load(f)
servers = cfg.get('mcpServers', {})
if 'mcp_server' in servers and 'distillation' in servers:
    m, d = servers['mcp_server'], servers['distillation']
    if m.get('args') == d.get('args'):
        del servers['mcp_server']
        with open(path, 'w') as f:
            json.dump(cfg, f, indent=2)
        print('Removed duplicate mcp_server entry.')
PY
fi

echo ""
echo "Done. Restart Claude Desktop to use Distillation."
echo ""
echo "Usage: In Claude, say:"
echo "  'Ingest my bookmarks from ~/Downloads/bookmarks.html'"
echo "  'List my bookmarks'"
echo "  'Distill the first 50 bookmarks'"
echo "  'Summarize https://example.com/article'"
echo "  'Discard bookmark 42'"
