# Options Page Container Width Design

## Goal

Reduce the standalone Options page card by exactly 120 pixels while keeping it horizontally centered.

## Scope

Change only the main card rendered by `SettingsScene` in `src/ella_bot/ui/pygame_gui/scenes/settings.py`. The in-game `PauseModal`, the card height, vertical position, controls, and content layout remain unchanged.

## Layout

The current card uses 32-pixel left and right margins, giving it a width of `screen_width - 64`. The revised card will use a width of `screen_width - 184`, which is exactly 120 pixels narrower. Its horizontal position will be calculated from the screen center, producing 92-pixel margins on both sides at every supported screen width.

## Implementation

Extract the card rectangle calculation into a small layout helper that returns a `pygame.Rect`. `render()` will use that helper for drawing and positioning the existing content. This makes the width and centering behavior directly testable without changing rendering behavior elsewhere.

## Verification

Add a focused regression test that supplies a representative screen size and verifies:

- the card is exactly 120 pixels narrower than the current layout;
- the card center matches the screen center;
- the existing top margin and height are unchanged.

Run the focused settings-scene tests and the broader relevant test suite after the change.
