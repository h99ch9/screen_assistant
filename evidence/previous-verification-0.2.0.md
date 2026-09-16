# Verification checkpoint — 2026-09-16

## Scope and actual locations

Input: screen-assistant-review-20260915-172132.zip, supplied by the user.
The existing PC project was reported at /path/to/screen-assistant.
This review did **not** access or modify that PC directory.

The upload was inspected at:
`/review-workspace/screen_assistant_repair/original`

Repairs were made in a separate copy:
`/review-workspace/screen_assistant_repair/project`

The rebuilt archive was independently extracted and tested at:
`/review-workspace/screen_assistant_repair/fresh-extraction/screen-assistant-repaired`

This is a repair of the existing image-question implementation. No live capture,
browser/terminal integration, new provider, or model-download feature was added.
The archive had no launch.sh, desktop shortcut files or Git history, despite the
earlier report. No unrelated PC files or installed shortcuts were changed.

## Findings in the upload

| Finding | Evidence | Repair |
|---|---|---|
| Window construction crashed | Original QTest run: AttributeError for missing _on_image_changed, exit 1 | Connected actual controls and explicit state updates |
| Pytest executed no tests | Original collection: zero tests, exit 5; functions used check_ names | One maintained pytest suite with 51 collected cases |
| Lockfile did not match project metadata | Pillow and pytest extra were declared but absent from uv.lock | Deliberately refreshed lock and runtime requirements export; kept Qt 6.11.2 |
| Open/Clear buttons and question changes were disconnected | Source inspection | Connected actions and readiness updates; real UI tests |
| Model selector was a label; checking connection did not reach verification | Source inspection | Real dropdown, model listing, selected-model verification |
| Fake server repeated the client's wrong capabilities shape | Source inspection against official API | Realistic string-array capabilities and model request field |
| Analysis relied on readyRead finding isFinished; system prompt was unused | Source inspection | Completion on finished, validated JSON, actual system and user messages |
| Cancellation and old callbacks could alter new state | Source inspection | Identity checks, explicit cancellation, deadline ownership and cleanup |
| Preview resize filter was absent; geometry was saved but not restored | Source inspection | Resize handling and geometry restore; isolated settings tests |
| Image data was fully read/decoded before limits were checked | Source inspection | Bounded read and header validation before full decoding |
| Observation was already hard-coded off; stale settings remained possible | Source inspection | Kept observation off, removed only the legacy observations_on key |
| About and README described conflicting milestones/versions | Source inspection | One current About dialog and evidence-based documentation |

The original Python files parsed, but that did not establish that the window
could be constructed or the application workflow worked. Earlier blanket PASS
claims are not carried forward.

The Ollama changes follow the documented
[show-model capabilities](https://docs.ollama.com/api-reference/show-model-details)
and [chat request/response format](https://docs.ollama.com/api/chat). Fake-server
success establishes client behavior against those shapes, not compatibility
or answer quality with the user's particular running model.

## Completed checks

All commands below ran in this review environment unless explicitly labelled
user-reported. Full commands, working directories and exit statuses are retained
in evidence/. Python was 3.12.14; PySide6 and its Qt dependencies remained 6.11.2.

| Check | Test mode | Command or procedure | Result | Evidence |
|---|---|---|---|---|
| Original source syntax | Static | Parse all uploaded Python modules with ast.parse | Passed | Runtime failure below still occurred |
| Original locked sync | Terminal | uv sync --locked --extra test | Failed: outdated lock, exit 1 | baseline-lock-mismatch-transcript.txt; baseline-dependency-metadata.json |
| Original window smoke test | Offscreen Qt | python verify_offscreen_qtest.py, bounded at 45 seconds | Failed immediately: missing callback, exit 1 | baseline-window.log |
| Original pytest collection | Pytest | python -m pytest --collect-only -q screen_assistant/test_verification.py | Failed: zero tests, exit 5 | baseline-pytest.log |
| Fresh repaired environment | Fresh extraction / terminal | uv sync --locked --extra test | Passed, exit 0; new .venv | fresh-sync.log |
| Full repaired suite | Offscreen Qt + fake HTTP server | QT_QPA_PLATFORM=offscreen timeout 45 uv run --locked --extra test python -m pytest -v | **51 passed in 7.76 seconds**, exit 0 | pytest.log |
| Foundation QTest entry point | Offscreen Qt | QT_QPA_PLATFORM=offscreen timeout 45 uv run --locked --extra test python verify_offscreen_qtest.py | **7 passed**, 44 deselected; exit 0 | foundation.log |
| Runtime-only install | Separate new environment | uv sync --locked with UV_PROJECT_ENVIRONMENT pointing at a new directory | Passed, exit 0; no pytest installed | runtime-sync.log |
| Runtime import | Runtime-only environment | uv run --locked python -c "import screen_assistant; import screen_assistant.__main__; print(screen_assistant.__version__)" | Passed, exit 0; printed 0.2.0 | runtime-import.log |
| Minimum-size readability and disabled Ask | Offscreen render | Capture MainWindow at 620 × 440 and inspect the image | Passed at that size in this environment | offscreen-minimum.png |
| Packaged source fidelity | Byte comparison | Compare all 20 project files with the tested extraction | Passed | SOURCE_SHA256SUMS.txt identifies delivered project bytes |

The 51 cases exercise actual widget actions and network requests: PNG/JPEG,
invalid files, independent byte/pixel limits, opening without sending, real
request fields and base64 content, verified/text-only models, malformed responses,
HTTP errors, redirects, oversized responses, slow/trickling responses, cancellation,
request replacement, model switches and delayed replies. They also exercise the
actual modal About dialog, all three close paths, a clean Qt event-loop exit,
preview resizing, invalid geometry, and size restoration with observation off.
Tests use temporary settings and synthetic images.

The seven foundation tests are a subset of the 51, **not seven extra independent
passes**. They replace the old 13-property script; no old count is carried forward.

## Failed attempts and temporary settings

- After the interruption, one dependency-install attempt timed out fetching
  setuptools metadata. A normal retry succeeded. No dependency source, system
  library, or security setting was changed to obtain that result.
- A later attempt to reproduce the original locked-sync error stopped earlier
  on a PyPI metadata timeout, exit 2. See
  evidence/baseline-sync-retry-network-failure.log. This does not invalidate
  the earlier recorded lock mismatch or the independent metadata comparison.
- No completed repaired test run timed out. A timeout must be recorded as a
  failed check; a GUI event loop simply remaining alive is not a test pass.
- QT_QPA_PLATFORM=offscreen was scoped to headless tests/renders. Temporary
  UV_PROJECT_ENVIRONMENT and test settings locations isolated verification.
  No LD_LIBRARY_PATH workaround was used. No headless default was added to
  normal application startup.
- Offscreen evidence is not evidence of a live desktop launch.

## Desktop and real-model checks

| Check | Test mode | Command or procedure | Result | Evidence |
|---|---|---|---|---|
| libxcb-cursor0 on the user's PC | User terminal | apt install output supplied in conversation | Already installed, version 0.1.4-1build1 | User output; not a current blocker |
| Earlier foundation appearance | User desktop | User's screenshot and confirmation | User-confirmed for the earlier build | Conversation; not this repaired build |
| Repaired build on Linux Mint desktop | Live desktop | From repaired root, env -u QT_QPA_PLATFORM uv run --locked python -m screen_assistant | Pending | No interactive PC desktop available to this review |
| Repaired build resize, About, Quit/Ctrl+Q, position and size round-trip | Live desktop | Follow README manual checklist | Pending; corresponding offscreen paths passed | Needs user's desktop session |
| Real vision-model responses | Local Ollama inference | Open 3 non-sensitive images; record model tag, responses and errors | Pending | Test server is simulated; no real model run |
| Disabled Ask with no verified model | Live desktop | Inspect before selecting a verified vision model | Pending on PC; passed offscreen | Offscreen render and tests |

Smallest remaining actions: launch this repaired copy in the user's existing
desktop session; then exercise its manual checklist with an installed local
vision model. No package reinstall or large model download is assumed.
The previously reported ordinary llama3.2:latest is text-only; check the actual
server model list and selected model's capabilities before choosing a download.

## Permission history

The pasted prior report quotes the rejection:
**"Edit approval denied by ACP client; file was not modified."**
That is an approval denial. Writing the blocked edit through a terminal is not
evidence of approval and must not be used to bypass such a gate. This review
cannot independently inspect the historical ACP event beyond the supplied text.

No such policy rejection occurred during these isolated repairs. One malformed
patch was rejected because it targeted the same file twice; it was corrected
as an ordinary Update File patch. That was a patch-format error, not an
approval restriction.

## Suggested Git checkpoint

```text
fix: repair image-question workflow and reproducible verification

Repair UI wiring, model capability checks, request completion, cancellation,
timeouts, image validation and geometry restoration. Align project metadata,
lockfile and verification entry points. Fresh extracted build passes 51 tests
using offscreen Qt and a fake Ollama server. Live desktop verification of this
repaired build and real-model accuracy remain pending.
```

No Git commit was created by this review. Stop at this checkpoint.
