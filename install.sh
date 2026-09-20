#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
INSTALL_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/whisper-py-convert"
BIN_DIR="${XDG_BIN_HOME:-$HOME/.local/bin}"

mkdir -p "$INSTALL_DIR" "$BIN_DIR"
cp "$SCRIPT_DIR/whisper-py-convert.py" "$INSTALL_DIR/whisper-py-convert.py"
chmod 755 "$INSTALL_DIR/whisper-py-convert.py"
ln -sf "$INSTALL_DIR/whisper-py-convert.py" "$BIN_DIR/whisper-py-convert"

echo "Installed whisper-py-convert to $BIN_DIR/whisper-py-convert"
case ":${PATH:-}:" in
  *:"$BIN_DIR":*) ;;
  *) echo "Add this to your shell profile if the command is not found:"; echo "  export PATH=\"$BIN_DIR:\$PATH\"" ;;
esac
