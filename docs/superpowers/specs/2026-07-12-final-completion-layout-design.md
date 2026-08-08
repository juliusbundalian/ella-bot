# Final Completion Layout Design

## Goal

Make the `All Levels Complete` screen visually consistent with the existing
level-completion screen while presenting only cumulative session results.

## Layout

`FinalEvaluationScene` will use the same card frame, ribbon banner, outlined
rating treatment, two-column information area, and button styling used by
`ResultsScene`.

- The ribbon will read `ALL LEVELS` and `COMPLETE!`.
- The left column will show the cumulative overall rating.
- The right column will show first-try score and overall fluency.
- The screen will keep `Play Again` and `Main Menu` actions.
- Per-level/tier rows will be removed.

## Data and Behavior

The scene will use the existing final evaluation result for the rating,
fluency, first-try score, and item total. The app does not currently retain a
session-wide start timestamp, so the screen will not show elapsed time.
Play-again and main-menu behavior will remain unchanged.

## Verification

Add a rendering-focused unit test that verifies the final scene renders the
new two-stat cumulative layout without requiring tier rows. Keep existing
action tests passing and run the final-scene and result-scene test modules.
