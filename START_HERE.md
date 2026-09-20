# Open Screen Assistant 0.4.0

This update adds **Capture area** on Linux X11. Drag an area, review the preview,
then Ask using a vision model. Escape cancels. Text-only and uploaded-image
questions remain available. On Wayland, use Open image.

1. Clone `https://github.com/h99ch9/screen_assistant.git`, or download the
   repository ZIP and extract it into a new folder. Keep your working copy.
2. Open the project folder in your Linux Mint file manager. Right-click an empty area
   and choose **Open in Terminal**.
3. Run the following commands, stopping if one reports an error:

```bash
uv sync --locked --extra test
QT_QPA_PLATFORM=offscreen timeout 45 uv run --locked --extra test python -m pytest -q
env -u QT_QPA_PLATFORM uv run --locked python -m screen_assistant
```

The automated test run should report **89 passed**. It uses synthetic images and
a fake local server. No real Ollama model is needed for those checks.

The last command opens the actual desktop application. Check Open image, the
preview, resizing, About, Quit/Ctrl+Q, and remembered size/position. The app starts
with observation off and Ask disabled. For a text answer, click **Check
connection**, select an installed local text or vision model, type a question,
and click **Ask**. No image is needed. About should show version **0.4.0**.

If an image is attached, **Clear image** returns to text questions while keeping
your typed question. An attached image still requires a vision model.

These steps run the cloned or extracted copy. The project does not apply itself to another copy,
install a model or change an Ollama service.

README.md explains operation and remaining manual checks.
VERIFICATION.md separates actual results, failed attempts and pending checks.
UPDATE.patch is historical reference for the 0.2.0 to 0.3.0 changes; do not apply
it to this repository, which already contains those changes.
SOURCE_SHA256SUMS.txt identifies the tested project files.
The evidence/text-questions folder includes the previous update's logs and explicitly
offscreen renders. The previous repair report is retained as historical evidence.
Real Ollama inference on your PC was not performed by this review.
