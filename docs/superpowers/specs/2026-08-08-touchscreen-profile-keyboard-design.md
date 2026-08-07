# Touchscreen Profile Keyboard Design

## Goal

Allow a learner to create or rename a profile using only ELLA's touchscreen, without requiring a physical keyboard or relying on Raspberry Pi OS to display an external on-screen keyboard.

## Root Cause

`ProfilesScene` calls `pygame.key.start_text_input()` when its Create or Rename modal opens. This enables Pygame `TEXTINPUT` events, but on the Raspberry Pi's Wayland/labwc desktop it does not reliably request or display Squeekboard. ELLA also runs fullscreen, so explicitly launching Squeekboard could cover the lower part of the profile modal instead of safely resizing the application.

## Scope

This change adds an embedded touchscreen keyboard to the existing Create Profile and Rename Profile modals. It does not change profile persistence, validation rules, profile limits, or other scenes. Physical keyboard input remains supported.

## User Experience

Opening Create Profile or Rename Profile displays the name field, an embedded QWERTY keyboard, and the existing primary and Cancel actions in one modal.

The keyboard provides:

- Letter keys in QWERTY order.
- A Shift key that toggles the letter keys between lowercase and uppercase.
- Space, apostrophe, and hyphen keys.
- A Backspace key.

Touching a character key appends that character to the profile name. Backspace removes the final character. Input stops at the existing 20-character limit. Create, Save, Cancel, Enter, and Escape retain their current meanings.

The keyboard appears only while the Create or Rename modal is open. Confirmation and warning modals do not display it.

## Architecture

### On-screen keyboard component

Add a reusable Pygame component under `src/ella_bot/ui/pygame_gui/components/`. It owns:

- The keyboard layout and responsive key rectangles.
- Shift state.
- Pressed-key visual state.
- Pointer down/up hit testing.
- Rendering key labels and button states.

The component reports semantic actions such as a character, `backspace`, or `shift`. It does not read or modify profiles and does not own the name string.

### Profiles scene integration

`ProfilesScene` owns the entered name and applies keyboard actions:

- Character action: append when the result is at most 20 characters.
- Backspace action: remove the final character.
- Shift action: handled by the keyboard component.

The scene continues to process Pygame `TEXTINPUT` and `KEYDOWN` events so a physical keyboard remains usable. Opening either name modal resets the embedded keyboard to lowercase. Closing the modal clears any pressed key state.

### Modal layout

The name modal grows vertically within the existing full-screen card. The title, prompt, and input field remain at the top; the keyboard occupies the middle; Create/Save and Cancel remain visible below it. Keyboard dimensions derive from the modal rectangle so all rows and actions remain inside the screen at the configured 1280x720 resolution.

## Input Flow

1. The user touches Create Profile or Rename.
2. `ProfilesScene` opens the name modal and resets keyboard state.
3. Pointer events are offered to modal action buttons and the embedded keyboard.
4. A completed keyboard tap returns one semantic action to the scene.
5. The scene updates `name_input` and clears any stale validation error.
6. Create or Save uses the existing application service and validation path.
7. Success closes the modal; validation or storage errors remain visible without losing the entered name.

Only a press and release on the same key activates it. Sliding or releasing outside the pressed key cancels the action, matching the existing button behavior.

## Error Handling

- Characters beyond the 20-character limit are ignored.
- Empty, duplicate, non-printable, and storage errors continue through `ProfileStore` and remain visible in the modal.
- Unsupported pointer events are ignored.
- The component exposes no subprocess or desktop-service dependency, so a missing or disabled Raspberry Pi OS keyboard cannot break profile creation.

## Testing

Component tests will verify:

- Key layout and hitboxes are produced within the supplied keyboard rectangle.
- Press/release on the same character emits that character.
- Releasing outside a key emits no action.
- Shift changes letter case.
- Space, apostrophe, hyphen, and Backspace emit the correct actions.

Profile scene tests will verify:

- Touch input updates Create and Rename names.
- Backspace removes one character.
- Touch input respects the 20-character limit.
- Opening a name modal resets keyboard state.
- Closing or leaving the modal clears pressed state.
- Existing Pygame text and physical-keyboard behavior still works.
- Save, validation-error, and Cancel flows remain unchanged.

The full `tests/` suite will be run after implementation.

## Out of Scope

- Launching or configuring Squeekboard, `wvkbd`, or Matchbox Keyboard.
- General-purpose text entry outside the profile scene.
- Symbols beyond apostrophe and hyphen.
- Keyboard localization, suggestions, autocorrect, or swipe input.
- Changes to profile-name validation or its 20-character limit.
