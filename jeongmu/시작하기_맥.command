#!/bin/bash
cd "$(dirname "$0")"
if ! command -v python3 >/dev/null; then
  echo "Python 3 이 필요합니다: https://www.python.org/downloads/"
  open https://www.python.org/downloads/
  read -p "엔터를 누르면 닫힙니다"
  exit 1
fi
python3 first_run.py
