# whisper-py-convert

A standalone command-line wrapper with native and portable local transcription backends:

- Apple SpeechAnalyzer/SpeechTranscriber on macOS 27+
- Windows AI Speech on supported Windows 11 24H2+ systems
- `faster-whisper==1.2.1` everywhere else

It supports audio/video formats including MP3 and MP4.

## Install the command

From this directory:

```sh
./install.sh
```

On macOS 27+, the installer also builds the native Apple Speech backend. On
other systems it installs the Python wrapper only; faster-whisper is installed
on first use if needed.

Then open a new shell, or add `~/.local/bin` to `PATH` as printed by the
installer. The command can then be run from any directory.

## Check installation and models

```sh
whisper-py-convert --check
```

The first faster-whisper invocation installs the exact `faster-whisper==1.2.1`
package if it is missing or a different version is installed. Whisper models
are downloaded lazily when first selected and cached under
`~/.cache/huggingface/hub`. The Apple backend downloads and manages its own
system speech assets through macOS.

For authenticated Hugging Face downloads, set the token in the environment:

```sh
export HF_TOKEN=hf_your_token_here
whisper-py-convert --model small.en recording.mp3 > transcript.txt
```

The token is passed only to the Hugging Face download client and is never
printed or saved by this tool. It is optional for these public models; it can
help avoid anonymous rate limits, but it does not guarantee a faster network
transfer.

## Transcribe

Print only the transcript to stdout, suitable for shell redirection:

```sh
whisper-py-convert --model small.en recording.mp3 > transcript.txt
whisper-py-convert --model medium.en recording.mp4 > transcript.txt
```

Or let the tool write the file:

```sh
whisper-py-convert --model small.en recording.mp3 --output transcript.txt
```

Choose a backend explicitly:

```sh
whisper-py-convert --engine apple recording.mp4 > transcript.txt
whisper-py-convert --engine windows recording.wav > transcript.txt
whisper-py-convert --engine faster-whisper --model small.en recording.mp4 > transcript.txt
```

`--engine auto` is the default. It uses the Apple backend when the native
binary is installed, then the Windows backend when its helper is installed,
and otherwise uses faster-whisper. Native OS backends do not use `--model`.

## Subtitle timestamps

Segment-level SRT:

```sh
whisper-py-convert recording.mp4 --srt --seg-ts > recording.srt
```

Word-level SRT:

```sh
whisper-py-convert recording.mp4 --srt --word-ts > recording-word.srt
```

`faster-whisper` supplies explicit segment and word timings. Apple’s backend
uses `SpeechTranscriber` audio-time-range attributes for word timings. The
Windows native backend currently returns plain text only, so use
faster-whisper for timed subtitles on Windows.

Use `--language en` when the recording is known to be English. Omit `.en`
models for multilingual recordings.

## Notes

- `small.en` is the recommended default for English.
- `medium.en` uses more memory and takes longer to load, but can improve
  accuracy.
- Apple SpeechAnalyzer processes speech locally with Apple-managed system
  assets. The audio is not sent to Apple servers by the new transcriber API.
- Only the selected model is loaded into memory. You can keep both models
  downloaded and switch with `--model`.
- Progress messages go to stderr, leaving stdout clean for transcript output.

## Project layout

```text
Package.swift                         Swift package for the Apple backend
Sources/WhisperAppleTranscribe/       Swift SpeechAnalyzer CLI
windows/                              Optional Windows AI Speech helper
BROWSER.md                            Deferred browser-local design notes
whisper-py-convert.py                 Cross-platform Python dispatcher
install.sh                            Builds and installs the command
```

The Python dispatcher is intentionally the stable CLI boundary. Future
backends can implement a new `transcribe_with_<engine>` function and be added
to `--engine` without changing the output, redirection, or installation model.
See [ARCHITECTURE.md](ARCHITECTURE.md) for the backend contract and extension
guide.

## Prerequisites

- Python 3.9+ for the Python wrapper and faster-whisper backend
- macOS 27+ and Swift 6/Xcode Command Line Tools for the Apple backend
- Windows 11 24H2+, Windows App SDK, supported hardware, and MSIX packaging for
  the Windows native backend; see [windows/README.md](windows/README.md)
- Network access only when installing packages or downloading first-use model
  assets; transcription itself is local after the assets are installed
