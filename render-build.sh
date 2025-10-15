#!/usr/bin/env bash
# exit on error
set -o errexit

# Install Python dependencies
pip install -r requirements.txt

# Manually download and install the GitHub CLI into a local 'bin' directory
echo "--- Installing GitHub CLI ---"
curl -L https://github.com/cli/cli/releases/download/v2.40.1/gh_2.40.1_linux_amd64.tar.gz -o gh.tar.gz
tar -xf gh.tar.gz
mkdir -p bin
mv gh_*/bin/gh bin/
rm -rf gh_* gh.tar.gz
