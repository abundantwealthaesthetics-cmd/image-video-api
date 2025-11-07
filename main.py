from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
import tempfile, os, requests, subprocess

app = FastAPI()

@app.post("/render")
def render(payload: dict):
    images = payload.get("images", [])
    if not images or len(images) < 1:
        raise HTTPException(400, "No image URLs provided")

    width  = int(payload.get("width", 1080))
    height = int(payload.get("height", 1920))
    fps    = int(payload.get("fps", 6))
    dur    = float(payload.get("per_image_seconds", 0.2))
    loops  = int(payload.get("loop", 3))

    tmp = tempfile.TemporaryDirectory()
    try:
        # Download images
        img_paths = []
        for i, url in enumerate(images):
            p = os.path.join(tmp.name, f"{i:03d}.jpg")
            r = requests.get(url, timeout=60)
            if r.status_code != 200:
                raise HTTPException(400, f"Failed to download: {url}")
            with open(p, "wb") as f: f.write(r.content)
            img_paths.append(p)

        # Build concat file
        concat = os.path.join(tmp.name, "list.txt")
        with open(concat, "w") as f:
            for _ in range(loops):
                for p in img_paths:
                    f.write(f"file '{p}'\n")
                    f.write(f"duration {dur}\n")
            f.write(f"file '{img_paths[-1]}'\n")

        # Render with ffmpeg
        out = os.path.join(tmp.name, "final.mp4")
        cmd = [
            "ffmpeg","-y","-f","concat","-safe","0","-i",concat,
            "-vf",f"scale={width}:{height}:force_original_aspect_ratio=cover,crop={width}:{height},format=yuv420p",
            "-r",str(fps),"-c:v","libx264","-pix_fmt","yuv420p",out
        ]
        subprocess.check_call(cmd)

        def iterfile():
            with open(out, "rb") as f:
                while chunk := f.read(1024 * 1024):
                    yield chunk
        return StreamingResponse(iterfile(), media_type="video/mp4",
                                 headers={"Content-Disposition": "inline; filename=final.mp4"})
    finally:
        tmp.cleanup()
