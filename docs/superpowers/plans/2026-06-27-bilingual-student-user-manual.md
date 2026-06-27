# E.L.L.A. Bilingual Student Manual Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce one 12-page bilingual English–Filipino E.L.L.A. student manual and one one-page bilingual quick-start guide as editable Word documents and print-ready PDFs for Philippine ARAL Program learners from Kindergarten to Grade 10.

**Architecture:** Treat the approved application revision as the sole interface source of truth. Maintain reusable bilingual copy and a revision-linked screenshot manifest, then assemble both Word deliverables from those shared sources and export verified PDFs. Keep release evidence, functional checks, and usability observations beside the manual so future student-facing UI changes can be traced to affected pages.

**Tech Stack:** Markdown and CSV source records; E.L.L.A.'s Pygame interface; PNG screenshots; Microsoft Word `.docx`; PDF; the `documents:documents` skill and its render-and-verify workflow; bundled Python, LibreOffice, and Poppler utilities.

## Global Constraints

- The manual serves one combined audience from Kindergarten to Grade 10; do not create separate grade-band manuals.
- Every learner-facing instruction must show English first and natural Filipino immediately below it.
- Preserve visible E.L.L.A. interface labels in English inside both language blocks.
- Keep one action per sentence and prefer sentences of 10 words or fewer.
- Use supportive, non-stigmatizing wording; describe retries as practice.
- The full manual must be 12 A4 portrait pages; the quick-start guide must be one A4 page.
- Deliver each artifact as an editable `.docx` and print-ready `.pdf`.
- Use only screenshots captured from the approved release revision at the deployed display resolution, expected to be 1280×720 unless the release audit records another resolution.
- Do not modify application code, student level content, scoring, speech behavior, or user-owned configuration as part of this documentation plan.
- Do not publish while the release audit, functional verification, print check, or required usability checks contain an unresolved release-blocking result.
- Use `/Users/juliusjervinbundalian/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3` for document utilities and add `/Users/juliusjervinbundalian/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin` to `PATH` for PDF utilities.
- Preserve the user's existing changes in `.claude/settings.json`, `config/level_pools.json`, `config/settings.ini`, `.codex/`, and `AGENTS.md`.

---

## Planned File Structure

```text
docs/user-manual/
├── README.md
├── content/
│   └── bilingual-copy.md
├── assets/
│   └── screenshots/
│       ├── intro.png
│       ├── main-menu.png
│       ├── exit-confirmation.png
│       ├── settings.png
│       ├── reset-progress-confirmation.png
│       ├── reading-screen.png
│       ├── state-speaking.png
│       ├── state-listening.png
│       ├── state-processing.png
│       ├── state-success.png
│       ├── state-retry.png
│       ├── options.png
│       ├── restart-level-confirmation.png
│       ├── back-to-menu-confirmation.png
│       ├── result-sublevel-pass.png
│       ├── result-tier-pass.png
│       ├── result-fail.png
│       ├── result-menu-choice.png
│       └── final-evaluation.png
├── source/
│   ├── ELLA-Student-User-Manual.docx
│   └── ELLA-Quick-Start-Guide.docx
├── output/
│   ├── ELLA-Student-User-Manual.pdf
│   └── ELLA-Quick-Start-Guide.pdf
└── qa/
    ├── release-audit.md
    ├── screenshot-manifest.csv
    ├── functional-verification.md
    ├── print-check.md
    ├── usability-observations.csv
    └── usability-summary.md
```

Rendered page images belong in `/tmp/ella-user-manual-render/` and must not be committed.

---

### Task 1: Establish the Publication Baseline

**Files:**
- Create: `docs/user-manual/qa/release-audit.md`
- Reference: `docs/superpowers/specs/2026-06-27-student-user-manual-design.md`
- Reference: `config/level_pools.json`
- Reference: `config/settings.ini`
- Test: `tests/`

**Interfaces:**
- Consumes: the application revision selected for deployment, the target display resolution, the complete project test suite, and explicit owner decisions about Level 1A content and default settings.
- Produces: a release audit with `Status: APPROVED FOR DOCUMENTATION`, an exact 40-character Git revision, an exact resolution, test evidence, and any explicitly accepted exceptions.

- [ ] **Step 1: Record the current repository evidence without changing it**

Run:

```bash
git rev-parse HEAD
git status --short
git diff -- config/level_pools.json config/settings.ini
```

Expected: the revision prints as a 40-character hash. Existing user changes remain visible and untouched. Record whether the deployment build includes or excludes those changes.

- [ ] **Step 2: Run the complete suite in the project environment**

Run:

```bash
.venv/bin/python -m pytest -q
```

Expected publication result: exit code 0 with every collected test passing. At the time this plan was written, the command produced 104 passing and 5 failing tests; screenshot production must wait until the owner resolves or explicitly accepts those five failures.

- [ ] **Step 3: Confirm the content and configuration decisions**

Record explicit answers for all four questions in the audit:

1. Is the approved Level 1A pool the committed five vowels or the locally edited `['a', '']` pool?
2. Is the default listening time 5 seconds or 8 seconds?
3. Is the deployed application fullscreen?
4. What exact pixel resolution does the deployed display use?

Expected: each question has one unambiguous answer. An empty Level 1A item cannot be approved accidentally; if it is intentional, the audit must say why and how the blank screen will be documented.

- [ ] **Step 4: Write the release audit**

Create `docs/user-manual/qa/release-audit.md` with this exact structure, replacing each instruction line with the observed value rather than leaving a marker:

```markdown
# E.L.L.A. Student Manual Release Audit

- Status: APPROVED FOR DOCUMENTATION
- Application revision: exact output of `git rev-parse HEAD`
- Deployment resolution: confirmed width × confirmed height
- Test command: `.venv/bin/python -m pytest -q`
- Test result: exact passed/failed summary and exit code
- Level 1A source: committed pool or explicitly approved local pool
- Default listening time: confirmed number of seconds
- Fullscreen: confirmed true or false
- Approved by: project owner role or name supplied during execution
- Approval date: ISO date of approval

## Accepted Exceptions

Write `None.` when all tests pass. Otherwise list each accepted failing test, the observed behavior, why the manual remains accurate, and the owner's acceptance date.

## Screenshot Rule

All screenshots in this manual set must come from the application revision and deployment resolution recorded above.
```

Expected: the file contains no uncertainty words and its status is not approved unless the owner has supplied every decision.

- [ ] **Step 5: Verify the gate**

Run:

```bash
rg -n "Status: APPROVED FOR DOCUMENTATION|Application revision: [0-9a-f]{40}|Deployment resolution: [0-9]+ × [0-9]+" docs/user-manual/qa/release-audit.md
rg -n "unclear|unknown|pending decision" docs/user-manual/qa/release-audit.md
```

Expected: the first command finds all three required records. The second command returns no matches. If the gate cannot pass, stop here and request the missing owner decision; later tasks must not fabricate a baseline.

- [ ] **Step 6: Commit the approved audit**

```bash
git add docs/user-manual/qa/release-audit.md
git commit -m "docs: record student manual release baseline"
```

Expected: the commit contains only the audit file.

---

### Task 2: Create the Shared Bilingual Copy Source

**Files:**
- Create: `docs/user-manual/content/bilingual-copy.md`
- Reference: `docs/superpowers/specs/2026-06-27-student-user-manual-design.md`
- Test: `docs/user-manual/content/bilingual-copy.md`

**Interfaces:**
- Consumes: the approved English–Filipino pattern, the exact UI labels in the release build, and the 12-page information architecture.
- Produces: complete learner-facing copy used verbatim by both Word documents, with screenshot IDs matching Task 3.

- [ ] **Step 1: Create the terminology block**

Start `docs/user-manual/content/bilingual-copy.md` with:

```markdown
# E.L.L.A. Bilingual Student Copy

## Interface Terms

Keep these visible labels in English in both language blocks:

- Start
- Exit
- Settings
- Back
- Options
- Volume
- Listening Time
- Restart Level
- Back to Menu
- Reset Progress
- Score
- Fluency
- Rating
- Continue
- Next Level
- Retry
- Main Menu
- Play Again

## Translation Pattern

English appears first. Filipino appears directly below it. Interface labels stay in English and use bold text.
```

Expected: later Word artifacts can copy interface labels without translating or renaming them.

- [ ] **Step 2: Add Pages 1–4 with exact bilingual copy**

Append:

```markdown
## Page 1 — Using E.L.L.A. / Paggamit ng E.L.L.A.

**Bilingual Student User Manual**  
**Bilingual na Gabay para sa Mag-aaral**

For ARAL Program learners  
Para sa mga mag-aaral ng ARAL Program

## Page 2 — Meet E.L.L.A. / Kilalanin si E.L.L.A.

E.L.L.A. helps you practice reading English aloud.  
Tinutulungan ka ng E.L.L.A. na magsanay bumasa ng Ingles nang malakas.

Sit near the microphone.  
Umupo malapit sa mikropono.

Practice in a quiet place.  
Magsanay sa tahimik na lugar.

Face the device and speak clearly.  
Humarap sa device at magsalita nang malinaw.

Use your natural voice.  
Gamitin ang karaniwan mong boses.

Ask your tutor when you need help.  
Humingi ng tulong sa tutor kung kailangan.

Screenshot: `intro`

## Page 3 — Six Steps / Anim na Hakbang

1. Tap **Start**.  
   Pindutin ang **Start**.
2. Look at the reading text.  
   Tingnan ang babasahin.
3. Listen while E.L.L.A. reads it.  
   Makinig habang binabasa ito ng E.L.L.A.
4. Read aloud when E.L.L.A. listens.  
   Bumasa nang malakas kapag nakikinig na ang E.L.L.A.
5. Wait while E.L.L.A. checks your reading.  
   Maghintay habang sinusuri ng E.L.L.A. ang pagbasa mo.
6. Listen, then retry or continue.  
   Makinig, pagkatapos ay subukan muli o magpatuloy.

Screenshots: `main-menu`, `reading-screen`, `state-speaking`, `state-listening`, `state-processing`, `state-retry`, `result-sublevel-pass`

## Page 4 — Main Menu and Settings / Pangunahing Menu at Settings

Tap **Start** to begin or resume.  
Pindutin ang **Start** para magsimula o magpatuloy.

Tap the gear to open **Settings**.  
Pindutin ang gear para buksan ang **Settings**.

Tap **Exit** to close E.L.L.A.  
Pindutin ang **Exit** para isara ang E.L.L.A.

Tap **Yes** only when you want to exit.  
Pindutin lamang ang **Yes** kung nais mong lumabas.

Tap **Back** to return to the Main Menu.  
Pindutin ang **Back** para bumalik sa Main Menu.

Screenshots: `main-menu`, `exit-confirmation`, `settings`
```

Expected: the first four pages contain the title, preparation, shared six-step flow, and main-menu controls.

- [ ] **Step 3: Add Pages 5–8 with exact bilingual copy**

Append:

```markdown
## Page 5 — Reading Screen / Screen ng Pagbasa

The top label shows your level and item.  
Makikita sa itaas ang iyong level at item.

Read the large text in the middle.  
Basahin ang malaking teksto sa gitna.

Tap the menu button to open **Options**.  
Pindutin ang menu button para buksan ang **Options**.

E.L.L.A. is speaking. Listen first.  
Nagsasalita ang E.L.L.A. Makinig muna.

E.L.L.A. is listening. Read aloud now.  
Nakikinig ang E.L.L.A. Bumasa nang malakas ngayon.

E.L.L.A. is checking. Please wait.  
Sinusuri ng E.L.L.A. ang pagbasa. Maghintay muna.

Do not tap repeatedly while E.L.L.A. works.  
Huwag pindutin nang paulit-ulit habang gumagana ang E.L.L.A.

Screenshots: `reading-screen`, `state-speaking`, `state-listening`, `state-processing`

## Page 6 — Options During Practice / Options Habang Nagsasanay

Tap minus or plus to change **Volume**.  
Pindutin ang minus o plus para baguhin ang **Volume**.

Set **Listening Time** from 5 to 10 seconds.  
Itakda ang **Listening Time** mula 5 hanggang 10 segundo.

Tap the X to continue practicing.  
Pindutin ang X para ipagpatuloy ang pagsasanay.

**Restart Level** begins the current level again.  
Uulitin ng **Restart Level** ang kasalukuyang level mula simula.

**Back to Menu** leaves the reading activity.  
Aalis ang **Back to Menu** sa gawain sa pagbasa.

Check the message before tapping **Yes**.  
Basahin ang mensahe bago pindutin ang **Yes**.

Screenshots: `options`, `restart-level-confirmation`, `back-to-menu-confirmation`

## Page 7 — Feedback and Practice / Payo at Pagsasanay

Wait until E.L.L.A. finishes speaking.  
Hintaying matapos magsalita ang E.L.L.A.

Listen to the sound, word, or sentence.  
Makinig sa tunog, salita, o pangungusap.

Follow E.L.L.A.'s pronunciation tip.  
Sundin ang payo ng E.L.L.A. sa pagbigkas.

Read the same item again when asked.  
Basahin muli ang item kapag sinabi ng E.L.L.A.

Trying again is part of learning.  
Bahagi ng pagkatuto ang pagsubok muli.

Screenshots: `state-success`, `state-retry`

## Page 8 — Your Results / Iyong Resulta

**Score** shows items correct on the first try.  
Ipinapakita ng **Score** ang tamang item sa unang subok.

**Fluency** shows smooth and accurate reading.  
Ipinapakita ng **Fluency** ang maayos at wastong pagbasa.

**Rating** uses A, B, C, D, or F.  
Gumagamit ang **Rating** ng A, B, C, D, o F.

A rating of C or higher lets you continue.  
Makapagpapatuloy ka kapag C o mas mataas ang rating.

Tap **Continue** after a sub-level.  
Pindutin ang **Continue** pagkatapos ng sub-level.

Tap **Next Level** after a full level.  
Pindutin ang **Next Level** pagkatapos ng buong level.

Tap **Retry** for another round of practice.  
Pindutin ang **Retry** para magsanay muli.

Your progress matters more than one rating.  
Mas mahalaga ang pag-unlad mo kaysa sa isang rating.

Screenshots: `result-sublevel-pass`, `result-tier-pass`, `result-fail`, `result-menu-choice`
```

Expected: the copy distinguishes speaking, listening, checking, retry, sub-level continuation, and tier continuation.

- [ ] **Step 4: Add Pages 9–12 and quick-start footer with exact copy**

Append:

```markdown
## Page 9 — Reading Levels / Mga Level sa Pagbasa

Levels 1A–1G: sounds, sound groups, and blends.  
Levels 1A–1G: mga tunog, pinagsamang tunog, at blends.

Levels 2A–2D: common and harder words.  
Levels 2A–2D: karaniwan at mas mahihirap na salita.

Level 3: phrases.  
Level 3: mga parirala.

Level 4: sentences and connected text.  
Level 4: mga pangungusap at magkakaugnay na teksto.

E.L.L.A. remembers completed progress when reopened.  
Naaalala ng E.L.L.A. ang natapos mong progreso kapag binuksan muli.

## Page 10 — Settings and Reset / Settings at Pag-reset

**Volume** has six positions.  
May anim na antas ang **Volume**.

**Listening Time** can be 5 to 10 seconds.  
Maaaring 5 hanggang 10 segundo ang **Listening Time**.

Ask your tutor before resetting progress.  
Magtanong muna sa tutor bago i-reset ang progreso.

**Reset Progress** returns to Level 1A.  
Ibabalik ka ng **Reset Progress** sa Level 1A.

It also removes saved progress.  
Binubura rin nito ang naka-save na progreso.

Tap **No** if you do not want to reset.  
Pindutin ang **No** kung ayaw mong mag-reset.

Screenshots: `settings`, `reset-progress-confirmation`

## Page 11 — Need Help? / Kailangan ng Tulong?

E.L.L.A. did not hear me.  
Hindi ako narinig ng E.L.L.A.

Wait for listening, face the microphone, and speak clearly.  
Hintaying makinig ang E.L.L.A., humarap sa mikropono, at magsalita nang malinaw.

I need more time.  
Kailangan ko ng mas mahabang oras.

Increase **Listening Time** in **Options**.  
Dagdagan ang **Listening Time** sa **Options**.

I cannot hear E.L.L.A.  
Hindi ko marinig ang E.L.L.A.

Increase **Volume** and ask your tutor to check.  
Dagdagan ang **Volume** at magpatulong sa tutor.

E.L.L.A. heard another word.  
Ibang salita ang narinig ng E.L.L.A.

Try again and use your natural voice.  
Subukan muli at gamitin ang karaniwan mong boses.

The screen stopped or showed an error.  
Huminto ang screen o nagpakita ng error.

Stop tapping and ask your tutor for help.  
Huwag muna pindutin at humingi ng tulong sa tutor.

## Page 12 — You Finished! / Natapos Mo!

See your overall rating and fluency.  
Tingnan ang iyong kabuuang rating at fluency.

Tap **Play Again** to return to Level 1A.  
Pindutin ang **Play Again** para bumalik sa Level 1A.

Tap **Main Menu** to return to the menu.  
Pindutin ang **Main Menu** para bumalik sa menu.

Practice helps your reading grow.  
Napauunlad ng pagsasanay ang iyong pagbasa.

Ask Your Tutor  
Humingi ng Tulong sa Tutor

You did meaningful work today.  
Mahalaga ang pagsasanay na ginawa mo ngayon.

Screenshot: `final-evaluation`

## Quick-Start Footer

Use E.L.L.A. in a quiet place.  
Gamitin ang E.L.L.A. sa tahimik na lugar.

Ask your tutor when you need help.  
Humingi ng tulong sa tutor kung kailangan.
```

Expected: the copy source contains all 12 pages and the reusable quick-start footer.

- [ ] **Step 5: Perform bilingual editorial and automated checks**

Check Filipino meaning, interface-label preservation, friendly tone, and destructive-action consequences line by line. Add `Editorial review: APPROVED — reviewer and ISO date` below the document title.

Run:

```bash
rg -n "ASR|TTS|WER|backend|session log|slow learner|weak reader|poor reader" docs/user-manual/content/bilingual-copy.md
rg -n "^## Page ([1-9]|1[0-2])" docs/user-manual/content/bilingual-copy.md | wc -l
```

Expected: the first command returns no matches; the second prints `12`.

- [ ] **Step 6: Commit the bilingual copy**

```bash
git add docs/user-manual/content/bilingual-copy.md
git commit -m "docs: add bilingual student manual copy"
```

Expected: the commit contains only the copy source.

---

### Task 3: Capture and Register the Release Screenshots

**Files:**
- Create: `docs/user-manual/assets/screenshots/*.png`
- Create: `docs/user-manual/qa/screenshot-manifest.csv`
- Reference: `docs/user-manual/qa/release-audit.md`
- Reference: `src/ella_bot/ui/pygame_gui/scenes/`
- Reference: `src/ella_bot/ui/pygame_gui/components/pause_modal.py`

**Interfaces:**
- Consumes: the exact approved revision and display resolution from Task 1.
- Produces: 19 full-screen PNGs and a manifest mapping each screenshot ID to its revision, dimensions, SHA-256 checksum, application state, and manual page.

- [ ] **Step 1: Create the screenshot manifest**

Create `docs/user-manual/qa/screenshot-manifest.csv` with:

```csv
id,file,revision,width,height,state,manual_pages,sha256,verified
```

Expected: exactly nine columns.

- [ ] **Step 2: Capture the 19 required states**

Run the approved build on the deployment device or equivalent display. Capture the full application frame for these exact files in `docs/user-manual/assets/screenshots/`:

```text
intro.png
main-menu.png
exit-confirmation.png
settings.png
reset-progress-confirmation.png
reading-screen.png
state-speaking.png
state-listening.png
state-processing.png
state-success.png
state-retry.png
options.png
restart-level-confirmation.png
back-to-menu-confirmation.png
result-sublevel-pass.png
result-tier-pass.png
result-fail.png
result-menu-choice.png
final-evaluation.png
```

Expected: 19 readable PNGs at the release-audit resolution, with no terminal, mouse pointer over controls, debug output, window border, personal data, or clipped control.

- [ ] **Step 3: Populate exact page mappings and checksums**

Use these mappings:

```text
intro → 1;2
main-menu → 3;4
exit-confirmation → 4
settings → 4;10
reset-progress-confirmation → 10
reading-screen → 3;5
state-speaking → 3;5
state-listening → 3;5
state-processing → 3;5
state-success → 7
state-retry → 3;7
options → 6
restart-level-confirmation → 6
back-to-menu-confirmation → 6
result-sublevel-pass → 3;8
result-tier-pass → 8
result-fail → 8
result-menu-choice → 8
final-evaluation → 12
```

Calculate SHA-256 with `shasum -a 256`; use the same revision and dimensions on every row; set `verified=yes` only after visual comparison with the running state.

- [ ] **Step 4: Verify every asset and manifest row**

Run:

```bash
/Users/juliusjervinbundalian/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -c 'import csv; from pathlib import Path; from PIL import Image; p=Path("docs/user-manual"); rows=list(csv.DictReader((p/"qa/screenshot-manifest.csv").open())); assert len(rows)==19; [Image.open(p/"assets/screenshots"/r["file"]).verify() for r in rows]; assert all(r["verified"]=="yes" for r in rows); print("19 screenshots verified")'
```

Expected: `19 screenshots verified` and exit code 0.

- [ ] **Step 5: Commit the screenshot pack**

```bash
git add docs/user-manual/assets/screenshots docs/user-manual/qa/screenshot-manifest.csv
git commit -m "docs: capture student manual screenshots"
```

Expected: the commit contains 19 PNGs and one CSV manifest.

---

### Task 4: Build the Full Illustrated Word Manual

**Files:**
- Create: `docs/user-manual/source/ELLA-Student-User-Manual.docx`
- Consume: `docs/user-manual/content/bilingual-copy.md`
- Consume: `docs/user-manual/assets/screenshots/*.png`
- Consume: `assets/menu-title.png`
- Test output: `/tmp/ella-user-manual-render/full/`

**Interfaces:**
- Consumes: approved bilingual copy and verified screenshots from Tasks 2 and 3.
- Produces: a 12-page A4 portrait Word document with reusable styles, numbered screenshot callouts, page breaks, accessibility cues, and revision metadata.

- [ ] **Step 1: Load the document-generation instructions**

Invoke `documents:documents` before creating or editing the `.docx`. Load the workspace dependencies and use the bundled document runtime reported by the app.

Expected: the required render-and-verify workflow is active before the artifact is created.

- [ ] **Step 2: Create the document foundation**

Create the DOCX with:

- A4 portrait pages;
- 14 mm left and right margins;
- 13 mm top and bottom margins;
- Arial body text;
- minimum 16 pt English body text;
- minimum 14 pt Filipino body text;
- 24–30 pt page headings;
- dark charcoal text on white;
- E.L.L.A. pink only for headings, borders, callouts, and highlights;
- footer text formed as `E.L.L.A. Student Manual · v1.0 · App ` followed by the first seven characters of the approved revision, then ` · Page X of 12`;
- document title: `Using E.L.L.A. / Paggamit ng E.L.L.A.`.

Define and use these Word styles:

```text
ELLA Cover Title
ELLA Page Title
ELLA English
ELLA Filipino
ELLA Step Number
ELLA Screenshot Caption
ELLA Tip
ELLA Warning
ELLA Footer
```

Expected: the document opens in Word, remains editable, and contains no floating element outside page bounds.

- [ ] **Step 3: Lay out Pages 1–4**

- Page 1: title, subtitle, ARAL audience line, `assets/menu-title.png`, and an E.L.L.A. character crop from `intro.png`.
- Page 2: five preparation instructions, `intro.png`, and an **Ask Your Tutor / Humingi ng Tulong sa Tutor** callout.
- Page 3: six numbered steps in two rows of three using the mapped UI or character image for every step.
- Page 4: annotated Main Menu, exit-confirmation, and Settings screenshots with numbered callouts that do not cover visible labels.

Expected: each page has one dominant task and no more than five non-step callouts.

- [ ] **Step 4: Lay out Pages 5–8**

- Page 5: one large reading screenshot plus speaking, listening, and processing state crops with bilingual state labels.
- Page 6: one large Options screenshot plus restart and back-to-menu confirmations; warnings appear before destructive actions.
- Page 7: success and retry character states with the five approved practice statements.
- Page 8: passing sub-level, passing tier, failing, and menu-choice result crops; connect each button to the exact explanation of Score, Fluency, Rating, Continue, Next Level, Retry, and Main Menu.

Expected: color is never the only distinction between success, retry, warning, and navigation.

- [ ] **Step 5: Lay out Pages 9–12**

- Page 9: four-stage path from Levels 1A–1G to Level 4 using text, numbered stages, and simple shapes.
- Page 10: annotated settings and reset-confirmation screenshots with the reset warning before the action.
- Page 11: five bilingual troubleshooting cards arranged as problem → action.
- Page 12: annotated final-evaluation screenshot, Play Again/Main Menu explanation, tutor-help box, and closing message.

Expected: Page 12 ends the manual without creating a blank thirteenth page.

- [ ] **Step 6: Add accessibility and editing safeguards**

For every screenshot:

- add concise alt text naming the screen and highlighted control;
- place callout numbers in reading order;
- keep normal-text contrast at least 4.5:1;
- pair color with a word, icon, shape, or number;
- preserve sufficient resolution for 100% A4 printing;
- keep text editable instead of flattening a whole page into one image.

Expected: Word users can edit text independently of images and understand states without relying only on color.

- [ ] **Step 7: Render and inspect the DOCX**

Use the `documents:documents` render script to render all pages into `/tmp/ella-user-manual-render/full/`. Inspect all 12 page PNGs individually or as a contact sheet.

Expected: exactly 12 page images; no clipped text, overlaps, blank pages, blurry callouts, widows, or separated bilingual pairs.

- [ ] **Step 8: Verify critical terms in the DOCX**

Run:

```bash
unzip -p docs/user-manual/source/ELLA-Student-User-Manual.docx word/document.xml | rg -o "Start|Listening Time|Restart Level|Reset Progress|Score|Fluency|Rating|Retry|Play Again|Humingi ng Tulong" | sort -u
```

Expected: every listed term appears. Visual review confirms all 12 page headings.

- [ ] **Step 9: Commit the full manual source**

```bash
git add docs/user-manual/source/ELLA-Student-User-Manual.docx
git commit -m "docs: build bilingual student user manual"
```

Expected: the commit contains only the full-manual DOCX.

---

### Task 5: Build the One-Page Quick-Start Word Guide

**Files:**
- Create: `docs/user-manual/source/ELLA-Quick-Start-Guide.docx`
- Consume: `docs/user-manual/content/bilingual-copy.md`
- Consume: mapped PNGs from `docs/user-manual/assets/screenshots/`
- Test output: `/tmp/ella-user-manual-render/quick-start/`

**Interfaces:**
- Consumes: the approved six-step copy and the screenshot pack used by the full manual.
- Produces: a one-page A4 Word guide whose six panels remain readable when posted beside E.L.L.A.

- [ ] **Step 1: Create the one-page layout**

Using `documents:documents`, create:

- A4 portrait with 10 mm margins;
- title: `Six Steps with E.L.L.A. / Anim na Hakbang kasama ang E.L.L.A.`;
- a 2-column × 3-row panel grid;
- one large step number and one cropped image per panel;
- English at 16 pt or larger;
- Filipino at 14 pt or larger;
- the two approved quiet-place and tutor-help footer reminders;
- footer metadata formed as `v1.0 · App ` followed by the first seven characters of the approved revision.

Expected: the title, grid, and footer fit on one page without reducing text below minimum sizes.

- [ ] **Step 2: Populate the six panels with exact copy and images**

```text
1 — Tap Start. / Pindutin ang Start. → main-menu
2 — Look at the reading text. / Tingnan ang babasahin. → reading-screen
3 — Listen while E.L.L.A. reads it. / Makinig habang binabasa ito ng E.L.L.A. → state-speaking
4 — Read aloud when E.L.L.A. listens. / Bumasa nang malakas kapag nakikinig na ang E.L.L.A. → state-listening
5 — Wait while E.L.L.A. checks. / Maghintay habang sinusuri ng E.L.L.A. → state-processing
6 — Retry or continue. / Subukan muli o magpatuloy. → state-retry and result-sublevel-pass
```

Expected: Page 3 of the full manual and the quick-start sequence match word for word.

- [ ] **Step 3: Add visual and accessibility cues**

- Put every step number in a high-contrast circle.
- Add the action word below the number.
- Point to the relevant control without obscuring its label.
- Add alt text for every image.
- Use borders and labels so grayscale printing preserves order and meaning.

Expected: a learner can follow all six panels without relying on pink color.

- [ ] **Step 4: Render and inspect the guide**

Render the DOCX into `/tmp/ella-user-manual-render/quick-start/` using the document workflow.

Expected: exactly one page image, no clipped footer, no split panel, and readable Filipino at 100% view.

- [ ] **Step 5: Commit the quick-start source**

```bash
git add docs/user-manual/source/ELLA-Quick-Start-Guide.docx
git commit -m "docs: build bilingual quick-start guide"
```

Expected: the commit contains only the quick-start DOCX.

---

### Task 6: Export PDFs and Complete Visual and Print QA

**Files:**
- Create: `docs/user-manual/output/ELLA-Student-User-Manual.pdf`
- Create: `docs/user-manual/output/ELLA-Quick-Start-Guide.pdf`
- Create: `docs/user-manual/qa/print-check.md`
- Consume: both DOCX files in `docs/user-manual/source/`
- Test output: `/tmp/ella-user-manual-render/pdf-color/`
- Test output: `/tmp/ella-user-manual-render/pdf-gray/`

**Interfaces:**
- Consumes: visually approved Word documents.
- Produces: print-ready PDFs plus color, grayscale, page-size, text, and physical-print evidence.

- [ ] **Step 1: Export both DOCX files to PDF**

Use the document skill's supported LibreOffice conversion path. Write the two final PDFs with the exact filenames above.

Expected: both PDFs open and contain selectable text.

- [ ] **Step 2: Verify page count and A4 size**

Run:

```bash
export PATH="/Users/juliusjervinbundalian/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin:$PATH"
pdfinfo docs/user-manual/output/ELLA-Student-User-Manual.pdf | rg "Pages:|Page size:"
pdfinfo docs/user-manual/output/ELLA-Quick-Start-Guide.pdf | rg "Pages:|Page size:"
```

Expected: the full manual reports 12 pages and the quick start reports 1 page; each page is approximately 595 × 842 points (A4).

- [ ] **Step 3: Verify searchable bilingual text**

Run:

```bash
pdftotext docs/user-manual/output/ELLA-Student-User-Manual.pdf - | rg "Paggamit ng E.L.L.A.|Pindutin ang Start|Humingi ng Tulong sa Tutor|Reset Progress|Fluency"
pdftotext docs/user-manual/output/ELLA-Quick-Start-Guide.pdf - | rg "Anim na Hakbang|Bumasa nang malakas|Subukan muli o magpatuloy"
```

Expected: every phrase is found. Failure means required text is missing, mistyped, or flattened into an image.

- [ ] **Step 4: Render color and grayscale proof images**

Run:

```bash
mkdir -p /tmp/ella-user-manual-render/pdf-color/full /tmp/ella-user-manual-render/pdf-color/quick /tmp/ella-user-manual-render/pdf-gray/full /tmp/ella-user-manual-render/pdf-gray/quick
pdftoppm -png -r 144 docs/user-manual/output/ELLA-Student-User-Manual.pdf /tmp/ella-user-manual-render/pdf-color/full/page
pdftoppm -png -r 144 docs/user-manual/output/ELLA-Quick-Start-Guide.pdf /tmp/ella-user-manual-render/pdf-color/quick/page
pdftoppm -gray -png -r 144 docs/user-manual/output/ELLA-Student-User-Manual.pdf /tmp/ella-user-manual-render/pdf-gray/full/page
pdftoppm -gray -png -r 144 docs/user-manual/output/ELLA-Quick-Start-Guide.pdf /tmp/ella-user-manual-render/pdf-gray/quick/page
```

Expected: 12 manual images and one quick-start image in each color mode.

- [ ] **Step 5: Inspect every proof image**

Inspect all 26 proofs for clipping, overlap, bilingual-pair order, screenshot/callout association, visible warnings, grayscale distinctions, revision footers, unexpected blank pages, and blurry images.

Expected: all checks pass before physical printing.

- [ ] **Step 6: Complete the physical A4 print check**

Print the quick-start guide and manual Pages 3, 6, 8, 10, and 11 in color and grayscale at 100% scale. Create `docs/user-manual/qa/print-check.md`:

```markdown
# E.L.L.A. Student Manual Print Check

- Printer and paper: actual printer model and A4 paper used
- Print scaling: 100%
- Color pages checked: quick start; full manual pages 3, 6, 8, 10, 11
- Grayscale pages checked: quick start; full manual pages 3, 6, 8, 10, 11
- Smallest text readable at normal distance: yes or no with measured issue
- Screenshot labels readable: yes or no with page and label
- Grayscale controls distinguishable: yes or no with page and control
- Margins complete: yes or no with page
- Status: PASS or FAIL
- Checked by: reviewer
- Date: ISO date
```

Expected: `Status: PASS`. A failed check blocks publication until the affected source and PDFs are regenerated and reinspected.

- [ ] **Step 7: Commit PDFs and print evidence**

```bash
git add docs/user-manual/output docs/user-manual/qa/print-check.md
git commit -m "docs: export and print-check student manuals"
```

Expected: the commit contains two PDFs and one print-check record.

---

### Task 7: Verify Every Documented Action Against E.L.L.A.

**Files:**
- Create: `docs/user-manual/qa/functional-verification.md`
- Consume: `docs/user-manual/source/*.docx`
- Consume: `docs/user-manual/output/*.pdf`
- Consume: the approved release build from Task 1

**Interfaces:**
- Consumes: completed documents and the same application revision used for screenshots.
- Produces: a pass/fail trace for every critical student action and destructive-action warning.

- [ ] **Step 1: Create the functional checklist**

Create rows with columns `Action`, `Manual location`, `Observed app result`, `Pass`, and `Reviewer` for:

```text
Open Settings from the gear
Return with Back
Start or resume a session
Identify the current level and item
Wait during speaking
Read during listening
Wait during processing
Open and close Options
Decrease and increase Volume
Change Listening Time within 5–10 seconds
Cancel Restart Level
Confirm Restart Level
Cancel Back to Menu
Confirm Back to Menu
Respond to success feedback
Respond to retry feedback
Use Continue after a passed sub-level
Use Next Level after a passed tier
Use Retry after a failed result
Choose Continue from the passed-result Main Menu dialog
Choose Restart from the passed-result Main Menu dialog
Cancel Reset Progress
Confirm Reset Progress
Cancel Exit
Confirm Exit
Use Play Again after final evaluation
Use Main Menu after final evaluation
Close and reopen the app to verify resume behavior
```

Expected: 28 rows.

- [ ] **Step 2: Execute the checklist on the approved revision**

Perform each action exactly as written in the manual and record the visible result using exact UI wording. Do not infer behavior from source code.

Expected: every row has `Pass: yes`. A mismatch requires copy or screenshot correction, affected DOCX/PDF regeneration, and repeated visual checks.

- [ ] **Step 3: Verify scoring with a controlled sample**

Run a short sample with at least one first-try correct item and one retried item. Confirm Score, Fluency, Rating, passing buttons, and the failed-result Retry button match the manual definitions.

Expected: all five concepts match the visible results screen.

- [ ] **Step 4: Commit functional evidence**

Add `Status: PASS`, exact app revision, reviewer, and ISO date.

```bash
git add docs/user-manual/qa/functional-verification.md
git commit -m "docs: verify student manual against application"
```

Expected: the commit contains only the functional record.

---

### Task 8: Conduct Cross-Grade ARAL Usability Checks

**Files:**
- Create: `docs/user-manual/qa/usability-observations.csv`
- Create: `docs/user-manual/qa/usability-summary.md`
- Modify when evidence requires it: `docs/user-manual/content/bilingual-copy.md`
- Modify when evidence requires it: both files in `docs/user-manual/source/`
- Modify when evidence requires it: both files in `docs/user-manual/output/`

**Interfaces:**
- Consumes: print-checked materials and representative ARAL learners from Grades 1–3, 4–6, and 7–10.
- Produces: anonymized observations for at least two learners per band, a findings summary, and evidence-backed revisions.

- [ ] **Step 1: Create the anonymized observation sheet**

```csv
participant_code,grade_band,task_id,outcome,prompt_count,used_tutor_read_aloud,issue_severity,observation,revision_action
```

Use participant codes only. Do not record names, learner reference numbers, disability information, assessment scores, or contact details.

Expected: the sheet contains no sensitive student data.

- [ ] **Step 2: Test seven tasks with each learner**

```text
T1 — Start a reading activity from the Main Menu.
T2 — Show when you should listen and when you should read.
T3 — Give yourself more listening time.
T4 — Return to Main Menu without resetting all progress.
T5 — Explain what Retry means.
T6 — Choose the next action on a results screen.
T7 — Find what to do when you need tutor help.
```

Allowed outcomes are `independent`, `one_prompt`, or `demonstration`. A tutor may read words aloud for younger learners but must not point to the correct control unless recording `demonstration`.

Expected: at least 42 rows: 6 learners × 7 tasks.

- [ ] **Step 3: Apply the revision threshold**

Create `usability-summary.md`. Require a revision when:

- two learners in one grade band require demonstration; or
- three learners across all bands make the same navigation or interpretation error.

Record page, current wording or visual, observed difficulty, exact change, and post-change result for every revision.

Expected: younger learners' findings are evaluated as part of the intended tutor-assisted audience.

- [ ] **Step 4: Revise and regenerate affected artifacts**

Change only copy, layout, callout, or screenshot selection needed to resolve evidence. Preserve interface labels and shared six-step wording. Rerender affected Word files, regenerate both PDFs when shared copy changes, repeat Task 6 checks, and rerun affected Task 7 actions.

Expected: every required revision has a passed post-change check.

- [ ] **Step 5: Approve and commit usability results**

End `usability-summary.md` with actual values using this structure:

```markdown
## Outcome

- Grade bands represented: Grades 1–3; Grades 4–6; Grades 7–10
- Learners per band: actual anonymous count
- Required revisions completed: actual count
- Remaining release blockers: None
- Status: PASS
- Reviewed by: reviewer
- Date: ISO date
```

Run:

```bash
git add docs/user-manual/content docs/user-manual/source docs/user-manual/output docs/user-manual/qa/usability-observations.csv docs/user-manual/qa/usability-summary.md
git commit -m "docs: validate student manuals with ARAL learners"
```

Expected: the commit contains anonymized evidence and evidence-backed artifact changes only.

---

### Task 9: Package the Final Manual Set and Maintenance Notes

**Files:**
- Create: `docs/user-manual/README.md`
- Verify: every file under `docs/user-manual/`

**Interfaces:**
- Consumes: the approved audit, bilingual source, screenshots, Word documents, PDFs, print check, functional verification, and usability evidence.
- Produces: a discoverable final package with version metadata and update triggers.

- [ ] **Step 1: Write the package README**

Create:

```markdown
# E.L.L.A. Student Manual Package

This package contains the bilingual English–Filipino E.L.L.A. student manual and one-page quick-start guide for Philippine ARAL Program learners from Kindergarten to Grade 10.

## Student Deliverables

- `source/ELLA-Student-User-Manual.docx` — editable 12-page manual
- `output/ELLA-Student-User-Manual.pdf` — print-ready 12-page manual
- `source/ELLA-Quick-Start-Guide.docx` — editable one-page guide
- `output/ELLA-Quick-Start-Guide.pdf` — print-ready one-page guide

## Supporting Sources

- `content/bilingual-copy.md` — approved English–Filipino copy
- `assets/screenshots/` — release-linked interface screenshots
- `qa/screenshot-manifest.csv` — revision, size, and checksum mapping

## Quality Evidence

- `qa/release-audit.md`
- `qa/print-check.md`
- `qa/functional-verification.md`
- `qa/usability-observations.csv`
- `qa/usability-summary.md`

## Maintenance Triggers

Review affected pages whenever E.L.L.A. changes a visible label, control, screen layout, character state, progression rule, score definition, result button, confirmation dialog, default listening range, or saved-progress behavior. Retake affected screenshots from the new approved revision, update manifest checksums, regenerate both formats when shared copy changes, and repeat QA in proportion to the change.
```

Append the actual manual version, publication date, app revision, deployment resolution, and final PDF SHA-256 checksums.

Expected: a new contributor can find each deliverable and its update rules.

- [ ] **Step 2: Run final package checks**

Run:

```bash
test -f docs/user-manual/source/ELLA-Student-User-Manual.docx
test -f docs/user-manual/source/ELLA-Quick-Start-Guide.docx
test -f docs/user-manual/output/ELLA-Student-User-Manual.pdf
test -f docs/user-manual/output/ELLA-Quick-Start-Guide.pdf
rg -n "Status: PASS" docs/user-manual/qa/print-check.md docs/user-manual/qa/functional-verification.md docs/user-manual/qa/usability-summary.md
git diff --check
```

Expected: all four artifacts exist, all three QA files report PASS, and `git diff --check` prints nothing.

- [ ] **Step 3: Check learner copy for unresolved markers and jargon**

Run:

```bash
rg -n "ASR|TTS|WER|backend|session log|unknown|pending decision" docs/user-manual/content docs/user-manual/README.md
```

Expected: no matches.

- [ ] **Step 4: Verify final PDF metadata and checksums**

Run:

```bash
pdfinfo docs/user-manual/output/ELLA-Student-User-Manual.pdf | rg "Title:|Pages:|Page size:"
pdfinfo docs/user-manual/output/ELLA-Quick-Start-Guide.pdf | rg "Title:|Pages:|Page size:"
shasum -a 256 docs/user-manual/output/*.pdf
```

Expected: titles identify the correct artifacts, counts are 12 and 1, both are A4, and each PDF has a checksum recorded in the README.

- [ ] **Step 5: Commit the final package index**

```bash
git add docs/user-manual/README.md
git commit -m "docs: publish ELLA student manual package"
```

Expected: no unrelated user file is staged.

---

## Final Verification Summary

Before completion, confirm with fresh evidence:

1. The release audit names one approved revision and resolution.
2. Every screenshot row matches that revision and resolution.
3. The full manual renders to exactly 12 A4 pages.
4. The quick-start guide renders to exactly one A4 page.
5. English and Filipino remain selectable in both PDFs.
6. All documented controls work on the approved build.
7. Color and grayscale print checks pass.
8. At least two learners from each grade band complete usability checks, or publication remains blocked.
9. No learner names or sensitive data enter the repository.
10. Existing user changes outside `docs/user-manual/` remain untouched.
