from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import tempfile, os, requests, subprocess, uuid, threading

app = FastAPI()

JOBS = {}  # job_id -> {"status": "...", "path": "...", "error": "..."}
LOCK = threading.Lock()

class RenderPayload(BaseModel):
    images: list[str]
    width: int = 1920
    height: int = 1080
    fps: int = 6
    per_image_seconds: float = 0.2
    loop: int = 3

def _run_ffmpeg(job_id: str, payload: RenderPayload):
    tmpdir = tempfile.mkdtemp()
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36"
        }
        img_paths = []
        for i, url in enumerate(payload.images):
            p = os.path.join(tmpdir, f"{i:03d}.jpg")
            r = requests.get(url, headers=headers, timeout=60, allow_redirects=True)
            r.raise_for_status()
            with open(p, "wb") as f: f.write(r.content)
            img_paths.append(p)

        concat = os.path.join(tmpdir, "list.txt")
        with open(concat, "w") as f:
            for _ in range(payload.loop):
                for p in img_paths:
                    f.write(f"file '{p}'\n")
                    f.write(f"duration {payload.per_image_seconds}\n")
            f.write(f"file '{img_paths[-1]}'\n")

        out = os.path.join(tmpdir, "final.mp4")
        cmd = [
            "ffmpeg","-y","-f","concat","-safe","0","-i",concat,
            "-vf",f"scale={payload.width}:{payload.height}:force_original_aspect_ratio=cover,"
                  f"crop={payload.width}:{payload.height},format=yuv420p",
            "-r",str(payload.fps),"-c:v","libx264","-pix_fmt","yuv420p", out
        ]
        subprocess.check_call(cmd)

        with LOCK:
            JOBS[job_id]["status"] = "done"
            JOBS[job_id]["path"] = out
    except Exception as e:
        with LOCK:
            JOBS[job_id]["status"] = "error"
            JOBS[job_id]["error"] = str(e)

@app.get("/")
def health():
    return {"ok": True}

@app.post("/render_async")
def render_async(payload: RenderPayload, background: BackgroundTasks):
    if not payload.images:
        raise HTTPException(400, "No image URLs provided")
    job_id = uuid.uuid4().hex
    with LOCK:
        JOBS[job_id] = {"status": "processing", "path": None, "error": None}
    background.add_task(_run_ffmpeg, job_id, payload)
    return {"job_id": job_id}

@app.get("/status/{job_id}")
def status(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Unknown job_id")
    return {"status": job["status"]}

@app.get("/download/{job_id}")
def download(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Unknown job_id")
    if job["status"] != "done" or not job["path"]:
        raise HTTPException(425, "Not ready")
    return FileResponse(job["path"], media_type="video/mp4", filename="final.mp4")
