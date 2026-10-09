# Screen Assistant 0.4.0 — capture an area, preview, and ask

Screen Assistant answers **text questions without requiring an image** using
an installed local Ollama model. You can optionally open a PNG or JPEG and ask
a vision model about it. It uses Python 3.12+, PySide6 and uv on the existing
Linux Mint desktop setup.

This update adds one-shot screen-region capture on Linux X11. Text questions and
optional image files remain supported. Continuous observation, browser and terminal
integration, voice, model downloads and additional providers remain outside scope.

## Run on your PC

Clone this repository and run from its root:

```bash
git clone https://github.com/h99ch9/screen_assistant.git
cd screen_assistant
uv sync --locked
env -u QT_QPA_PLATFORM uv run --locked python -m screen_assistant
```

The environment-unset command removes any inherited headless Qt selection for
this launch only. It does not change shell configuration. When no such variable
is set, the ordinary command is equivalent:

```bash
uv run --locked python -m screen_assistant
```

The user installed uv at ~/.local/bin and confirmed libxcb-cursor0 was already
installed on the PC. Neither needs reinstalling for this update. If a new terminal
cannot find uv, run `export PATH="$HOME/.local/bin:$PATH"` in that terminal.

No LD_LIBRARY_PATH change, private library copy, global offscreen setting,
sudo command or desktop shortcut change is required by this project. This
archive does not contain the previously claimed launch.sh or .desktop files;
existing PC shortcuts were not inspected or modified.

If --locked reports a mismatch, stop and inspect pyproject.toml versus uv.lock
before changing dependencies. This update changed only the application's own
version in the lockfile, from 0.3.0 to 0.4.0. All third-party pins are unchanged;
PySide6, Essentials, Addons and Shiboken remain at 6.11.2.
requirements.txt is a generated runtime-only export; uv.lock is authoritative.

## Use the current workflow

1. **Check connection**: list installed models from Ollama at 127.0.0.1:11434.
   Choose a local text or vision model from the dropdown. The app checks that
   the model can generate answers. An embedding-only model is not suitable.
2. Type a question and press **Ask** or Enter. With no image attached, only
   the question and text-specific system instructions are sent. The source
   indicator reads **Text only — no image**.
3. For an image question, use **Open image** (or Ctrl+O) to select a PNG or JPEG,
   and choose a model with verified vision support. The source indicator shows
   the image filename. If a text-only model is selected, Ask stays disabled and
   a message explains that you must clear the image or choose a vision model.
   Opening or cancelling the picker sends no image or question to Ollama.
4. **Cancel** stops waiting for the active request. Changing the image or model,
   clearing the image, or closing the window also invalidates the request.
   Late responses cannot replace the current result.
5. **Clear image** returns to text questions, clearing the preview and answer
   while retaining the question you typed. The original file is unchanged.
   **Quit**, Ctrl+Q and the window close button save geometry and close the app.

Preview images retain their proportions during resize. Answers appear as plain
text, with the selected model and measured elapsed time. Each question gets one
non-streaming response. The app sends no prior answer or conversation history
with a new question. Observation stays off.
Only window geometry is written to QSettings; the old observations_on key is
removed without discarding geometry.

## Capture area (Linux X11)

1. Click **Capture area** or press **Ctrl+Shift+A** within the app. With several
   displays, choose one first. The assistant hides briefly.
2. Drag a rectangle on the frozen display image. Release to return to the crop
   preview. **Escape** or right-click cancels and preserves the previous image.
3. Inspect the preview, select a vision model, type a question, and press **Ask**.
   Selecting an area sends nothing to the model. Ask sends exactly the previewed
   crop; it does not silently refresh the screen. Capture again for fresh content.
4. **Clear image** removes the capture and returns to text questions.

The source label includes capture time and display name. A single display frame
is temporarily held in memory for selection; only the selected crop is retained
when the selector closes. Nothing is saved to disk by capture. Existing image
size limits apply, including a 25-million-pixel limit on the temporary display
frame. Observation remains off. Overlapping windows and notifications visible
at capture time may appear; review the crop before Ask.

This backend supports Linux X11 only. Wayland (including XWayland), other OSes,
and headless sessions show an explanation and keep **Open image** available.
There is no automatic switch to a broader capture source. Select one display at
a time; regions cannot span displays. A disconnected or resized display cancels
selection. The 300 ms hide delay allows the desktop to repaint, but compositor
behavior still needs checking on the target desktop.

Automated tests cover the selector and request flow. See VERIFICATION.md for
actual results and the remaining Linux Mint, multi-monitor, and real-model checks.

## Ollama and limits

The app does not start, stop or reconfigure your Ollama service, install models,
or share its conversation state with Hermes. It sends requests directly to a
loopback address with proxies and HTTP redirects disabled.

Use an installed **local model that can generate answers**. Text-only models
work without an image; image attachments require vision support. The app reads
the model's reported capabilities rather than guessing from its name. There is
no assumed default model and no automatic download.

Ollama can route requests to cloud models even when its API is on localhost.
This client rejects identified remote models, but a localhost address alone
cannot guarantee server-side privacy. For local-only inference, configure
the actual Ollama service with OLLAMA_NO_CLOUD=1 or the documented
disable_ollama_cloud server setting. The app does not change an existing
server's configuration. Ollama's own storage, logging and server-side behavior
are separate from the application's in-memory state.

Limits: PNG/JPEG only, at most 20 MiB per file and 25 million decoded pixels.
File size, detected format and header dimensions are checked before full
decoding. Model metadata requests have an 8-second deadline; analysis has a
180-second total deadline. Responses are limited to 8 MiB. A timeout is an
error. Cancel aborts the client's request; it cannot guarantee that an
independent server immediately stops all computation.

Model output can be inaccurate, particularly for small text. The system prompt
asks the model to distinguish evidence from inference, acknowledge unreadable
text, and treat instructions inside the image as content. This is guidance
to the model, not a guarantee of correctness.

## Repeatable verification

Install the **test extra** explicitly; it is an optional dependency extra,
not a uv dependency group.

```bash
uv sync --locked --extra test
QT_QPA_PLATFORM=offscreen timeout 45 uv run --locked --extra test python -m screen_assistant.verify
```

The equivalent direct command is:

```bash
QT_QPA_PLATFORM=offscreen timeout 45 uv run --locked --extra test python -m pytest -q
```

The old foundation entry point now selects the maintained foundation tests:

```bash
QT_QPA_PLATFORM=offscreen timeout 45 uv run --locked --extra test python verify_offscreen_qtest.py
```

These commands use a fake HTTP server on an ephemeral loopback port, synthetic
images and temporary settings files. They do not contact your real Ollama
service or need a downloaded model. A failing test, uncaught Qt callback
exception, zero collected tests, or outer timeout returns nonzero.
An exit status of 124 means the outer timeout failed the check.

To verify a genuinely new environment while keeping the normal .venv:

```bash
check_dir=$(mktemp -d)
UV_PROJECT_ENVIRONMENT="$check_dir/venv" uv sync --locked --extra test &&
UV_PROJECT_ENVIRONMENT="$check_dir/venv" QT_QPA_PLATFORM=offscreen timeout 45 uv run --locked --extra test python -m pytest -q
```

The package cache may be reused; the virtual environment in check_dir is new.

## Manual checks for this update

In a real desktop session, inspect the title and window, resize it to its minimum,
confirm disabled Ask is distinct, and open/close About. Select an installed
text model, type "What is two plus two?", and Ask with no image. Confirm a real
answer appears. Then load a non-sensitive
PNG and JPEG and check their previews. With a verified local vision model,
ask about three known images (terminal text, a webpage screenshot and a diagram).
Record the exact model tag, whether the response is grounded in the image,
and any unreadable text or incorrect answer. Exercise Cancel, clear and replace.
Clear the image and ask another text question; confirm no old image is sent.
Check File → Quit, Ctrl+Q, and remembered size/position after relaunch.

The user reports that the preceding image-question build now works. This is
user-reported evidence, not an independently recorded accuracy or performance
test. The new text-question flow has been tested offscreen with a fake server;
its real-model and live desktop checks remain to be performed on the PC.

The root screen-assistant-github-ready.zip is the historical 0.3.0 delivery;
use the current Git checkout or GitHub Download ZIP for 0.4.0.

See VERIFICATION.md and evidence/ for the review findings, exact results and
remaining checks. Offscreen renders are explicitly labelled; they do not prove
a live desktop launch. UPDATE.patch records the historical changes from the
previously delivered 0.2.0 source. Historical patches and logs have local machine
paths normalized for publication; they are reference evidence, not update
instructions for this repository. Use Git for subsequent repository updates.

## References

- [uv locking and syncing](https://docs.astral.sh/uv/concepts/projects/sync/)
- [Ollama model capabilities](https://docs.ollama.com/api-reference/show-model-details)
- [Ollama chat request format](https://docs.ollama.com/api/chat)
- [Ollama local-only configuration](https://docs.ollama.com/faq)
- [Qt Linux dependencies](https://doc.qt.io/qt-6/linux-requirements.html)
