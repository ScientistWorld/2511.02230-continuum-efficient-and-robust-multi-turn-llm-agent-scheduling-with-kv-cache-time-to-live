#!/bin/bash
# Download all data and models needed for this environment.
#
# Estimated total download size: 0 GB
# Estimated disk usage after extraction: 0 GB
#
# The reproduction uses deterministic synthetic traces generated from the
# paper's published workload statistics, so there are no external downloads.

set -euo pipefail

cd /home/user
mkdir -p data/downloads
echo "No external downloads required."
