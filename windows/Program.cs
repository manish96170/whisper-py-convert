using Microsoft.Windows.AI;
using Microsoft.Windows.AI.Speech;

if (args.Length == 0 || args is ["--help"])
{
    Console.Error.WriteLine("Usage: whisper-py-convert-windows.exe recording.wav");
    Console.Error.WriteLine("Uses Windows AI Speech Recognition on-device.");
    return args.Length == 0 ? 2 : 0;
}

var input = Path.GetFullPath(args[0]);
if (!File.Exists(input))
{
    Console.Error.WriteLine($"Input file does not exist: {input}");
    return 2;
}

try
{
    if (SpeechRecognitionModel.GetReadyState() != AIFeatureReadyState.Ready)
    {
        Console.Error.WriteLine("Preparing the Windows speech model...");
        await SpeechRecognitionModel.EnsureReadyAsync();
    }

    var modelResult = await SpeechRecognitionModel.TryCreateAsync();
    if (modelResult.SpeechModel is null)
    {
        Console.Error.WriteLine($"Windows speech model is unavailable: {modelResult.ExtendedError}");
        return 3;
    }

    using var recognition = new BatchRecognition(modelResult.SpeechModel);
    var transcript = await recognition.RecognizeFromFile(input);
    Console.WriteLine(transcript);
    return 0;
}
catch (Exception error)
{
    Console.Error.WriteLine($"Windows AI Speech error: {error.Message}");
    return 1;
}
