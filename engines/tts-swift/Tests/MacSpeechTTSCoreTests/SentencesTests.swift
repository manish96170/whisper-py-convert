import Testing
@testable import MacSpeechTTSCore

@Suite struct SentencesTests {
    @Test func splitsOnTerminalPunctuation() {
        let sentences = splitIntoSentences("First one here. Second one here! Third one here?")
        #expect(sentences == ["First one here.", "Second one here!", "Third one here?"])
    }

    @Test func doesNotSplitOnAbbreviationsOrDecimals() {
        let sentences = splitIntoSentences("Dr. Smith paid $3.50 for it, e.g. a reasonable price.")
        #expect(sentences.count == 1)
    }

    @Test func doesNotSplitOnSemicolonsColonsOrParentheses() {
        let text = "Punctuation such as commas, periods, and semicolons; colons: and parentheses (like this) do not cause splits."
        #expect(splitIntoSentences(text).count == 1)
    }

    @Test func emptyTextProducesNoSentences() {
        #expect(splitIntoSentences("") == [])
        #expect(splitIntoSentences("   \n\t  ") == [])
    }

    @Test func singleShortPhraseWithNoPunctuationIsOneSentence() {
        #expect(splitIntoSentences("hello there") == ["hello there"])
    }

    @Test func newlineSeparatedSentencesAreSplit() {
        let sentences = splitIntoSentences("Sentence one.\nSentence two.")
        #expect(sentences.count == 2)
    }
}
