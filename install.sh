#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
INSTALL_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/whisper-py-convert"
BIN_DIR="${XDG_BIN_HOME:-$HOME/.local/bin}"

mkdir -p "$INSTALL_DIR" "$BIN_DIR"
cp "$SCRIPT_DIR/whisper-py-convert.py" "$INSTALL_DIR/whisper-py-convert.py"
chmod 755 "$INSTALL_DIR/whisper-py-convert.py"

if [ "$(uname -s)" = "Darwin" ] && command -v swift >/dev/null 2>&1; then
  printf '%s\n' "Building Apple Speech backend..."
  if swift build --configuration release --package-path "$SCRIPT_DIR"; then
    APPLE_BINARY=""
    for candidate in \
      "$SCRIPT_DIR/.build/out/Products/Release/whisper-py-convert-apple" \
      "$SCRIPT_DIR/.build/release/whisper-py-convert-apple" \
      "$SCRIPT_DIR/.build/arm64-apple-macosx/release/whisper-py-convert-apple"; do
      if [ -x "$candidate" ]; then
        APPLE_BINARY="$candidate"
        break
      fi
    done
    if [ -n "$APPLE_BINARY" ]; then
      cp "$APPLE_BINARY" "$INSTALL_DIR/whisper-py-convert-apple"
      chmod 755 "$INSTALL_DIR/whisper-py-convert-apple"
    else
      printf '%s\n' "Warning: Swift build succeeded but release binary was not found." >&2
    fi
  else
    printf '%s\n' "Warning: Apple backend could not be built; faster-whisper remains available." >&2
  fi
fi
ln -sf "$INSTALL_DIR/whisper-py-convert.py" "$BIN_DIR/whisper-py-convert"

echo "Installed whisper-py-convert to $BIN_DIR/whisper-py-convert"
case ":${PATH:-}:" in
  *:"$BIN_DIR":*) ;;
  *) echo "Add this to your shell profile if the command is not found:"; echo "  export PATH=\"$BIN_DIR:\$PATH\"" ;;
esac
