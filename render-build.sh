#!/usr/bin/env bash
set -o errexit

# Install Python dependencies
pip install -r requirements.txt

# Install GitHub CLI system-wide
echo "--- Installing GitHub CLI ---"
apt-get update && apt-get install -y gh

