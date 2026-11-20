import json, threading, traceback, asyncio, time, re
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from dotenv import load_dotenv
load_dotenv()

from astra.action_executor import execute as execute_targeted
from astra.chatgpt import extract_prompt, run_chatgpt
from astra.agents import orchestrate, plan, inspect_screen, make_actions, verify
from astra.computer import execute_action, screenshot_data_url, screen_size, screenshot_dimensions, coordinate_calibration, launch_desktop_app, ALLOWED
from astra.browser import extract_url, open_and_check, play_youtube_song, extract_youtube_search_query

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
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="ASTRA COMPUTER AGENT", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(outer, text="NVIDIA NIM • Multi-agent workflow • Local Windows control").pack(anchor="w", pady=(0,10))

        ttk.Label(outer, text="What should Astra do?").pack(anchor="w")
        self.task = scrolledtext.ScrolledText(outer, height=5, wrap="word", font=("Segoe UI", 10))
        self.task.pack(fill="x", pady=5)
        self.task.insert("1.0", "Open a browser and navigate to https://www.nvidia.com")

        controls = ttk.Frame(outer)
        controls.pack(fill="x", pady=6)
        self.approval = tk.BooleanVar(value=True)
        ttk.Checkbutton(controls, text="Ask me before every computer action (recommended)", variable=self.approval).pack(side="left")
        self.run_btn = ttk.Button(controls, text="Run Astra", command=self.start)
        self.run_btn.pack(side="right")
        ttk.Button(controls, text="Inspect screen", command=self.inspect_only).pack(side="right", padx=8)
        ttk.Button(controls, text="Emergency stop", command=self.stop_notice).pack(side="right", padx=8)

        self.status = tk.StringVar(value="Ready")
        ttk.Label(outer, textvariable=self.status).pack(anchor="w", pady=4)
        ttk.Label(outer, text="Activity log").pack(anchor="w")
        self.log = scrolledtext.ScrolledText(outer, height=22, wrap="word", font=("Consolas", 9), state="disabled")
        self.log.pack(fill="both", expand=True)
        ttk.Label(outer, text="Safety: move the mouse to the top-left screen corner to trigger PyAutoGUI fail-safe.",
                  foreground="#9a4b00").pack(anchor="w", pady=(8,0))

    def write_log(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def ui(self, fn, *args):
        self.root.after(0, lambda: fn(*args))

    def ask_approval(self, description):
        # Workflow runs on a worker; modal Tk dialogs belong to the UI thread.
        done = threading.Event()
        answer = []

        def show():
            try:
                self.root.deiconify()
                answer.append(messagebox.askyesno("Approve Astra action", description, parent=self.root))
            finally:
                done.set()

        self.root.after(0, show)
        done.wait()
        return bool(answer and answer[0])

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
        minimized.wait(timeout=3)
        time.sleep(0.8)  # allow Windows to finish minimizing/redrawing
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
        try:
            asyncio.run(self.async_workflow(task))
        except Exception as e:
            self.ui(self.write_log, "WORKFLOW ERROR: " + str(e))
            self.ui(self.write_log, traceback.format_exc())
        finally:
            self.ui(self.finish)


    async def async_workflow(self, task):
        execution_log = []
        self.ui(self.set_status, "1/6 — Orchestrating")
        routing = await orchestrate(task)
        self.ui(self.write_log, "ORCHESTRATOR:\n" + json.dumps(routing, indent=2))

        self.ui(self.set_status, "2/6 — Planning")
        plan_data = await plan(task, routing)
        self.ui(self.write_log, "PLAN:\n" + json.dumps(plan_data, indent=2))

        # Browser tasks use a dedicated browser service. Never let the visual
        # desktop agent click Astra's own Run button to imitate browser execution.
        is_browser_task = (
            routing.get("task_type") == "browser_task"
            or bool(routing.get("needs_browser", False))
        )

        # Deterministic Windows app launch: for explicit "open Brave" requests,
        # resolve the actual .lnk target and pass the URL as a process argument.
        # This avoids vision-coordinate mistakes (e.g. clicking Proton VPN) and
        # prevents typing URLs into an unrelated foreground window.
        wants_brave = bool(re.search(r"\bbrave\b", task, flags=re.IGNORECASE))
        has_site = bool(re.search(r"https?://|\b[a-z0-9-]+\.[a-z]{2,}\b", task, flags=re.IGNORECASE))
        prompt = extract_prompt(task)
        if prompt:
            self.ui(self.set_status, "3/6 — Opening ChatGPT (sign in manually if prompted)")
            if self.approval.get() and not self.ask_approval(
                "Open ChatGPT in your default browser, replace the clipboard with this prompt, paste it and click Send? Keep that tab in front.\n\n" + prompt
            ):
                result = {"action": "chatgpt_prompt", "status": "cancelled_by_user"}
            else:
                result = await asyncio.to_thread(run_chatgpt, prompt)
            execution_log.append(result)
            self.ui(self.write_log, "CHATGPT RESULT:\n" + json.dumps(result, indent=2, ensure_ascii=False))
        elif wants_brave and has_site:
            self.ui(self.set_status, "3/6 — Launching Brave directly")
            target_url = extract_url(task)
            approved = True
            if self.approval.get():
                approved = self.ask_approval(
                    f"Launch Brave and open this website?\n\n{target_url}\n\nAstra will use the actual Windows shortcut/executable, not mouse coordinates."
                )
            if approved:
                launch_result = await asyncio.to_thread(launch_desktop_app, "Brave", target_url)
                execution_log.append({"action": "launch_brave_and_open_url", "result": launch_result})
                self.ui(self.write_log, "APPLICATION LAUNCH:\n" + json.dumps(launch_result, indent=2))
                # Verify network reachability separately; this does not pretend
                # to prove the visible browser tab rendered successfully.
                try:
                    # Check reachability without opening a second/default browser.
                    from urllib.request import Request, urlopen
                    request = Request(target_url, headers={"User-Agent": "Mozilla/5.0 AstraComputerAgent/1.0"})
                    with urlopen(request, timeout=15) as response:
                        network_result = {"http_status": response.status, "reachable": 200 <= response.status < 400}
                except Exception as exc:
                    network_result = {"reachable": False, "note": str(exc)}
                execution_log.append({"action": "http_reachability_check", "url": target_url, "result": network_result})
                self.ui(self.write_log, "WEBSITE REACHABILITY:\n" + json.dumps(network_result, indent=2))
            else:
                execution_log.append({"action": "launch_brave_and_open_url", "status": "cancelled_by_user"})
                self.ui(self.write_log, "Brave launch cancelled by user.")
        elif is_browser_task:
            wants_youtube_song = bool(re.search(r"youtube", task, re.I) and re.search(r"\b(play|song|music)\b", task, re.I))
            if wants_youtube_song:
                self.ui(self.set_status, "3/6 — Launching Chrome and playing a YouTube song")
                # Extract the requested track from the user's original instruction.
                # Never let a planner example or a previous test song override it.
                search_query = extract_youtube_search_query(task)
                if self.approval.get():
                    approved = self.ask_approval(
                        "Launch Google Chrome, search YouTube for\n\n"
                        + search_query
                        + "\n\nand open the first playable video?"
                    )
                else:
                    approved = True
                if not approved:
                    execution_log.append({"action": "youtube_search_and_play", "status": "cancelled_by_user"})
                    self.ui(self.write_log, "YouTube playback cancelled by user.")
                else:
                    chrome = await asyncio.to_thread(launch_desktop_app, "Chrome", None, False)
                    self.ui(self.write_log, "CHROME APPLICATION RESOLUTION:\n" + json.dumps(chrome, indent=2))
                    result = await asyncio.to_thread(play_youtube_song, chrome["executable"], search_query)
                    execution_log.append({"action": "launch_chrome", "result": chrome})
                    execution_log.append(result)
                    self.ui(self.write_log, "YOUTUBE PLAYBACK RESULT:\n" + json.dumps(result, indent=2))
            else:
                self.ui(self.set_status, "3/6 — Opening website in default browser")
                url = extract_url(task)
                if self.approval.get():
                    approved = self.ask_approval(f"Open this website in your default browser?\n\n{url}")
                else:
                    approved = True
                if not approved:
                    execution_log.append({"action": "open_browser_url", "url": url, "status": "cancelled_by_user"})
                    self.ui(self.write_log, "Browser navigation cancelled by user.")
                else:
                    result = open_and_check(url)
                    execution_log.append(result)
                    self.ui(self.write_log, "BROWSER RESULT:\n" + json.dumps(result, indent=2))
        else:
            # Desktop tasks use screenshot grounding and allowlisted local actions.
            self.ui(self.set_status, "3/6 — Inspecting desktop")
            observation = None
            if routing.get("needs_computer", True):
                clean_image = await asyncio.to_thread(self.capture_clean_desktop)
                calibration = await asyncio.to_thread(coordinate_calibration)
                self.ui(self.write_log, "COORDINATE CALIBRATION:\n" + json.dumps(calibration, indent=2))
                observation = await inspect_screen(task, screenshot_url=clean_image)
                self.ui(self.write_log, "COMPUTER AGENT OBSERVATION:\n" + json.dumps(observation, indent=2))

            self.ui(self.set_status, "4/6 — Preparing computer actions")
            proposed = await make_actions(task, plan_data, observation)
            actions = proposed.get("actions", [])

            self.ui(self.write_log, "PROPOSED ACTIONS:\n" + json.dumps(proposed, indent=2))
            for index, item in enumerate(actions, 1):
                if not isinstance(item, dict) or item.get("action") not in ALLOWED:
                    raise ValueError(f"Rejected unsupported action: {item}")
                description = f"Action {index}/{len(actions)}: {json.dumps(item, ensure_ascii=False)}"
                if self.approval.get():
                    approved = self.ask_approval(description)
                    if not approved:
                        execution_log.append({"action": item, "status": "skipped_by_user"})
                        break
                self.ui(self.set_status, f"4/6 — Executing action {index}/{len(actions)}")
                # Approval dialogs and clean-screen inspection restore Astra. Keep it
                # out of the actual input path before grounding or sending keys.
                self.root.iconify()
                await asyncio.sleep(0.5)
                if item["action"] in {"click", "double_click", "right_click", "move", "scroll", "type_text"}:
                    result = await execute_targeted(item)
                else:
                    result = execute_action(item)
                execution_log.append({"action": item, "result": result})
                self.ui(self.write_log, "EXECUTED:\n" + json.dumps(execution_log[-1], indent=2))

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
        self.ui(self.write_log, "ASTRA FINISHED. Verdict: " + str(verdict.get("verdict", "unknown")))

def main():
    root = tk.Tk()
    AstraApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
