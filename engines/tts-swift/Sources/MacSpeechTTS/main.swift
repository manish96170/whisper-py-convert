import Foundation
import MacSpeechTTSCore

// Thin executable shell: all logic lives in MacSpeechTTSCore so it can be
// unit- and integration-tested directly (see Tests/MacSpeechTTSCoreTests),
// without spawning a subprocess per test case.
exit(run(arguments: Array(CommandLine.arguments.dropFirst())))
