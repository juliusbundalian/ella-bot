# Profiles Carousel Redesign

## Goal

Redesign the Profiles page so its main container matches the standalone Options page and its learner profiles are easier to browse and manage on a touchscreen.

## Scope

The redesign changes `ProfilesScene` presentation, pagination state, and input hitboxes. Profile persistence, the five-profile limit, profile selection behavior, name-entry modals, the touchscreen keyboard, and reset/delete confirmation behavior remain unchanged.

## Main Container

The Profiles page container will match the standalone Options page container:

- fixed width: `720px`;
- horizontally centered at every supported screen width;
- existing height and vertical position retained;
- corner radius: `140px` for the shadow, fill, and border.

The `Who's Learning?` banner remains centered above the content.

## Carousel Model

`ProfilesScene` will own a zero-based `carousel_page` value and show two existing profiles per page. Page count is `ceil(profile_count / 2)`, up to three pages for the existing five-profile limit.

When the scene opens, it selects the page containing the active profile. If there is no active profile, it selects the first page. The page index is always clamped to the available pages after a rename, reset, delete, or profile-list refresh.

Large left and right arrow buttons flank the two-card viewport. Navigation changes pages immediately without animation. The left arrow is disabled on the first page, the right arrow is disabled on the last page, and both are disabled when only one page exists. Disabled arrows remain visible but clearly dimmed and do not create clickable hitboxes.

Visual-only page indicators appear below the cards. One dot is rendered per page, with the current page highlighted. The dots are not interactive. With no profiles, the carousel displays a centered empty-state message, hides the indicators, and disables both arrows.

## Fixed Page Actions

`+ Create Profile` is no longer a carousel card. It occupies a fixed action slot below the indicators and remains visible whenever fewer than five profiles exist. At five profiles, that slot displays the noninteractive status `5 of 5 profiles`.

`+ Create Profile` and `Back to Menu` form a fixed bottom row with equal width, height, corner radius, stroke weight, and font size. Their placement does not change as the carousel page changes.

## Profile Card Design

Every visible profile card has identical dimensions and internal spacing. Each card contains:

1. A profile name in one shared primary font size.
2. A progress summary in one shared secondary font size.
3. A compact `Active` badge and yellow card border when the profile is selected.
4. A management section with three buttons.

The information area above the management section is the profile-selection hitbox. Management buttons have separate hitboxes and never trigger profile selection.

The management section uses two rows:

- `Rename` spans the full top row.
- `Reset` and `Delete` occupy equal halves of the bottom row.

All three buttons use a `40px` height, the same corner radius, stroke weight, and font size. Labels are exactly `Rename`, `Reset`, and `Delete`, preventing per-label text scaling. Rename and Reset use the shared yellow button theme; Delete uses the shared violet button theme. The existing confirmation dialogs continue to provide the full destructive-action wording.

## Interaction and Data Flow

On each render, the scene reads the current profile tuple and active profile from the application, clamps `carousel_page`, slices the tuple to the two visible profiles, and builds hitboxes only for those cards and controls.

Arrow presses update `carousel_page` only when the direction is enabled. Changing pages clears and rebuilds visible profile and management hitboxes during the next render. Selecting a profile continues to persist that selection and return to the Main Menu.

Rename and Reset retain the current carousel page. After Delete, the scene clamps the current page to the new last page before the next render so it cannot show an empty page.

## Error Handling

Profile summary, selection, creation, rename, reset, and delete errors retain their existing behavior. Non-modal errors render above the fixed bottom action row and do not change the current carousel page. Modal errors remain inside their existing dialogs.

## Testing

Focused `ProfilesScene` tests will cover:

- a `720px` container centered on the screen with a `140px` corner radius contract;
- two-profile page slicing and a maximum of three pages;
- opening on the active profile's page;
- disabled first/last arrow behavior and ignored clicks;
- visual indicator count and current-page state;
- the fixed Create Profile action and five-profile capacity status;
- equal profile card dimensions;
- full-width Rename above equal Reset/Delete buttons;
- consistent action height and labels;
- separation of profile-selection and management hitboxes;
- page retention after rename/reset;
- page clamping after deletion;
- the empty-profile state.

Existing profile persistence, touchscreen keyboard, modal, and scene-flow tests will remain green.

## Out of Scope

- Animated slide transitions, swipe gestures, and wraparound navigation.
- Tappable page indicators.
- Changes to the maximum profile count or profile storage format.
- Changes to modal copy, the touchscreen keyboard, or reading-session behavior.
