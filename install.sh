#!/usr/bin/env bash
# Install this repo as a Hermes Agent skill (devops/litellm-multi-key-gateway).
set -euo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/.hermes/skills/devops/litellm-multi-key-gateway"

mkdir -p "$DEST"
cp -r "$SRC/SKILL.md" "$SRC/templates" "$SRC/references" "$DEST/"
echo "installed -> $DEST"
echo "verify with: skill_view(name='litellm-multi-key-gateway')"
