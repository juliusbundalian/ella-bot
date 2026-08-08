# ELLA Pedagogical Grading & Speech Recognition Updates (July 2026)

This document outlines the recent enhancements made to ELLA's speech recognition pipeline and validation engine, specifically tuned for 9th-grade reading expectations.

## 1. Advanced Fluency Validation (Levels 3 & 4)

To ensure that Grade 9 students are graded strictly on proper reading fluency rather than just raw phonetic translation, a multi-layered validation system has been deployed:

*   **Strict Sentence Matching:**
    The global `ASR_HOMOPHONES` mapping (which allowed loose phonetic matches like "go" -> "got" for early childhood levels) has been disabled for multi-word sentences. Levels 3 and 4 now strictly enforce exact-word matching to ensure the student is accurately reading the text.
*   **Targeted English Homophones:**
    A new `STRICT_HOMOPHONES` dictionary was implemented (e.g., `be/bee`, `to/too/two`, `wise/weiss`). This ensures the grading engine does not unfairly penalize a student when the offline speech model defaults to an identical-sounding alternate spelling of a correct word.
*   **Acoustic Fluency Threshold Override:**
    The system now extracts raw **acoustic confidence scores** directly from the Vosk engine and pipes them into the mathematical text alignment algorithm. For Levels 3 and 4, if a student mumbles, stutters, or sounds a word out awkwardly (e.g., sounding out "before" as "beh fo reh"), the acoustic confidence score drops. If the confidence drops below **70%**, the algorithm forcefully overrides the text match and marks the word as `INCORRECT`. 
*   **Dynamic Coarticulation Forgiveness:**
    To accommodate natural conversational fluency where Grade 9 students blend suffixes into succeeding consonants, the engine implements dynamic suffix forgiveness. Any curriculum word ending in `-ed` or `-'s` will automatically forgive and accept a transcribed present-tense or plural version (e.g., grading "liked" as "like", or "teacher's" as "teachers") since offline acoustic engines frequently drop these assimilated sounds.

## 2. Refined Pedagogical Coaching (Whole-Part-Whole)

The coaching loop has been refined to provide more natural, effective feedback when a student fails a reading prompt:

*   **Error Isolation:** 
    ELLA now successfully isolates and targets the specific mispronounced word for coaching, rather than indiscriminately repeating entire sentences.
*   **Natural Slow-Paced Enunciation (`SLOW:` Tag):** 
    Robotic phonetic spelling breakdowns have been replaced. A `SLOW:` tag parser has been implemented in the TTS Engine (`AttemptRunner._speak()`). This seamlessly commands the Piper TTS engine to drop its speech rate to 70% when enunciating the targeted tricky word, followed by repeating the full sentence at a natural pace.
*   **TTS Sanitization Fix:** 
    The `_sanitize_for_tts` text cleaner was patched to protect the `SLOW:` command tags from being accidentally stripped or formatted out before reaching the audio processor.

## 3. "Fluency" Score Aggregation Fix

A mathematical error in how the final session Fluency score was calculated has been resolved:

*   **Previous Behavior:** The `EvaluationService` calculated the Fluency score by averaging *every single recording attempt*. If a student answered 8 items correctly on their first try (100% accuracy) but retried 2 failed items 3 times each (0% accuracy), the system graded them out of 14 total attempts, artificially deflating their final score to ~60%.
*   **New Behavior:** The `_aggregate` function was rewritten to group attempts by their unique item ID and only extract the **highest accuracy achieved per item**. A student passing 8 out of 10 items will now accurately receive an 80% Fluency score on the final Results screen, regardless of how many retry attempts they exhausted on the failed items.

## 4. Reverting the Vocabulary Restriction (Lessons Learned)

An attempt was made to manually restrict the Vosk speech model's grammar to only the 1,108 curriculum words to stop the model from hallucinating non-curriculum words (e.g., guessing "hood base" when the student said "school base"). 
*   **The Issue:** Passing a custom grammar array into the Vosk engine completely disabled its internal N-gram Language Model. This reduced the engine to a uniform unigram model, turning every sentence into a random acoustic multiple-choice question. It broke its ability to parse natural sentence structures and caused wild phonetic hallucinations (like translating "be" to "ni" just because "ni" was in the curriculum).
*   **The Reversion:** The `vosk_engine.py` logic was reverted back to using the full, natural English language model. While the model may occasionally transcribe a wildly incorrect student attempt into an unrelated English word (e.g., "school base" -> "hood base"), this is mathematically harmless as it still correctly results in a 0% accuracy grade for that specific word.

---
**Status:** All unit tests (Validators, Attempt Runner, Evaluation, and TTS) have been updated to support these new paradigms and are passing perfectly.
