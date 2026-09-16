# Screen Assistant 0.3.0 verification — 2026-09-16

This update makes images optional. It builds on the previously delivered 0.2.0
repair. The old UI required an image and the old client rejected every text-only
model. Both restrictions have now been changed.

Publication note: machine-specific paths in documentation, historical patches
and logs have been normalized to `/review-workspace` and `/path/to/screen-assistant`.
The paths below represent the original review layout, not directories that must
exist on a developer's machine. The application and test source are unchanged
from the 76-case run. GitHub setup instructions and ignore rules were added for
this repository; no new test run is claimed for those documentation changes.

Work and verification took place at:
`/review-workspace/screen_assistant_repair/project`

The user's reported PC project is `/path/to/screen-assistant`; this review
did not access or modify that directory. Extracting the ZIP creates a separate
`screen-assistant-0.3.0` folder. About identifies the new version.

## Behavior

- With no image, a verified local model with the `completion` capability can
  answer a nonblank question. The request contains text-specific system
  instructions and the current question, with no `images` field.
- With an image, the same model must additionally report `vision`. A text-only
  model is blocked with an explanation; the image is never silently discarded.
- Clear image cancels an active request, discards the image and old answer,
  and keeps the typed question so it can be sent as text.
- Embedding-only, unverified and identified remote models stay blocked.
- Questions remain independent: previous answers and images are not included
  in subsequent text requests. Observation remains off; only geometry persists.
- Text surfaces have explicit foreground/background colors, correcting the
  dark text on dark backgrounds visible in the user's screenshot.

The implementation follows Ollama's documented
[model capabilities](https://docs.ollama.com/api-reference/show-model-details)
and [chat request format](https://docs.ollama.com/api/chat).

## Results

| Check | Test mode | Command or procedure | Result | Evidence |
|---|---|---|---|---|
| Locked install with test extra | Terminal, existing isolated environment | `uv sync --locked --extra test` under a 60-second bound | Passed, exit 0; built 0.3.0 | `evidence/text-questions/locked-sync.log` |
| Normal runtime install | Terminal, existing isolated environment | `timeout 45 uv sync --locked` | Passed, exit 0 | `evidence/text-questions/runtime-sync.log` |
| Runtime import and version | Runtime environment without test extra | Import package and entry point; compare installed metadata version | Passed, exit 0; both versions 0.3.0 | `evidence/text-questions/runtime-import.log` |
| Full regression suite | Offscreen Qt and fake loopback HTTP server | `QT_QPA_PLATFORM=offscreen timeout 45 uv run --locked --extra test python -m pytest -q` | **76 passed in 15.10 seconds**, exit 0 | `evidence/text-questions/pytest.log` |
| Text payloads and model capabilities | Actual Qt client with fake HTTP responses | Text question with both a text model and a vision model; reject image with text-only model; reject embedding-only model | Passed within the 76 cases | Collected tests in `screen_assistant/test_verification.py` |
| Text UI and mode changes | Offscreen widgets and fake server | Ask/Enter without image, blank questions, attach/clear image, cancel, switch model, close, late reply | Passed within the 76 cases | Same suite; requests inspected for absent image/history |
| Existing image workflow | Offscreen widgets and fake server | Load/preview PNG and JPEG; ask, cancel, validate files, restore geometry, About and Quit | Passed within the 76 cases | Same suite; these are not additional test counts |
| Text readability with dark palette | Offscreen render | Simulated dark Fusion palette at 620 × 440; inspect ready and answer views | Inspected; readable in this simulated environment | `evidence/text-questions/offscreen-text-ready-dark-palette.png` and `offscreen-text-answer-dark-palette.png` |
| Third-party dependency pins | Static comparison | Compare all non-project entries in old and new `uv.lock` | All 11 unchanged; only project version changed | Old/new lockfiles in `UPDATE.patch` |
| User's prior image workflow | User report | Latest conversation says image questions now work | User-reported success; no independent performance claim | Conversation |
| New text workflow on user's PC | Live desktop and real Ollama inference | Follow START_HERE; ask without an image, then test an image and return to text | Pending | This environment cannot inspect the user's desktop or Ollama |

The successful suite uses synthetic data and a fake server. It establishes
client behavior, not model answer quality or speed. Neither an offscreen
render nor a running GUI event loop proves a live desktop launch.

## Attempts and environment

- The first `uv lock --offline` attempt failed because Pillow metadata was not
  cached. A bounded ordinary `uv lock` succeeded in 23.09 seconds, updating only
  screen-assistant from 0.2.0 to 0.3.0. No dependency upgrades were introduced.
- An initial direct-venv run also passed all 76 cases before the locked run.
  The locked run above is the reported verification result, not an extra count.
- `QT_QPA_PLATFORM=offscreen` was scoped to tests and rendering. No
  `LD_LIBRARY_PATH` workaround or headless default was added to normal startup.
- Test settings and synthetic images were isolated. No PC settings, services,
  installed models, desktop shortcuts or unrelated files were changed.
- No completed test run timed out. The 180-second model-request deadline and
  non-streaming response behavior remain unchanged; this update does not claim
  to improve real-model speed.
- Historical repair results are retained in
  `evidence/previous-verification-0.2.0.md`; they describe the preceding build.

## Smallest remaining check

Launch this new folder on the user's desktop, check About shows 0.3.0, choose a
local text model and ask "What is two plus two?" without opening an image. Then
attach a non-sensitive image, select a vision model, ask about it, clear it and
ask another text question. Record any exact error and the selected model tag.

## Suggested Git checkpoint

```text
feat: allow local text questions with optional images

Accept verified text-generation models for questions without images, retain
vision checks for attachments, and select prompts and request fields for the
current inputs. Clarify readiness and keep text surfaces readable with a dark
desktop palette. Locked offscreen verification passes 76 tests with a fake
Ollama server. Real-model testing of the new text workflow remains pending.
```

No Git commit was created. No screen capture or other integration was added.
