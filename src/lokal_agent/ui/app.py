from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from queue import Queue, Empty
from typing import Optional
from pathlib import Path

from nicegui import ui
import requests

from lokal_agent.core.config import AppConfig
from lokal_agent.core.storage.db import (
    init_db,
    upsert_project,
    create_run,
    list_messages,
)
from lokal_agent.core.agent.runner import run_agent, DummyAgent

import subprocess
import re


# ------------------------
# Port auto-kill (Windows)
# ------------------------
def kill_port(port: int) -> None:
    try:
        out = subprocess.check_output(["netstat", "-ano"], text=True, errors="ignore")
    except Exception:
        return

    pattern = re.compile(rf"^\s*TCP\s+\S+:{port}\s+\S+\s+(\S+)\s+(\d+)\s*$", re.IGNORECASE)
    for line in out.splitlines():
        m = pattern.match(line)
        if not m:
            continue
        state = m.group(1).upper()
        pid = m.group(2)
        if ("LISTEN" in state) or ("ABH" in state):
            subprocess.run(
                ["taskkill", "/PID", pid, "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )


# ------------------------
# App setup
# ------------------------
cfg = AppConfig()
init_db(cfg)

event_q: Queue = Queue()


@dataclass
class UiState:
    project_path: str = ""
    start_message: str = ""
    run_id: Optional[int] = None
    status: str = "IDLE"
    report_text: str = ""
    mode: str = "LOCAL"  # LOCAL | API
    api_base_url: str = "http://127.0.0.1:8000"


state = UiState()


# ------------------------
# Workers
# ------------------------
def _run_worker_local(project_path: str, start_message: str):
    try:
        proj = upsert_project(cfg, project_path)
        run = create_run(cfg, proj.id, start_message)
        state.run_id = run.id
        event_q.put(("status", f"RUNNING (run_id={run.id})"))

        final = run_agent(cfg, DummyAgent(), run.id, project_path, start_message)
        event_q.put(("final", final.summary))
    except Exception as e:
        event_q.put(("error", str(e)))


def _run_worker_api(project_path: str, start_message: str):
    try:
        event_q.put(("status", "RUNNING (API)"))
        url = state.api_base_url.rstrip("/") + "/runs"
        r = requests.post(
            url,
            json={"project_path": project_path, "start_message": start_message},
            timeout=120,
        )
        r.raise_for_status()
        data = r.json()
        state.run_id = data.get("run_id")
        final = data.get("final", {})
        event_q.put(("final", final.get("summary", "API run completed.")))
    except Exception as e:
        event_q.put(("error", f"API error: {e}"))


# ------------------------
# UI actions
# ------------------------
def start_run():
    if not state.project_path.strip():
        ui.notify("Projektordner fehlt.", type="warning")
        return

    if not Path(state.project_path).exists():
        ui.notify("Projektpfad existiert nicht.", type="warning")
        return

    if not state.start_message.strip():
        ui.notify("Startnachricht fehlt.", type="warning")
        return

    state.status = "STARTING"
    state.report_text = ""
    state.run_id = None

    worker = _run_worker_api if state.mode == "API" else _run_worker_local
    threading.Thread(
        target=worker,
        args=(state.project_path, state.start_message),
        daemon=True,
    ).start()


def refresh_view(status_label, report_area, chat_column):
    changed = False
    while True:
        try:
            kind, payload = event_q.get_nowait()
        except Empty:
            break

        changed = True
        if kind == "status":
            state.status = payload
        elif kind == "final":
            state.status = "COMPLETED"
            if state.mode == "LOCAL" and state.run_id:
                msgs = list_messages(cfg, state.run_id)
                state.report_text = (
                    f"Run {state.run_id} abgeschlossen\n\n"
                    f"{payload}\n\n"
                    + "\n\n".join([f"[{m.role}] {m.content}" for m in msgs])
                )
            else:
                state.report_text = payload
        elif kind == "error":
            state.status = "FAILED"
            state.report_text = payload

    if changed:
        status_label.text = f"Status: {state.status}"
        report_area.value = state.report_text

        chat_column.clear()
        if state.mode == "LOCAL" and state.run_id:
            for m in list_messages(cfg, state.run_id):
                with chat_column:
                    ui.markdown(f"**{m.role}**\n\n{m.content}")


# ------------------------
# UI Layout
# ------------------------
@ui.page("/")
def main_page():
    dark = ui.dark_mode()
    dark.enable()

    ui.markdown("# Lokal-GbtAgent (NiceGUI)")
    ui.switch(
        "Dark Mode",
        value=True,
        on_change=lambda e: dark.enable() if e.value else dark.disable(),
    )

    ui.separator()

    with ui.row().classes("w-full items-center"):
        ui.select(["LOCAL", "API"], value="LOCAL", label="Modus") \
            .on("change", lambda e: setattr(state, "mode", e.value))
        ui.input("API Base URL", value=state.api_base_url).classes("w-full") \
            .bind_value_to(state, "api_base_url")

    ui.separator()

    # -------- Projektordner: NUR eine Adresszeile --------
    ui.input(
        "Projektordner (Pfad)",
        placeholder=r"C:\Users\kscha\Desktop\Projekt-Ordner\MeinProjekt",
    ).classes("w-full").bind_value_to(state, "project_path")

    ui.textarea(
        "Startnachricht",
        placeholder="Was soll der Agent tun?",
    ).classes("w-full").bind_value_to(state, "start_message")

    with ui.row().classes("items-center"):
        ui.button("RUN STARTEN", on_click=start_run)
        status_label = ui.label("Status: IDLE")

    ui.separator()

    with ui.row().classes("w-full"):
        with ui.column().classes("w-1/2"):
            ui.markdown("## Chat")
            chat_column = ui.column().classes("w-full")
        with ui.column().classes("w-1/2"):
            ui.markdown("## Report")
            report_area = ui.textarea().classes("w-full")
            report_area.props("rows=18")
            report_area.props("disable")

    ui.timer(0.5, lambda: refresh_view(status_label, report_area, chat_column))


# ------------------------
# Entry
# ------------------------
def main():
    kill_port(8081)
    ui.run(host="127.0.0.1", port=8081, reload=False)


if __name__ == "__main__":
    main()
