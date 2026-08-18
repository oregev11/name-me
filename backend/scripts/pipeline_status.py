"""Tiny status writer shared by the offline artifact-build scripts
(build_corpus.py, export_semantic_model.py, build_artifacts.py), so a human
can watch progress live while a multi-minute script runs.

Design choice: rather than a static HTML page polling a JSON file via
fetch() (which hits CORS restrictions on file:// URLs in some browsers),
this regenerates a small self-contained pipeline_status.html on every
update, with the current status embedded directly and a meta-refresh tag.
Open it once in a browser (or VS Code's built-in preview) and it keeps
showing the latest state with no server process and no fetch/CORS concerns
at all -- works identically everywhere.
"""

from __future__ import annotations

import html
import json
import time
from pathlib import Path

STATUS_JSON_PATH = Path(__file__).parent / ".pipeline_status.json"
STATUS_HTML_PATH = Path(__file__).parent / "pipeline_status.html"

_REFRESH_SECONDS = 2


class PipelineStatus:
    def __init__(self, script_name: str) -> None:
        self._script_name = script_name
        self._start = time.time()
        self._log: list[str] = []
        self._write(step="starting", progress=None)

    def step(self, name: str) -> None:
        print(f"[{self._script_name}] step: {name}")
        self._log.append(name)
        self._write(step=name, progress=None)

    def progress(self, label: str, done: int, total: int) -> None:
        self._write(step=label, progress={"done": done, "total": total})

    def done(self) -> None:
        self._log.append("done")
        self._write(step="done", progress=None, finished=True)

    def failed(self, error: str) -> None:
        self._log.append(f"FAILED: {error}")
        self._write(step="failed", progress=None, finished=True, error=error)

    def _write(
        self,
        step: str,
        progress: dict | None,
        finished: bool = False,
        error: str | None = None,
    ) -> None:
        elapsed = round(time.time() - self._start, 1)
        payload = {
            "script": self._script_name,
            "step": step,
            "progress": progress,
            "elapsed_seconds": elapsed,
            "finished": finished,
            "error": error,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        STATUS_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
        STATUS_HTML_PATH.write_text(self._render_html(payload))

    def _render_html(self, payload: dict) -> str:
        step = html.escape(payload["step"])
        progress = payload["progress"]
        finished = payload["finished"]
        error = payload["error"]

        bar_html = ""
        if progress:
            pct = 100 * progress["done"] / max(progress["total"], 1)
            bar_html = f"""
            <div class="bar-track"><div class="bar-fill" style="width:{pct:.1f}%"></div></div>
            <p class="muted">{progress['done']} / {progress['total']} ({pct:.0f}%)</p>
            """

        status_word = "❌ failed" if error else ("✅ done" if finished else "⏳ running")
        refresh_tag = (
            "" if finished else f'<meta http-equiv="refresh" content="{_REFRESH_SECONDS}">'
        )
        log_items = "".join(f"<li>{html.escape(s)}</li>" for s in self._log[-15:])
        error_html = f'<p class="error">{html.escape(error)}</p>' if error else ""

        return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
{refresh_tag}
<title>name-me pipeline: {html.escape(self._script_name)}</title>
<style>
  body {{ font: 15px/1.5 system-ui, sans-serif; max-width: 640px;
    margin: 2rem auto; padding: 0 1rem; }}
  h1 {{ font-size: 1.25rem; }}
  .bar-track {{ background: #e5e4e7; border-radius: 6px; height: 14px; overflow: hidden; }}
  .bar-fill {{ background: #7c3aed; height: 100%; transition: width 0.3s; }}
  .muted {{ color: #6b6375; font-size: 0.9rem; }}
  .error {{ color: #c0392b; font-weight: 600; }}
  ul {{ font-size: 0.9rem; color: #6b6375; }}
</style>
</head>
<body>
  <h1>{html.escape(self._script_name)} — {status_word}</h1>
  <p><strong>Current step:</strong> {step}</p>
  {bar_html}
  <p class="muted">Elapsed: {payload['elapsed_seconds']}s · Updated: {payload['updated_at']}</p>
  {error_html}
  <h2>Recent steps</h2>
  <ul>{log_items}</ul>
  <p class="muted">This page regenerates itself on every status update — no server, no
  fetch, just re-open or let the meta-refresh reload it while the script runs.</p>
</body>
</html>
"""
