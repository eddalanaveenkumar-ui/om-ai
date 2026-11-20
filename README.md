# Astra Computer Agent — Asynchronous Windows MVP

A Windows desktop assistant prototype using separate NVIDIA NIM models for different agent roles.

## Agent/model allocation

- Master Orchestrator: `nvidia/nemotron-3-ultra-550b-a55b`
- Reasoning & Planning: `nvidia/nemotron-3.5-lightning-30b-a3b`
- Execution: `nvidia/nemotron-3.5-bolt-e4b`
- Verification: `nvidia/nemotron-3.5-super-vl-120b-a12b`
- Computer Use / visual grounding: `nvidia/nemotron-3.5-super-vl-120b-a12b`

These are configurable starting IDs. The Execution model ID `nvidia/nemotron-3.5-bolt-e4b` is confirmed in NVIDIA's API reference. Confirm exact model identifiers, endpoint availability, image-input support, rate limits, and account access in your NVIDIA NIM catalog. Do not assume every model is enabled for every key.

## Parallel workflow

1. Orchestrator classifies the request.
2. Planner and Computer Use screenshot analysis run concurrently when screen inspection is required.
3. Executor combines the plan and screen observations and proposes actions.
4. The local Windows controller executes allowlisted actions, asking for approval by default.
5. Final screenshot inspection runs, followed by independent verification.

This is dependency-aware concurrency, not indiscriminate parallel execution. Execution waits for planning and screenshot analysis. Verification waits for execution.

## Requirements

- Windows 10/11
- Python 3.11 recommended
- NVIDIA NIM API key with access to selected model endpoints
- Unlocked interactive desktop for PyAutoGUI

## Configure API keys

1. Copy `.env.example` to `.env`.
2. Set `NVIDIA_API_KEY`.
3. Optionally provide per-agent keys.
4. Check and update each model ID in `.env` against your NVIDIA account.

Never share `.env` or commit it to Git. The EXE does not embed your API key.

## Run from source

```powershell
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Or double-click `run.bat`.

## Build EXE

Double-click `build.bat`. Output: `dist\AstraComputerAgent.exe`.
Copy `.env` beside the EXE before running it.

## Supported local actions

click, double-click, right-click, move, scroll, type text, restricted key presses, hotkeys,
open HTTP/HTTPS URLs, wait, screenshot.

## Limitations and safety

- This is an MVP. Python syntax is checked, but live NIM endpoints and EXE execution must be tested on your machine.
- Model IDs and endpoint formats can change. Some vision models may require a model-specific image request format.
- Browser navigation requires a visible browser UI.
- No arbitrary shell, PowerShell, Python execution, file deletion, payment, or message sending is exposed.
- Coordinates can be affected by display scaling and multiple monitors.
- Keep approval enabled. Review important actions yourself.
- Emergency stop: move mouse to the top-left corner to trigger PyAutoGUI fail-safe.


## Fixes in this build

- Added a JSON parsing retry when a model responds with prose or malformed JSON.
- JSON parsing accepts valid objects surrounded by explanations or Markdown fences.
- Error messages include the beginning of the model response for easier diagnosis.
- Fixed the Inspect Screen button: it now awaits the async Computer Use Agent before
  serializing its result, fixing `coroutine is not JSON serializable`.


## Computer Use model endpoint correction

The hosted Computer Use agent is configured to use
`nvidia/nemotron-3.5-super-vl-120b-a12b`, which has a documented hosted
`/v1/chat/completions` API reference with image input.

`nvidia/cosmos3-nano-reasoner` is listed as a downloadable NIM deployment.
Do not point the hosted `https://integrate.api.nvidia.com/v1` client at Cosmos
unless NVIDIA explicitly enables a hosted endpoint for your account. For local
Cosmos deployment, use its local NIM server URL and deployment instructions.

If you are updating an existing installation, also change the existing `.env`:
`COMPUTER_MODEL=nvidia/nemotron-3.5-super-vl-120b-a12b`
because values in `.env` override Python defaults.


## Planner empty-response fix

For `nvidia/nemotron-3.5-lightning-30b-a3b`, the Planner request disables
internal thinking using NVIDIA's documented
`chat_template_kwargs: {"enable_thinking": false}` request option.
This prevents the reasoning trace from consuming the complete output token
budget before the structured plan is emitted. The model itself is unchanged.
If you later switch the Planner to another model, this option is only applied
when the agent is `planner` and the model ID contains `nemotron-3.5-lightning`.


## Mouse and keyboard only

Browser tasks (including ChatGPT and YouTube) use the same desktop input loop as other applications. Astra can select an existing tab, open an application from the taskbar or Start menu, search by site name, and click a result. The workflow no longer uses URL launchers, shell/process commands, browser drivers or network reachability checks. Screenshots and accessibility queries are read-only targeting aids. Keep per-action approval enabled when testing.

## Full-desktop inspection and visual computer use update

- Inspect Screen now minimizes the Astra window before taking the screenshot, then restores it. This prevents Astra's own UI from becoming the dominant detected object and exposes the desktop underneath.
- The Computer Use vision prompt now requests a multi-element inventory (desktop shortcuts, folders/files, taskbar icons, windows, and controls), with bounding boxes and click points for each visible target.
- Desktop workflows use the same clean-desktop capture before planning actions and before final visual verification.
- The Executor still proposes actions; the local controller validates them and asks for approval when the checkbox is enabled. Keep approval enabled while testing.
- Detection quality depends on the selected vision model and screenshot clarity. It cannot identify icons hidden behind other windows or guarantee perfect coordinates; inspect the proposed action before approving it.

## Desktop vision and multi-step Brave navigation fix

This build gives the Computer Use vision request a larger output budget and disables
Nemotron Super VL thinking for this structured extraction task, with one larger-budget
retry if the model ends with `finish_reason=length`. Vision coordinates are interpreted
in the screenshot bitmap coordinate space and scaled to PyAutoGUI screen coordinates
when required by Windows display scaling.

### AI control indicator (Windows)

**Run Astra** displays a blue glow around the primary screen and a violet-and-mint spark beside the pointer. They indicate an active workflow, including planning, approvals and verification; **Inspect screen** alone does not enable them. The overlay is click-through and does not modify your Windows pointer scheme. Both effects disappear when the workflow finishes or Astra exits.

### Accessibility + Set-of-Mark targeting

For every approved desktop click, double-click, right-click, move, text or scroll action, Astra takes a fresh primary-display screenshot and enumerates interactive controls in the foreground window. Windows uses UI Automation (including the taskbar for taskbar targets); macOS uses AXUIElement. Keep the target on the primary display. Enable **Accessibility** and **Screen Recording** permissions for the launching application on macOS. Platform-specific browser shortcuts, including the ChatGPT origin/focus guards, remain Windows-specific.

The vision endpoint receives an annotated copy and a list of IDs, names and roles. The selected ID must exist in this snapshot and the operation must match the approved action. Only the approved text/scroll amount is executed. The click uses the integer center of the OS rectangle; on Retina only the annotation is scaled. Geometry is deterministic, but OS visibility, model selection and moving controls can still affect accuracy. Missing/invalid IDs and stale targets stop the action; only an empty element set uses the older vision-box locator.

Set `DEBUG_SOM=True` in `.env` and restart to save `debug_som.png` and `debug_target.png` in the working directory. They can contain sensitive screen contents. To check alignment, try a benign button on the primary display at Windows 125%/150% or macOS Retina scale; compare its badge and center dot with the actual pointer. Debug output is disabled by default and ignored by Git.

### Direct creation requests

Try **Create an HTML login page with ChatGPT**. Direct creation requests ending in “with/using/via/in ChatGPT” use a reusable UI recipe rather than relying on the model to invent each step. Its only launch exception is the OS default browser (no task URL or prompt is passed to it). Choose your profile, then Astra searches for ChatGPT and clicks the official result through the visible UI. Confirm the site and empty composer before it types and submits your request. Per-action approvals still apply. The result stays in the conversation; this recipe does not save files. Explicit step-by-step tasks still use the ordinary desktop executor.

### Recovering a desktop task

If targeting fails before any input is sent (for example, a control moved or the selection is ambiguous), Astra logs the failure, inspects a fresh screen and asks for a repair for that step. The remaining queue is preserved. A partial or failed final verification can also propose remaining steps, with explicit approval before continuing. A shared three-round limit prevents runaway retries. Cancellation, fail-safe stops, uncertain input errors and invalid or empty repair plans are not automatically retried.
