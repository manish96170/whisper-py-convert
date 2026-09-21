# Browser prototype decision

The repository does not currently ship a browser frontend. A browser cannot
directly call Apple SpeechAnalyzer or Windows AI Speech because those native
system APIs are outside the browser sandbox.

The Web Speech API is useful for microphone experiments, but its recognition
engine and offline behavior vary by browser. The `processLocally` option and
language-pack APIs are not available consistently enough to make them the main
upload-recording path.

For a future browser upload tool, the realistic local architecture is:

```text
browser file upload
    -> WebAssembly/WebGPU speech model
    -> transcript/SRT in the browser
```

The current Python `faster-whisper` package cannot be imported directly into a
browser: it depends on Python and native CTranslate2 runtime support. A browser
implementation would need a separately compiled WASM/WebGPU model such as a
whisper.cpp or Transformers.js-compatible model. That is a separate backend,
with its own model download, memory, and browser-compatibility tradeoffs.

Until there is a concrete website integration to target, the native machine
backends and faster-whisper CLI remain the supported product surface.
