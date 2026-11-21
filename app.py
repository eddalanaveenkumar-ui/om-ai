import json, threading, traceback, asyncio, time
import tkinter as tk
from tkinter import messagebox, simpledialog
from astra.workspace_ui import build
from dotenv import load_dotenv
load_dotenv()

from astra.recovery import RecoveryBudget, TargetNotReady, repair_queue
from astra.skills import launch_default_browser
from astra.preparation import prepare
from astra.input_activity import activity_sink
from astra.action_executor import execute as execute_targeted
from astra.agents import orchestrate, plan, inspect_screen, make_actions, verify
from astra.computer import execute_action, screenshot_data_url, coordinate_calibration, selected_explorer_item, ALLOWED
from astra.ui_policy import PRESS_KEYS, folder_key_pair, opens_chrome, planned_key, single_key, validate_ui_action

from astra.indicator import ControlIndicator


class AstraApp:
    def __init__(self, root):
        self.root = root
        root.title("Astra — Computer Agent")
        root.geometry("1000x760")
        root.minsize(800, 600)
        self.busy = False
        self.indicator = ControlIndicator(root)
        self._build()

    def _build(self):
        build(self)

    def write_log(self, text):
        self.log.configure(state="normal")
        if self.log.tag_ranges("idle"):
            self.log.delete("1.0", "end")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def ui(self, fn, *args):
        self.root.after(0, lambda: fn(*args))

    def ask_on_ui(self, dialog):
        # Workflow runs on a worker; modal Tk dialogs belong to the UI thread.
        done = threading.Event()
        answer = []

        def show():
            try:
                self.root.deiconify()
                answer.append(dialog())
            finally:
                done.set()

        self.root.after(0, show)
        done.wait()
        return answer[0] if answer else None

    def ask_approval(self, description):
        return self.ask_on_ui(lambda: messagebox.askyesno("Approve Astra action", description, parent=self.root))

    def clarify_key(self, item):
        def dialog():
            message = ("The proposed key is missing or ambiguous. No key has been pressed.\n"
                       + str(item.get('reason', '')) + "\nChoose one: " + ', '.join(sorted(PRESS_KEYS)))
            while True:
                value = simpledialog.askstring("Which key should Astra press?", message, parent=self.root)
                if value is None or single_key(value):
                    return single_key(value)
                messagebox.showwarning("Unsupported key", "Enter one listed key, or Cancel to stop.", parent=self.root)
        return self.ask_on_ui(dialog)

    def set_status(self, value):
        self.status.set(value)

    def start(self):
        if self.busy: return
        task = self.task.get("1.0", "end").strip()
        if not task:
            messagebox.showwarning("Astra", "Enter a task first.")
            return
        try:
            self.indicator.start()
        except Exception as exc:
            self.indicator.stop()
            self.write_log(f"Cannot show AI control indicator; task not started: {exc}")
            return
        self.busy = True
        self.run_btn.configure(state="disabled")
        threading.Thread(target=self.workflow, args=(task,), daemon=True).start()

    def finish(self):
        self.indicator.stop()
        self.root.deiconify()
        self.busy = False
        self.run_btn.configure(state="normal")
        self.set_status("Ready")

    def stop_notice(self):
        messagebox.showinfo("Emergency stop", "Move your mouse to the extreme top-left corner of the screen. PyAutoGUI will raise its fail-safe exception.")

    def capture_clean_desktop(self):
        """Minimize Astra before capture so the vision model sees the desktop beneath it."""
        minimized = threading.Event()
        restored = threading.Event()

        def do_minimize():
            self.root.iconify()
            minimized.set()

        self.root.after(0, do_minimize)
        if not minimized.wait(timeout=3):
            raise RuntimeError("Astra did not minimize; capture cancelled.")
        # Wait for the compositor rather than sleeping 800 ms on every capture.
        import ctypes
        try:
            if ctypes.windll.dwmapi.DwmFlush() != 0:
                time.sleep(0.25)
        except (AttributeError, OSError):
            time.sleep(0.25)
        try:
            image_url = screenshot_data_url()
        finally:
            def do_restore():
                self.root.deiconify()
                self.root.lift()
                restored.set()
            self.root.after(0, do_restore)
            restored.wait(timeout=3)
        return image_url

    def inspect_only(self):
        if self.busy: return
        self.busy = True
        threading.Thread(target=self.inspect_work, daemon=True).start()

    def inspect_work(self):
        try:
            self.ui(self.set_status, "Inspecting screen...")
            image_url = self.capture_clean_desktop()
            calibration = coordinate_calibration()
            self.ui(self.write_log, "COORDINATE CALIBRATION:\n" + json.dumps(calibration, indent=2))
            result = asyncio.run(inspect_screen(
                "Inventory all visible desktop elements. Identify desktop shortcuts, folders, taskbar icons, and open windows. Do not report Astra itself.",
                screenshot_url=image_url
            ))
            self.ui(self.write_log, "SCREEN INSPECTION:\n" + json.dumps(result, indent=2))
        except Exception as e:
            self.ui(self.write_log, "ERROR: " + str(e))
        finally:
            self.ui(self.finish)


    def workflow(self, task):
        token = activity_sink.set(lambda event: self.ui(self.write_log, "COMPUTER INPUT: " + json.dumps(event)))
        try:
            asyncio.run(self.async_workflow(task))
        except Exception as e:
            self.ui(self.write_log, "WORKFLOW ERROR: " + str(e))
            self.ui(self.write_log, traceback.format_exc())
        finally:
            activity_sink.reset(token)
            self.ui(self.finish)


    async def async_workflow(self, task):
        execution_log = []
        self.ui(self.set_status, "Preparing workflow")
        started = time.perf_counter()

        async def inspect_initial(request):
            image = await asyncio.to_thread(self.capture_clean_desktop)
            return await inspect_screen(request, screenshot_url=image)

        def report(label, data):
            self.ui(self.write_log, label + ":\n" + json.dumps(data, indent=2))

        routing, plan_data, prompt, proposed = await prepare(
            task, orchestrate, plan, inspect_initial, make_actions, report)
        self.ui(self.write_log, f"Workflow prepared in {time.perf_counter() - started:.1f}s")
        actions = proposed.get("actions", [])

        self.ui(self.write_log, "PROPOSED ACTIONS:\n" + json.dumps(proposed, indent=2))
        profile_ready = False
        index = 0
        budget = RecoveryBudget()
        halted = False
        while True:
            while index < len(actions):
                item = actions[index]
                index += 1
                skill_step = prompt and isinstance(item, dict) and item.get("action") in {"launch_default_browser", "confirm_chatgpt"}
                if not skill_step and (not isinstance(item, dict) or item.get("action") not in ALLOWED):
                    raise ValueError(f"Rejected unsupported action: {item}")
                paired_delete = (index < len(actions) and folder_key_pair(task, item, actions[index]))
                if item["action"] == "press_key":
                    key = planned_key(item) or self.clarify_key(item)
                    if key is None:
                        execution_log.append({"action": item, "status": "cancelled_before_keypress"})
                        halted = True
                        break
                    item = dict(item, key=key)
                validate_ui_action(item)
                if profile_ready and opens_chrome(item):
                    raise ValueError("Chrome is already open; refusing to reopen it after profile selection.")
                description = f"Action {index}/{len(actions)}: {json.dumps(item, ensure_ascii=False)}"
                if item["action"] == "confirm_chatgpt":
                    if not self.ask_approval("Check that the active site is chatgpt.com, sign in yourself if needed, and open an empty chat. Continue only when ready to enter your request?"):
                        execution_log.append({"action": item, "status": "cancelled"})
                        halted = True
                        break
                    continue
                if paired_delete:
                    description += "\nThen press Delete on the single selected Explorer item. Approve both steps?"
                if paired_delete or self.approval.get():
                    approved = self.ask_approval(description)
                    if not approved:
                        execution_log.append({"action": item, "status": "skipped_by_user"})
                        halted = True
                        break
                self.ui(self.set_status, f"4/6 — Executing action {index}/{len(actions)}")
                # Approval dialogs and clean-screen inspection restore Astra. Keep it
                # out of the actual input path before grounding or sending keys.
                if self.root.state() != "iconic":
                    self.root.iconify()
                    await asyncio.sleep(0.25)
                if item["action"] == "launch_default_browser":
                    result = await asyncio.to_thread(launch_default_browser)
                elif item["action"] in {"click", "double_click", "right_click", "move", "scroll", "type_text"}:
                    try:
                        result = await execute_targeted(item)
                    except TargetNotReady as exc:
                        failure = {"action": item, "status": "no_input_sent", "reason": str(exc)}
                        execution_log.append(failure)
                        self.ui(self.write_log, "TARGET NOT READY: " + str(exc))
                        if not budget.claim():
                            halted = True
                            break
                        image = await asyncio.to_thread(self.capture_clean_desktop)
                        observation = await inspect_screen("Identify what blocks this action: " + description,
                                                           screenshot_url=image)
                        repair = await make_actions(task, dict(plan_data, failed=failure, recent=execution_log[-8:],
                            recovery="Explain the observed blocker. Propose only the steps needed to complete this failed action. Do not repeat completed actions, submit twice, or perform later steps. Return empty actions if human input is required."), observation)
                        self.ui(self.write_log, "RECOVERY: " + json.dumps(repair, ensure_ascii=False))
                        replacement = repair_queue(repair, actions[index:], ALLOWED)
                        if replacement is None:
                            halted = True
                            break
                        actions, index = replacement, 0
                        continue
                else:
                    result = execute_action(item)
                execution_log.append({"action": item, "result": result})
                self.ui(self.write_log, "EXECUTED:\n" + json.dumps(execution_log[-1], indent=2))

                if paired_delete:
                    # No dialog, minimize, or separate approval between selection and key.
                    try:
                        selected = selected_explorer_item(result['x'], result['y'])
                    except Exception as exc:
                        selected = False
                        self.ui(self.write_log, f'Explorer selection check unavailable: {exc}')
                    if not selected:
                        self.ui(self.write_log, "Delete withheld: could not verify a single selected Explorer item.")
                        halted = True
                        break
                    key_action = {"action": "press_key", "key": "delete"}
                    key_result = execute_action(key_action)
                    execution_log.append({"action": key_action, "result": key_result})
                    self.ui(self.write_log, "EXECUTED: " + json.dumps(execution_log[-1]))
                    index += 1

                if opens_chrome(item) or item["action"] == "launch_default_browser":
                    self.ui(self.set_status, "Paused — confirm browser profile")
                    ready = self.ask_approval(
                        "Automation is paused. Switch to your browser (Alt+Tab) and choose your profile. "
                        "If the browser already shows the profile you want, leave it open. "
                        "Return here and choose Yes only when your browser window is ready. "
                        "Choose No to stop. Astra will not select an account for you."
                    )
                    execution_log.append({"action": "manual_chrome_profile", "ready": ready})
                    if not ready:
                        halted = True
                        break
                    profile_ready = True
                    if prompt:
                        continue  # Resume the fixed recipe; each target is grounded live.
                    # The pre-launch plan cannot know which window opened. Replace its
                    # remaining actions rather than replaying stale picker or search steps.
                    image = await asyncio.to_thread(self.capture_clean_desktop)
                    observation = await inspect_screen(task, screenshot_url=image)
                    remaining = await make_actions(task, dict(plan_data, completed=
                        "Chrome is open and the user confirmed their profile. Do not reopen Chrome or select an account. "
                        "Return only remaining actions, or an empty list if finished."), observation)
                    actions = remaining.get("actions", [])
                    index = 0
                    self.ui(self.write_log, "AFTER PROFILE SELECTION:\n" + json.dumps(remaining, indent=2))

            final_observation = None
            if routing.get("needs_verification", True):
                self.ui(self.set_status, "5/6 — Capturing final screen")
                try:
                    clean_image = await asyncio.to_thread(self.capture_clean_desktop)
                    final_observation = await inspect_screen(
                        "Describe the current desktop and check whether the requested task visibly succeeded: " + task,
                        screenshot_url=clean_image
                    )
                    self.ui(self.write_log, "FINAL SCREEN OBSERVATION:\n" + json.dumps(final_observation, indent=2))
                except Exception as e:
                    self.ui(self.write_log, "Final screenshot analysis unavailable: " + str(e))

            self.ui(self.set_status, "6/6 — Verifying")
            verdict = await verify(task, plan_data, execution_log, final_observation)
            self.ui(self.write_log, "VERIFICATION:\n" + json.dumps(verdict, indent=2))
            if halted or verdict.get("verdict") not in {"partial", "fail"} or not budget.claim():
                break
            # Actions may already have taken effect. Do not silently replay an
            # uncertain submission just because the verifier could not see it.
            continuation = await make_actions(task, dict(plan_data, recent=execution_log[-12:],
                verification=verdict, recovery="Propose only missing steps supported by current screen evidence. Never repeat a possibly completed submission. Return no actions when unsure."), final_observation)
            actions = repair_queue(continuation, [], ALLOWED)
            if not actions or not self.ask_approval("Task not verified complete. Continue with these remaining steps?\n\n" + json.dumps(actions, ensure_ascii=False, indent=2)):
                break
            index = 0
        self.ui(self.write_log, "ASTRA FINISHED. Verdict: " + str(verdict.get("verdict", "unknown")))

def main():
    root = tk.Tk()
    AstraApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
