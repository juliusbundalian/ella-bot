from __future__ import annotations

from ella_bot.validation.feedback import FeedbackResult
from ella_bot.validation.validators import ValidationResult


def render_result(
	expected_sentence: str,
	spoken_sentence: str,
	highlighted_expected: str,
	validation: ValidationResult,
	feedback: FeedbackResult,
) -> str:
	lines = [
		"=== E.L.L.A. Reading Check ===",
		f"Expected: {expected_sentence}",
		f"Spoken:   {spoken_sentence}",
		f"Target with highlights: {highlighted_expected}",
		f"Accuracy: {validation.accuracy * 100:.1f}%",
		f"WER: {validation.wer:.2f}",
		"",
		f"Feedback: {feedback.level_message}",
	]

	if feedback.detailed_messages:
		lines.append("Details:")
		lines.extend([f"- {msg}" for msg in feedback.detailed_messages])

	if feedback.pronunciation_hints:
		lines.append("Pronunciation support:")
		lines.extend([f"- {hint}" for hint in feedback.pronunciation_hints])

	return "\n".join(lines)
