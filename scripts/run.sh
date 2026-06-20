#!/bin/bash
# Job script for the scaled Continuum reproduction.

set -euo pipefail

cd /home/user

bash scripts/reproduce.sh
python validate.py --compare
