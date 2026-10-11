import Foundation
import NaturalLanguage

/// Splits text into sentences using `NLTokenizer`, which correctly handles
/// abbreviations, decimals, and punctuation (verified against "Dr. Smith
/// paid $3.50 for it, e.g. a reasonable price." during Phase 2 discovery —
/// it does not split mid-abbreviation).
///
/// Sentence-level chunking is not an optional nicety here: see
/// docs/tts-engine.md for a reproduced bug where
/// `AVSpeechSynthesizer.write(_:toBufferCallback:)` silently stops producing
/// real speech after the first sentence of a multi-sentence utterance on
/// this macOS version, while still emitting a plausible-length tail of
/// audio. Synthesizing one sentence per `AVSpeechUtterance`/
/// `AVSpeechSynthesizer` instance and concatenating the results is the
/// verified workaround, so `runSave` and `runSpeak` both always chunk by
/// sentence rather than treating it as an optional "long text" code path.
public func splitIntoSentences(_ text: String) -> [String] {
    let tokenizer = NLTokenizer(unit: .sentence)
    tokenizer.string = text
    var sentences: [String] = []
    tokenizer.enumerateTokens(in: text.startIndex..<text.endIndex) { range, _ in
        let sentence = String(text[range]).trimmingCharacters(in: .whitespacesAndNewlines)
        if !sentence.isEmpty {
            sentences.append(sentence)
        }
        return true
    }
    if sentences.isEmpty {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? [] : [trimmed]
    }
    return sentences
}
