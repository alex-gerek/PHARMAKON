import os
import sys
import json
import urllib.parse
from pathlib import Path

# Add parent directory to path so remaster_engine can be imported
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_DIR))

import remaster_engine
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(title="PHARMAKON Studio Console", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = PROJECT_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

DEMO_DIR = PROJECT_DIR / "demo_audio"

# Bundled demo audio paths located directly inside the repository
DEMO_TRACKS = [
    {
        "id": "bronze_psalter",
        "title": "Bronze Psalter (Single WAV)",
        "subtitle": "AI De-Harshing & Tape Saturation",
        "path": str(DEMO_DIR / "bronze_psalter" / "Bronze_Psalter_Demo.wav"),
        "rel_path": "demo_audio/bronze_psalter/Bronze_Psalter_Demo.wav",
        "type": "file"
    },
    {
        "id": "gravity_stems",
        "title": "GRAVITY HAS AN ADDRESS (4 Stems)",
        "subtitle": "Stem Mastering & Sub Crossover",
        "path": str(DEMO_DIR / "gravity_stems"),
        "rel_path": "demo_audio/gravity_stems",
        "type": "stems"
    }
]

@app.get("/api/demos")
def get_demos():
    return {"demos": DEMO_TRACKS}

@app.post("/api/browse-native")
def browse_native(mode: str = "file"):
    """Opens native Windows file/folder picker dialog directly on user desktop."""
    try:
        import tkinter as tk
        import tkinter.filedialog as fd
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)

        init_dir = r"D:\КЛИПЫ\Reels" if os.path.exists(r"D:\КЛИПЫ\Reels") else str(Path.home())

        if mode == "folder":
            selected = fd.askdirectory(title="PHARMAKON // Select Stems Folder", initialdir=init_dir)
        else:
            selected = fd.askopenfilename(
                title="PHARMAKON // Select Audio File",
                initialdir=init_dir,
                filetypes=[
                    ("Audio Files (*.wav, *.mp3, *.flac, *.ogg)", "*.wav;*.mp3;*.flac;*.ogg;*.aiff;*.aif"),
                    ("All Files (*.*)", "*.*")
                ]
            )
        root.destroy()
        if selected:
            selected = os.path.normpath(selected)
            return {"success": True, "selected_path": selected}
        return {"success": False, "selected_path": ""}
    except Exception as e:
        return {"success": False, "error": str(e), "selected_path": ""}

@app.get("/api/system-info")
def get_system_info():
    demos = [d for d in DEMO_TRACKS if os.path.exists(d["path"])]
    return {
        "engine": "PHARMAKON 2.0 DSP",
        "author": "Lex Gerek",
        "default_params": remaster_engine.DEFAULT_PARAMS,
        "demos": demos,
        "status": "ready"
    }

@app.post("/api/process")
async def process_target(request: Request):
    try:
        body = await request.json()
        target_path = body.get("target_path", "").strip().strip('"').strip("'")
        mode = body.get("mode", "pharmakon1")
        custom_params = body.get("params", {})

        # Resolve relative paths against project root (e.g. demo_audio/...)
        if target_path and not os.path.exists(target_path):
            rel_candidate = PROJECT_DIR / target_path
            if rel_candidate.exists():
                target_path = str(rel_candidate.resolve())

        params = dict(remaster_engine.DEFAULT_PARAMS)
        params.update(custom_params)
        params["mode"] = mode

        if not target_path or not os.path.exists(target_path):
            raise HTTPException(status_code=400, detail=f"Target path not found: {target_path}")

        if os.path.isfile(target_path):
            out_file, metrics = remaster_engine.process_single_file(target_path, params=params, open_folder=False)
            if not out_file:
                raise HTTPException(status_code=500, detail="Processing failed")
            out_dir = os.path.dirname(out_file)
            return {
                "success": True,
                "type": "file",
                "original_path": target_path,
                "master_path": out_file,
                "output_dir": out_dir,
                "track_name": os.path.splitext(os.path.basename(target_path))[0],
                "metrics": metrics
            }
        elif os.path.isdir(target_path):
            master_path, metrics = remaster_engine.process_stems_folder(target_path, params=params, open_folder=False)
            if not master_path:
                raise HTTPException(status_code=500, detail="Stems processing failed")
            out_dir = os.path.dirname(master_path)
            raw_path = (metrics.get('raw_sum_path') if metrics else None) or os.path.join(out_dir, f"{os.path.basename(target_path)} - RAW_SUM.wav")
            return {
                "success": True,
                "type": "stems",
                "original_path": raw_path,
                "master_path": master_path,
                "output_dir": out_dir,
                "track_name": os.path.basename(target_path),
                "metrics": metrics
            }
        else:
            raise HTTPException(status_code=400, detail="Invalid target type")

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/upload-binary")
async def upload_binary(request: Request, filename: str):
    """Direct streaming binary upload for drag & drop from browser without multipart dependency."""
    try:
        clean_name = os.path.basename(filename)
        save_path = UPLOAD_DIR / clean_name
        body = await request.body()
        with open(save_path, "wb") as f:
            f.write(body)
        return {
            "success": True,
            "saved_path": str(save_path),
            "filename": clean_name,
            "size": len(body)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stream")
def stream_audio(path: str):
    """Stream audio file for synchronized in-browser A/B comparison."""
    clean_path = urllib.parse.unquote(path).strip().strip('"').strip("'")
    if not os.path.isfile(clean_path):
        raise HTTPException(status_code=404, detail="Audio file not found")
    return FileResponse(clean_path, media_type="audio/wav")

@app.post("/api/reveal")
async def reveal_in_explorer(request: Request):
    try:
        body = await request.json()
        folder_path = body.get("path", "").strip().strip('"').strip("'")
        if os.path.isfile(folder_path):
            folder_path = os.path.dirname(folder_path)
        if os.path.isdir(folder_path) and sys.platform == "win32":
            os.system(f'explorer "{folder_path}"')
            return {"success": True}
        return {"success": False, "error": "Folder not found"}
    except Exception as e:
        return {"success": False, "error": str(e)}

# Mount static files for the UI
STATIC_DIR = SCRIPT_DIR / "static"
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/")
def get_index():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return HTMLResponse("<h1>PHARMAKON Studio Console</h1><p>UI initializing...</p>")

if __name__ == "__main__":
    uvicorn.run("server:app", host="127.0.0.1", port=7860, reload=False)
