#!/usr/bin/env bash
# Native TTS only. Never use/delete the repository .build or shared user caches.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ "$(uname -s)" != Darwin ]]; then
    echo 'Native TTS CI requires macOS.' >&2
    exit 1
fi

swift_version="$(swift --version)"
echo "$swift_version"
if ! grep -Eq 'Swift version 6\.4([.]|[[:space:]]|$)' <<< "$swift_version"; then
    echo 'Select a Swift 6.4.x toolchain and compatible macOS SDK before running this check.' >&2
    exit 1
fi

temp_parent="${RUNNER_TEMP:-${TMPDIR:-}}"
if [[ -z "$temp_parent" || ! -d "$temp_parent" ]]; then
    echo 'Set RUNNER_TEMP or TMPDIR to an existing writable temporary directory.' >&2
    exit 1
fi
work_dir="$(mktemp -d "${temp_parent%/}/mac-speech-swift-ci.XXXXXX")"
trap 'rm -rf "$work_dir"' EXIT

# Separate debug/release scratch spaces reduce risk #17's interleaved-build
# TestingMacros/module-cache failure. Disable shared manifest caching, too.
# No external Swift dependencies exist, so neither command needs the network.
run_test() {
    local scratch_name="$1"
    shift
    swift test \
        --package-path "$repo_root/engines/tts-swift" \
        --scratch-path "$work_dir/$scratch_name" \
        --cache-path "$work_dir/$scratch_name-cache" \
        --manifest-cache none \
        --skip-update "$@"
}

if run_test debug > "$work_dir/test.log" 2>&1; then
    cat "$work_dir/test.log"
else
    status="$?"
    if grep -Eq "plugin for module 'TestingMacros' not found|external macro implementation type 'TestingMacros[.].*could not be found" "$work_dir/test.log"; then
        echo 'Known TestingMacros failure; retrying once with fresh scratch and cache directories.' >&2
        tail -n 30 "$work_dir/test.log" >&2
        # CLT-only Swift 6.4 can intermittently omit this installed plugin
        # from the compiler's load list. Derive its location from the selected
        # toolchain, never assume a machine-specific installation path.
        # Do not retry test assertions, generic compilation errors, or release builds.
        compiler_path="$(xcrun --find swiftc)"
        compiler_usr="$(cd "$(dirname "$compiler_path")/.." && pwd)"
        testing_plugin="$compiler_usr/lib/swift/host/plugins/testing/libTestingMacros.dylib"
        if [[ -f "$testing_plugin" ]]; then
            echo "Explicitly loading the selected toolchain's TestingMacros plugin: $testing_plugin" >&2
            run_test debug-retry -Xswiftc -load-plugin-library -Xswiftc "$testing_plugin"
        else
            run_test debug-retry
        fi
    else
        cat "$work_dir/test.log" >&2
        exit "$status"
    fi
fi
swift build \
    --package-path "$repo_root/engines/tts-swift" \
    --configuration release \
    --scratch-path "$work_dir/release" \
    --cache-path "$work_dir/release-cache" \
    --manifest-cache none \
    --skip-update
