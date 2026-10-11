"""Installer/documented file lifecycle simulations, never native speech tests.

The real installer and marked documentation blocks run only against temporary
source/HOME/XDG paths. Fake Swift/uname commands prevent real builds or Apple
locale/permission changes. No model, account, actual installed binary, or auth
cache is used. The worktree test clones local Git history into a temporary repo
before creating a worktree, so the user's Git metadata is not changed either.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
INSTALLATION_DOC = ROOT / "docs" / "installation.md"
pytestmark = pytest.mark.skipif(
    not all(path.is_file() for path in (ROOT / "install.sh", ROOT / "whisper-py-convert.py", INSTALLATION_DOC)),
    reason="Installer lifecycle simulations need a full repository checkout, not the Python-only sdist",
)


def _documented_block(name: str) -> str:
    match = re.search(
        rf"<!-- lifecycle: {re.escape(name)} -->\n```sh\n(.*?)\n```",
        INSTALLATION_DOC.read_text(encoding="utf-8"),
        flags=re.DOTALL,
    )
    assert match is not None, f"Missing tested documentation block: {name}"
    return match.group(1)


class Sandbox:
    def __init__(self, root: Path, *, custom_xdg: bool = True):
        self.root = root
        self.source = root / "current source"
        self.source.mkdir()
        # Copies, not edits, of the protected legacy source and real installer.
        for name in ("install.sh", "whisper-py-convert.py"):
            shutil.copy2(ROOT / name, self.source / name)
        self.home = root / "home"
        self.home.mkdir()
        fake_bin = root / "fake toolchain"
        fake_bin.mkdir()
        self.env = {
            "HOME": str(self.home),
            "PATH": f"{fake_bin}:/usr/bin:/bin:/usr/sbin:/sbin",
            "LC_ALL": "C",
            "FAKE_BUILD_VERSION": "before",
            "FAKE_SWIFT_LOG": str(root / "swift-calls.txt"),
            # Avoid global Git hooks/configuration/credential helpers in tests.
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
        }
        if custom_xdg:
            self.env.update(
                XDG_DATA_HOME=str(root / "custom data"),
                XDG_BIN_HOME=str(root / "custom bin"),
                XDG_CACHE_HOME=str(root / "custom cache"),
            )
        self.data = Path(self.env.get("XDG_DATA_HOME", self.home / ".local/share"))
        self.bin = Path(self.env.get("XDG_BIN_HOME", self.home / ".local/bin"))
        self.cache = Path(self.env.get("XDG_CACHE_HOME", self.home / ".cache"))
        self.stt = self.data / "whisper-py-convert"
        self.tts = self.data / "mac-speech"
        self.token = self.home / ".config/mac-speech/gdrive-token.json"
        self.command = self.bin / "whisper-py-convert"
        self._write_executable(fake_bin / "uname", "#!/bin/sh\nprintf 'Darwin\\n'\n")
        self._write_executable(
            fake_bin / "swift",
            """#!/bin/sh
set -eu
package=""
while [ "$#" -gt 0 ]; do
    if [ "$1" = "--package-path" ]; then
        shift
        package="$1"
    fi
    shift
done
test -n "$package"
printf '%s\n' "$package" >> "$FAKE_SWIFT_LOG"
case "$package" in
    */engines/tts-swift) name=mac-speech-tts ;;
    *) name=whisper-py-convert-apple ;;
esac
mkdir -p "$package/.build/release"
printf '#!/bin/sh\n# simulated native build: %s\nexit 0\n' "$FAKE_BUILD_VERSION" > "$package/.build/release/$name"
chmod 755 "$package/.build/release/$name"
""",
        )

    @staticmethod
    def _write_executable(path: Path, content: str) -> None:
        path.write_text(content, encoding="utf-8")
        path.chmod(0o755)

    def run(self, args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess:
        result = subprocess.run(
            args,
            cwd=cwd or self.source,
            env=self.env,
            text=True,
            capture_output=True,
            timeout=60,
        )
        assert result.returncode == 0, f"{args!r}\n{result.stdout}\n{result.stderr}"
        return result

    def install(self, mode: str) -> None:
        self.run(["/bin/sh", str(self.source / "install.sh"), mode])

    def documentation(self, *blocks: str) -> None:
        script = "\n".join(_documented_block(name) for name in ("paths", *blocks))
        self.run(["/bin/sh", "-eu", "-c", script])

    def sentinel(self, path: Path) -> bytes:
        path.parent.mkdir(parents=True, exist_ok=True)
        content = b"synthetic unrelated user data: preserve\n"
        path.write_bytes(content)
        return content


@pytest.mark.parametrize("mode", ["stt", "tts", "all"])
def test_install_modes_always_copy_legacy_wrapper_and_build_only_selected(tmp_path, mode):
    box = Sandbox(tmp_path)
    box.install(mode)
    assert box.command.is_symlink()
    assert box.command.resolve() == box.stt / "whisper-py-convert.py"
    assert (box.stt / "whisper-py-convert.py").read_bytes() == (box.source / "whisper-py-convert.py").read_bytes()
    assert (box.stt / "whisper-py-convert-apple").exists() == (mode in {"stt", "all"})
    assert (box.tts / "mac-speech-tts").exists() == (mode in {"tts", "all"})
    calls = Path(box.env["FAKE_SWIFT_LOG"]).read_text().splitlines()
    assert len(calls) == (2 if mode == "all" else 1)
    if mode == "tts":
        assert calls == [str(box.source / "engines/tts-swift")]


def test_selected_upgrade_replaces_selected_files_but_keeps_other_engine(tmp_path):
    box = Sandbox(tmp_path)
    box.install("all")
    apple_before = (box.stt / "whisper-py-convert-apple").read_bytes()
    old_tts = (box.tts / "mac-speech-tts").read_bytes()
    # Only alter the disposable copied source, not the repository's legacy file.
    with (box.source / "whisper-py-convert.py").open("a") as stream:
        stream.write("\n# simulated new source revision\n")
    box.env["FAKE_BUILD_VERSION"] = "after"
    box.install("tts")
    assert (box.tts / "mac-speech-tts").read_bytes() != old_tts
    assert (box.stt / "whisper-py-convert-apple").read_bytes() == apple_before
    assert (box.stt / "whisper-py-convert.py").read_bytes() == (box.source / "whisper-py-convert.py").read_bytes()
    box.install("tts")  # idempotent copies; not a transactional-upgrade claim
    assert (box.stt / "whisper-py-convert-apple").read_bytes() == apple_before


@pytest.mark.parametrize("custom_xdg", [False, True])
def test_documented_uninstall_preserves_outputs_credentials_and_shared_cache(tmp_path, custom_xdg):
    box = Sandbox(tmp_path, custom_xdg=custom_xdg)
    box.install("all")
    # Explicit custom PID path tests that cleanup does not assume cache defaults.
    pid = box.root / "separate control" / "chosen.pid"
    box.env["MAC_SPEECH_TTS_PID_FILE"] = str(pid)
    box.sentinel(pid)  # no process exists; tests never signal this synthetic file
    preserved = {
        path: box.sentinel(path)
        for path in (
            box.tts / "generated.wav",
            box.stt / "transcript.srt",
            box.cache / "mac-speech" / "workflow.json",
            box.home / ".cache/huggingface/hub/models--shared/sentinel",
            box.token,
            box.home / ".aws/config",
        )
    }
    box.documentation("uninstall-tts")
    assert not (box.tts / "mac-speech-tts").exists()
    assert not pid.exists()
    assert (box.stt / "whisper-py-convert-apple").exists()
    assert box.command.is_symlink()
    box.documentation("uninstall-stt")
    assert not box.command.is_symlink()
    assert not (box.stt / "whisper-py-convert.py").exists()
    assert not (box.stt / "whisper-py-convert-apple").exists()
    for path, content in preserved.items():
        assert path.read_bytes() == content
    # Repeating cleanup is harmless, including rmdir of nonempty/missing dirs.
    box.documentation("uninstall-tts", "uninstall-stt")


def test_stt_uninstall_does_not_remove_replaced_unrelated_command(tmp_path):
    box = Sandbox(tmp_path)
    box.install("stt")
    box.command.unlink()
    content = box.sentinel(box.command)
    box.documentation("uninstall-stt")
    assert box.command.read_bytes() == content


def test_documented_binary_backup_restore_preserves_current_source_and_stt(tmp_path):
    box = Sandbox(tmp_path)
    box.install("all")
    tts_before = (box.tts / "mac-speech-tts").read_bytes()
    dirty = box.sentinel(box.source / "uncommitted-notes.txt")
    token = box.sentinel(box.token)
    output = box.sentinel(box.tts / "generated.wav")
    box.env["BACKUP_DIR"] = str(box.root / "kept binaries")
    box.documentation("backup-installed")
    backup = Path(box.env["BACKUP_DIR"])
    assert {path.name for path in backup.iterdir()} == {
        "mac-speech-tts", "whisper-py-convert.py", "whisper-py-convert-apple"
    }
    assert backup.stat().st_mode & 0o077 == 0
    box.env["FAKE_BUILD_VERSION"] = "after"
    box.install("all")
    apple_after = (box.stt / "whisper-py-convert-apple").read_bytes()
    assert (box.tts / "mac-speech-tts").read_bytes() != tts_before
    box.documentation("restore-tts")
    assert (box.tts / "mac-speech-tts").read_bytes() == tts_before
    assert os.access(box.tts / "mac-speech-tts", os.X_OK)
    assert (box.stt / "whisper-py-convert-apple").read_bytes() == apple_after
    assert (box.source / "uncommitted-notes.txt").read_bytes() == dirty
    assert box.token.read_bytes() == token
    assert (box.tts / "generated.wav").read_bytes() == output
    # Existing backup paths are refused, rather than silently updated in place.
    result = subprocess.run(
        ["/bin/sh", "-eu", "-c", _documented_block("paths") + "\n" + _documented_block("backup-installed")],
        cwd=box.source, env=box.env, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode != 0
    assert (backup / "mac-speech-tts").read_bytes() == tts_before


@pytest.mark.parametrize("token_override", [False, True])
def test_explicit_token_removal_deletes_only_selected_synthetic_token(tmp_path, token_override):
    box = Sandbox(tmp_path)
    box.sentinel(box.token)
    selected = box.token
    if token_override:
        selected = box.root / "custom config" / "chosen-token.json"
        box.env["MAC_SPEECH_GDRIVE_TOKEN"] = str(selected)
        box.sentinel(selected)
    kept = box.home / ".config/mac-speech/unrelated.json"
    content = box.sentinel(kept)
    box.documentation("remove-gdrive-token")
    assert not selected.exists()
    assert kept.read_bytes() == content
    if token_override:
        assert box.token.exists()


def test_documented_previous_worktree_preserves_dirty_and_untracked_source(tmp_path):
    box = Sandbox(tmp_path)
    if shutil.which("git", path=box.env["PATH"]) is None:
        pytest.skip("Git is unavailable for isolated local-worktree simulation")
    git_root = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "--show-toplevel"],
        env=box.env, text=True, capture_output=True, timeout=60,
    )
    if git_root.returncode or Path(git_root.stdout.strip()).resolve() != ROOT:
        pytest.skip("Separate-worktree simulation needs repository Git history, not a source archive")
    history = box.root / "isolated history"
    # Clone only local committed history; no network, commit creation, or changes
    # to the main checkout's worktree registry. The previous revision may predate TTS.
    box.run(["git", "clone", "--local", "--no-hardlinks", str(ROOT), str(history)])
    tracked = history / "install.sh"
    previous_installer = tracked.read_bytes()
    tracked.write_bytes(previous_installer + b"\n# preserve this dirty source\n")
    untracked = history / "untracked-user-notes.txt"
    notes = box.sentinel(untracked)
    status_before = box.run(["git", "status", "--porcelain"], cwd=history).stdout
    box.env["PREVIOUS_REVISION"] = box.run(["git", "rev-parse", "HEAD"], cwd=history).stdout.strip()
    previous = box.root / "previous source"
    box.env["PREVIOUS_SOURCE"] = str(previous)
    box.run(["/bin/sh", "-eu", "-c", _documented_block("previous-worktree")], cwd=history)
    assert (previous / "install.sh").read_bytes() == previous_installer
    assert tracked.read_bytes() == previous_installer + b"\n# preserve this dirty source\n"
    assert untracked.read_bytes() == notes
    assert box.run(["git", "status", "--porcelain"], cwd=history).stdout == status_before
    assert box.run(["git", "symbolic-ref", "-q", "HEAD"], cwd=history).stdout.strip()
    # Execute the previous installer's supported no-argument path using fake
    # Swift only; no claim that this historical commit includes new TTS files.
    box.run(["/bin/sh", str(previous / "install.sh")], cwd=previous)
    assert (box.stt / "whisper-py-convert.py").read_bytes() == (previous / "whisper-py-convert.py").read_bytes()
    assert tracked.read_bytes() == previous_installer + b"\n# preserve this dirty source\n"
