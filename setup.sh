#!/bin/bash
# =============================================================================
# JobHunt Agent — Setup Script
# =============================================================================
# Creates config files from templates and symlinks workspace into OpenClaw.
#
# Usage:
#   ./setup.sh           # Interactive setup
#   ./setup.sh --link    # Just create symlinks (skip template copying)
#   ./setup.sh --check   # Verify setup is correct
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE="$SCRIPT_DIR/workspace"
OPENCLAW_DIR="$HOME/.openclaw"
OPENCLAW_WORKSPACE="$OPENCLAW_DIR/workspace"
OPENCLAW_CRON="$OPENCLAW_DIR/cron"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}!${NC} $1"; }
err()  { echo -e "  ${RED}✗${NC} $1"; }

copy_template() {
  local src="$1"
  local dst="$2"
  local label="$3"
  if [ -f "$dst" ]; then
    warn "$label already exists — skipping (delete to regenerate)"
  else
    cp "$src" "$dst"
    ok "Created $label — edit with your personal data"
  fi
}

# ---------------------------------------------------------------------------
# --check mode
# ---------------------------------------------------------------------------
if [ "$1" = "--check" ]; then
  echo "=== JobHunt Setup Check ==="
  errors=0

  # Check symlinks
  if [ -L "$OPENCLAW_WORKSPACE" ]; then
    target=$(readlink "$OPENCLAW_WORKSPACE")
    if [ "$target" = "$WORKSPACE" ]; then
      ok "Workspace symlink: $OPENCLAW_WORKSPACE → $WORKSPACE"
    else
      err "Workspace symlink points to wrong target: $target"
      errors=$((errors + 1))
    fi
  elif [ -d "$OPENCLAW_WORKSPACE" ]; then
    err "Workspace is a directory (not symlinked): $OPENCLAW_WORKSPACE"
    errors=$((errors + 1))
  else
    err "Workspace does not exist: $OPENCLAW_WORKSPACE"
    errors=$((errors + 1))
  fi

  if [ -L "$OPENCLAW_CRON/jobs.json" ]; then
    ok "Cron symlink: $(readlink "$OPENCLAW_CRON/jobs.json")"
  else
    warn "Cron jobs.json is not symlinked (changes won't be tracked)"
  fi

  # Check personal config files
  for f in AGENTS.md SOUL.md form-fields.md search-rotation.md company-watchlist.md \
           ats-reference.md HEARTBEAT.md; do
    if [ -f "$WORKSPACE/$f" ]; then
      ok "$f exists"
    else
      err "$f missing — run ./setup.sh to create from template"
      errors=$((errors + 1))
    fi
  done

  for f in form-filler.js search-connections.py; do
    if [ -f "$WORKSPACE/scripts/$f" ]; then
      ok "scripts/$f exists"
    else
      err "scripts/$f missing — run ./setup.sh to create from template"
      errors=$((errors + 1))
    fi
  done

  # Check .env
  if [ -f "$SCRIPT_DIR/.env" ]; then
    ok ".env exists"
  else
    err ".env missing — copy from .env.example"
    errors=$((errors + 1))
  fi

  # Check resume
  if ls "$WORKSPACE/resume/"*.pdf &>/dev/null 2>&1; then
    ok "Resume PDF found in workspace/resume/"
  else
    warn "No resume PDF in workspace/resume/ — agents won't be able to upload"
  fi

  echo ""
  if [ $errors -eq 0 ]; then
    echo -e "${GREEN}All checks passed!${NC}"
  else
    echo -e "${RED}$errors issue(s) found.${NC} Run ./setup.sh to fix."
  fi
  exit $errors
fi

# ---------------------------------------------------------------------------
# Main setup
# ---------------------------------------------------------------------------
echo "=== JobHunt Agent Setup ==="
echo ""

# Step 1: Create personal config files from templates
if [ "$1" != "--link" ]; then
  echo "[1/4] Creating config files from templates..."

  # Workspace config files
  copy_template "$WORKSPACE/AGENTS.md.example" "$WORKSPACE/AGENTS.md" "workspace/AGENTS.md"
  copy_template "$WORKSPACE/SOUL.md.example" "$WORKSPACE/SOUL.md" "workspace/SOUL.md"
  copy_template "$WORKSPACE/form-fields.md.example" "$WORKSPACE/form-fields.md" "workspace/form-fields.md"
  copy_template "$WORKSPACE/search-rotation.md.example" "$WORKSPACE/search-rotation.md" "workspace/search-rotation.md"
  copy_template "$WORKSPACE/company-watchlist.md.example" "$WORKSPACE/company-watchlist.md" "workspace/company-watchlist.md"
  copy_template "$WORKSPACE/ats-reference.md.example" "$WORKSPACE/ats-reference.md" "workspace/ats-reference.md"
  copy_template "$WORKSPACE/HEARTBEAT.md.example" "$WORKSPACE/HEARTBEAT.md" "workspace/HEARTBEAT.md"

  # Script config files
  copy_template "$WORKSPACE/scripts/form-filler.js.example" "$WORKSPACE/scripts/form-filler.js" "scripts/form-filler.js"
  copy_template "$WORKSPACE/scripts/search-connections.py.example" "$WORKSPACE/scripts/search-connections.py" "scripts/search-connections.py"
  copy_template "$WORKSPACE/scripts/ats-notes.md.example" "$WORKSPACE/scripts/ats-notes.md" "scripts/ats-notes.md"

  # .env
  copy_template "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env" ".env"

  # Cron config
  mkdir -p "$SCRIPT_DIR/cron"
  copy_template "$SCRIPT_DIR/cron/jobs.json.example" "$SCRIPT_DIR/cron/jobs.json" "cron/jobs.json"

  # Create empty runtime files if they don't exist
  for f in job-queue.md job-tracker.md dedup-index.md manual-dedup.md; do
    if [ ! -f "$WORKSPACE/$f" ]; then
      touch "$WORKSPACE/$f"
      ok "Created empty $f"
    fi
  done

  echo ""
fi

# Step 2: Check OpenClaw is installed
echo "[2/4] Checking OpenClaw installation..."
if [ -d "$OPENCLAW_DIR" ]; then
  ok "OpenClaw config dir exists: $OPENCLAW_DIR"
else
  err "OpenClaw not installed. Install it first: https://github.com/nichochar/openclaw"
  echo "  After installing, run this script again."
  exit 1
fi

# Step 3: Create symlinks
echo "[3/4] Setting up symlinks..."

# Workspace symlink
if [ -L "$OPENCLAW_WORKSPACE" ]; then
  current_target=$(readlink "$OPENCLAW_WORKSPACE")
  if [ "$current_target" = "$WORKSPACE" ]; then
    ok "Workspace symlink already correct"
  else
    warn "Workspace symlink points to: $current_target"
    echo "       Updating to: $WORKSPACE"
    rm "$OPENCLAW_WORKSPACE"
    ln -s "$WORKSPACE" "$OPENCLAW_WORKSPACE"
    ok "Workspace symlink updated"
  fi
elif [ -d "$OPENCLAW_WORKSPACE" ]; then
  echo ""
  echo "  WARNING: $OPENCLAW_WORKSPACE is a real directory."
  echo "  This will be backed up to $OPENCLAW_WORKSPACE.bak"
  read -p "  Continue? (y/N) " confirm
  if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
    mv "$OPENCLAW_WORKSPACE" "$OPENCLAW_WORKSPACE.bak"
    ln -s "$WORKSPACE" "$OPENCLAW_WORKSPACE"
    ok "Workspace backed up and symlinked"
  else
    err "Aborted. Move/backup the workspace manually, then re-run."
    exit 1
  fi
else
  ln -s "$WORKSPACE" "$OPENCLAW_WORKSPACE"
  ok "Workspace symlinked: $OPENCLAW_WORKSPACE → $WORKSPACE"
fi

# Cron symlink
mkdir -p "$OPENCLAW_CRON"
if [ -f "$SCRIPT_DIR/cron/jobs.json" ]; then
  if [ -L "$OPENCLAW_CRON/jobs.json" ]; then
    ok "Cron symlink already exists"
  else
    if [ -f "$OPENCLAW_CRON/jobs.json" ]; then
      cp "$OPENCLAW_CRON/jobs.json" "$OPENCLAW_CRON/jobs.json.bak"
      warn "Backed up existing jobs.json to jobs.json.bak"
    fi
    ln -sf "$SCRIPT_DIR/cron/jobs.json" "$OPENCLAW_CRON/jobs.json"
    ok "Cron symlinked: jobs.json → $SCRIPT_DIR/cron/jobs.json"
  fi
fi

# Step 4: Create required directories
echo "[4/4] Ensuring directories exist..."
mkdir -p "$WORKSPACE/memory" "$WORKSPACE/analysis" "$WORKSPACE/resume"
mkdir -p /tmp/openclaw/uploads
ok "Directories ready"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit workspace/SOUL.md with your background and talking points"
echo "  2. Edit workspace/form-fields.md with your personal details"
echo "  3. Edit workspace/scripts/form-filler.js — update the PROFILE object"
echo "  4. Edit workspace/company-watchlist.md with your target companies"
echo "  5. Edit .env with your Brave Search API key"
echo "  6. Edit cron/jobs.json — update phone numbers and email"
echo "  7. Add your resume PDF to workspace/resume/"
echo "  8. Run: ./start.sh"
echo ""
echo "Verify setup: ./setup.sh --check"
