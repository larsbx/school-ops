#!/usr/bin/env bash
# Only install missing display executables. Never modify the setup-python interpreter via apt.
set -euo pipefail
probe='import tkinter as tk; root = tk.Tk(); root.update(); print("Tk display ready:", root.tk.call("info", "patchlevel")); root.destroy()'
missing=()
command -v Xvfb >/dev/null || missing+=(xvfb)
command -v xvfb-run >/dev/null || { [[ " ${missing[*]} " == *" xvfb "* ]] || missing+=(xvfb); }
command -v xauth >/dev/null || missing+=(xauth)
if ((${#missing[@]})); then
  for attempt in 1 2 3; do
    if sudo apt-get -o Acquire::Retries=2 -o Acquire::http::Timeout=15 -o Acquire::https::Timeout=15 -o APT::Update::Error-Mode=any update &&
       sudo apt-get -o Acquire::Retries=2 -o Acquire::http::Timeout=15 -o Acquire::https::Timeout=15 install --no-install-recommends -y "${missing[@]}"; then
      break
    fi
    if [[ $attempt == 3 ]]; then exit 1; fi
    sleep "$((attempt * 5))"
  done
fi
python -c 'import sys, tkinter; print(sys.executable, tkinter.TkVersion)'
# A present but unusable display is a hard failure, not an excuse to skip GUI smoke.
xvfb-run -a python -c "$probe"
