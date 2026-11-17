#!/bin/zsh
# Double-click (macOS) to play in testing mode. Runs from wherever this folder is.
cd "$(dirname "$0")" && exec ./.venv/bin/python -m prism --dev "$@"
