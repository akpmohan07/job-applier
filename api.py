import asyncio
import json
import logging
import queue
import threading
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import orchestrator
import sheets_logger

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class RunRequest(BaseModel):
    urls: list[str]
    profile: str = ""


@app.post("/run")
async def run_jobs(req: RunRequest):
    """
    SSE endpoint — streams log lines then a final JSON result line.
    Frontend reads the stream and updates the UI live.
    """
    from pathlib import Path

    profile_text = req.profile or (
        Path("profile.md").read_text() if Path("profile.md").exists() else ""
    )

    log_queue: queue.Queue = queue.Queue()
    results_holder: dict = {}

    class _QueueHandler(logging.Handler):
        def emit(self, record):
            log_queue.put(self.format(record))

    handler = _QueueHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s  %(message)s", datefmt="%H:%M:%S"))
    orch_logger = logging.getLogger("orchestrator")
    orch_logger.addHandler(handler)

    def _run():
        try:
            results_holder["data"] = asyncio.run(
                orchestrator.process_jobs(req.urls, profile_text)
            )
        except Exception as e:
            results_holder["error"] = str(e)
        finally:
            log_queue.put("__DONE__")

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    async def event_stream():
        while True:
            await asyncio.sleep(0.1)
            while not log_queue.empty():
                msg = log_queue.get_nowait()
                if msg == "__DONE__":
                    orch_logger.removeHandler(handler)
                    if "error" in results_holder:
                        yield f"data: {json.dumps({'type': 'error', 'message': results_holder['error']})}\n\n"
                    else:
                        results = results_holder.get("data", [])
                        try:
                            sheets_logger.log_results(results)
                        except Exception:
                            pass
                        yield f"data: {json.dumps({'type': 'results', 'data': results})}\n\n"
                    return
                yield f"data: {json.dumps({'type': 'log', 'message': msg})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/health")
def health():
    return {"status": "ok"}
