# whisper-py-convert

A small standalone command-line wrapper around `faster-whisper==1.2.1`.
It runs locally after the model has been downloaded and supports audio/video
formats that faster-whisper/PyAV can read, including MP3 and MP4.

## Install the command

From this directory:

```sh
./install.sh
```

Then open a new shell, or add `~/.local/bin` to `PATH` as printed by the
installer. The command can then be run from any directory.

## Check installation and models

```sh
whisper-py-convert --check
```

The first invocation installs the exact `faster-whisper==1.2.1` package if it
is missing or a different version is installed. Models are downloaded lazily
when first selected and cached under `~/.cache/huggingface/hub`.

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

Use `--language en` when the recording is known to be English. Omit `.en`
models for multilingual recordings.

## Notes

- `small.en` is the recommended default for English.
- `medium.en` uses more memory and takes longer to load, but can improve
  accuracy.
- Only the selected model is loaded into memory. You can keep both models
  downloaded and switch with `--model`.
- Progress messages go to stderr, leaving stdout clean for transcript output.
