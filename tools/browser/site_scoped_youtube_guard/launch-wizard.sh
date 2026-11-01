#!/bin/sh
# Run as a normal user, not root. Admin policy installation is a separate step.
set -eu
cd "$(dirname "$0")"
exec python3 wizard.py
