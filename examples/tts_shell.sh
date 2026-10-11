#!/bin/sh
# Example: using `mac-speech tts` from the shell.
#
# Run from the repository root after setting up the venv (see
# python/README.md):
#
#   .venv/bin/activate   # or call .venv/bin/mac-speech directly
#   ./examples/tts_shell.sh
set -eu

MKS="${MAC_SPEECH_BIN:-mac-speech}"

echo "== Doctor and capabilities =="
"$MKS" doctor
"$MKS" capabilities --json | python3 -m json.tool

echo
echo "== List English voices =="
"$MKS" tts voices --language en-US

echo
echo "== Speak a short phrase (blocking) =="
"$MKS" tts speak "Hello from the mac speech toolkit shell example."

echo
echo "== Synthesize to a file =="
mkdir -p examples/output
"$MKS" tts save "This file was produced by the shell example." \
  --output examples/output/shell-example.wav --force

echo
echo "== Background speak + stop from a separate command =="
"$MKS" tts speak "This longer sentence runs long enough that a separate stop command sent a moment later has time to interrupt it before natural completion occurs." &
SPEAK_PID=$!
sleep 1
"$MKS" tts stop
wait "$SPEAK_PID" || true

echo
echo "Done. See examples/output/ for generated audio files."
