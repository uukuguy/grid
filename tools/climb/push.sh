#!/usr/bin/env bash
set -euo pipefail

RUN_DIR=${1:?usage: push.sh RUN_DIR}
cp "$RUN_DIR/manifest.json" "$RUN_DIR/candidate-climb.json"
echo "[climb] local candidate recorded: $RUN_DIR/candidate-climb.json"
