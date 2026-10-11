#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
INSTALL_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/whisper-py-convert"
BIN_DIR="${XDG_BIN_HOME:-$HOME/.local/bin}"
TTS_INSTALL_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/mac-speech"

# Capability-based install mode: stt, tts, or all (default). See
# docs/installation.md. Lets a user build/install only the capability
# they need without pulling in the other engine's build step.
MODE="${1:-all}"
case "$MODE" in
  stt | tts | all) ;;
  *)
    echo "Usage: ./install.sh [stt|tts|all]" >&2
    echo "  stt  - build/install only the Apple Speech (STT) backend" >&2
    echo "  tts  - build/install only the native TTS engine" >&2
    echo "  all  - build/install both (default)" >&2
    exit 2
    ;;
esac

mkdir -p "$INSTALL_DIR" "$BIN_DIR"
cp "$SCRIPT_DIR/whisper-py-convert.py" "$INSTALL_DIR/whisper-py-convert.py"
chmod 755 "$INSTALL_DIR/whisper-py-convert.py"

if [ "$MODE" = "stt" ] || [ "$MODE" = "all" ]; then
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
  else
    printf '%s\n' "Skipping Apple Speech backend build (requires macOS and Swift); faster-whisper remains available." >&2
  fi
fi

ln -sf "$INSTALL_DIR/whisper-py-convert.py" "$BIN_DIR/whisper-py-convert"

echo "Installed whisper-py-convert to $BIN_DIR/whisper-py-convert"
case ":${PATH:-}:" in
  *:"$BIN_DIR":*) ;;
  *) echo "Add this to your shell profile if the command is not found:"; echo "  export PATH=\"$BIN_DIR:\$PATH\"" ;;
esac

# --- Native TTS engine (independent of the Apple STT backend above; see
# docs/decisions/ADR-001-repository-and-module-boundaries.md) ---------------
if [ "$MODE" = "tts" ] || [ "$MODE" = "all" ]; then
  if [ "$(uname -s)" = "Darwin" ] && command -v swift >/dev/null 2>&1; then
    printf '%s\n' "Building native TTS engine..."
    if swift build --configuration release --package-path "$SCRIPT_DIR/engines/tts-swift"; then
      TTS_BINARY=""
      for candidate in \
        "$SCRIPT_DIR/engines/tts-swift/.build/out/Products/Release/mac-speech-tts" \
        "$SCRIPT_DIR/engines/tts-swift/.build/release/mac-speech-tts" \
        "$SCRIPT_DIR/engines/tts-swift/.build/arm64-apple-macosx/release/mac-speech-tts"; do
        if [ -x "$candidate" ]; then
          TTS_BINARY="$candidate"
          break
        fi
      done
      if [ -n "$TTS_BINARY" ]; then
        mkdir -p "$TTS_INSTALL_DIR"
        cp "$TTS_BINARY" "$TTS_INSTALL_DIR/mac-speech-tts"
        chmod 755 "$TTS_INSTALL_DIR/mac-speech-tts"
        echo "Installed native TTS engine to $TTS_INSTALL_DIR/mac-speech-tts"
      else
        printf '%s\n' "Warning: TTS build succeeded but release binary was not found." >&2
      fi
    else
      printf '%s\n' "Warning: Native TTS engine could not be built; 'mac-speech tts' commands will report it as unavailable." >&2
    fi
  else
    printf '%s\n' "Skipping native TTS engine build (requires macOS and Swift)." >&2
  fi
else
  printf '%s\n' "Skipping native TTS engine (mode=$MODE); 'mac-speech tts' commands will report it as unavailable." >&2
fi

echo ""
echo "To use the mac-speech Python CLI (capabilities, doctor, tts, stt)," \
     "set up its own virtual environment once:"
echo "  cd $SCRIPT_DIR"
echo "  python3 -m venv .venv && .venv/bin/pip install -e \".[dev]\""
echo "  .venv/bin/mac-speech doctor"
echo "This is a separate, optional step; it does not affect whisper-py-convert."
echo ""
echo "See docs/installation.md for upgrade, uninstall, and rollback instructions."
