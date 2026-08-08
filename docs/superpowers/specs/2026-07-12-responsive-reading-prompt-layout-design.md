# Responsive Reading Prompt Layout Design

## Goal

Keep every Level 4 prompt readable and visible by moving long sentences higher and reducing their font size as their wrapped height grows.

## Layout Behavior

The prompt remains horizontally centered. Short prompts retain the current centered placement and font sizes.

For longer prompts, the renderer will:

- choose a smaller font based on the text length;
- measure the wrapped lines in the available prompt rectangle;
- move the text block upward enough to keep its bottom clear of the Ella sprite;
- keep the existing word wrapping and centered alignment.

The renderer will not place text in a separate upper-left column and will not change Ella's size or placement.

## Verification

Add focused tests for the long Level 4 sentence path, confirming that the chosen font is smaller than the regular long-prompt font and that the calculated prompt rectangle ends above the sprite-safe lower boundary. Run the reading-prompt tests and existing GUI scene tests that cover rendering behavior.
