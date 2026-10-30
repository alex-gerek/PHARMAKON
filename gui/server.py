import os
import sys
import json
import shutil
import asyncio
import subprocess
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
        "presets": remaster_engine.PRESETS,
        "demos": demos,
        "status": "ready"
    }

@app.get("/api/presets")
def get_presets():
    return remaster_engine.PRESETS

@app.post("/api/split-and-master")
async def split_and_master_target(request: Request):
    """Decomposes single mixed file into 4 stems and executes deep stem surgery."""
    try:
        body = await request.json()
        target_path = body.get("target_path", "").strip().strip('"').strip("'")
        custom_params = body.get("params", {})
        mode = body.get("mode", "pharmakon1")

        if target_path and not os.path.exists(target_path):
            rel_candidate = PROJECT_DIR / target_path
            if rel_candidate.exists():
                target_path = str(rel_candidate.resolve())

        if not target_path or not os.path.isfile(target_path):
            raise HTTPException(status_code=400, detail=f"Target audio file not found: {target_path}")

        params = dict(remaster_engine.DEFAULT_PARAMS)
        params.update(custom_params)
        params["mode"] = mode

        out_master, metrics, stems_dir = await asyncio.to_thread(
            remaster_engine.split_and_master_single_file, target_path, params
        )

        if not out_master or not os.path.isfile(out_master):
            raise HTTPException(status_code=500, detail="Split & stem mastering failed")

        track_name = os.path.splitext(os.path.basename(target_path))[0]
        out_dir = os.path.dirname(out_master)

        return {
            "success": True,
            "type": "split_stems",
            "original_path": target_path,
            "master_path": out_master,
            "output_dir": out_dir,
            "stems_dir": stems_dir,
            "report_path": metrics.get("report_path") if metrics else None,
            "track_name": track_name,
            "metrics": metrics
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
                "report_path": metrics.get("report_path") if metrics else None,
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
                "report_path": metrics.get("report_path") if metrics else None,
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

@app.get("/api/report")
def get_mastering_report(path: str):
    """Serves the standalone HTML Mastering Report & Certificate."""
    clean_path = urllib.parse.unquote(path).strip().strip('"').strip("'")
    if not os.path.isfile(clean_path):
        candidate = PROJECT_DIR / clean_path
        if candidate.exists():
            clean_path = str(candidate.resolve())
    if not os.path.isfile(clean_path):
        raise HTTPException(status_code=404, detail="Mastering report not found")
    return FileResponse(clean_path, media_type="text/html")

@app.post("/api/open-report")
async def open_report_file(request: Request):
    """Opens HTML report in system default web browser (Chrome, Edge, etc.)."""
    try:
        body = await request.json()
        report_path = body.get("path", "").strip().strip('"').strip("'")
        report_path = urllib.parse.unquote(report_path)
        if report_path.startswith("file:///"):
            report_path = report_path[8:]

        # Smart fallback: if path is empty or not on disk, search candidate directories
        if not report_path or not os.path.isfile(report_path):
            candidates = [
                PROJECT_DIR / report_path if report_path else None,
                PROJECT_DIR / "demo_audio" / "bronze_psalter" / "Remaster" / "Bronze_Psalter_Demo - MASTERING_REPORT.html",
                PROJECT_DIR / "demo_audio" / "gravity_stems" / "Remaster" / "Gravity_Has_An_Address - MASTERING_REPORT.html",
            ]
            for c in candidates:
                if c and c.exists() and os.path.isfile(str(c)):
                    report_path = str(c.resolve())
                    break

        if not report_path or not os.path.isfile(report_path):
            # Also search for any *MASTERING_REPORT.html in PROJECT_DIR
            for root, dirs, files in os.walk(str(PROJECT_DIR)):
                for f in files:
                    if f.endswith("MASTERING_REPORT.html"):
                        candidate = os.path.join(root, f)
                        if os.path.isfile(candidate):
                            report_path = candidate
                            break
                if report_path and os.path.isfile(report_path):
                    break

        if not report_path or not os.path.isfile(report_path):
            return {"success": False, "error": "Report not found on disk. Please render a master first!"}

        report_path = os.path.normpath(report_path)
        if sys.platform == "win32":
            os.startfile(report_path)
            return {"success": True, "opened": report_path}

        return {"success": False, "error": "Platform not supported"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/save-image-as")
async def save_image_as(request: Request):
    """Opens native Windows Save-As dialog to save PNG image to user-chosen directory."""
    try:
        import base64
        body = await request.json()
        default_name = body.get("filename", "MASTERING_CERTIFICATE.png")
        data_url = body.get("data_url", "")
        if "," in data_url:
            data_url = data_url.split(",", 1)[1]

        image_bytes = base64.b64decode(data_url)
        save_dest = await asyncio.to_thread(_run_save_image_dialog, default_name)

        if save_dest:
            save_dest = os.path.normpath(save_dest)
            with open(save_dest, "wb") as f:
                f.write(image_bytes)
            return {"success": True, "saved_path": save_dest, "filename": os.path.basename(save_dest)}
        return {"success": False, "cancelled": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

def _run_save_stems_zip_dialog(default_name: str) -> str:
    """Threaded native Tkinter Save As dialog for Stems ZIP archive."""
    import tkinter as tk
    import tkinter.filedialog as fd

    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)

    init_dir = os.path.expanduser("~/Music")
    if not os.path.exists(init_dir):
        init_dir = os.path.expanduser("~/Desktop")

    save_dest = fd.asksaveasfilename(
        title="PHARMAKON // Save Stems Pack ZIP As...",
        initialdir=init_dir,
        initialfile=default_name,
        defaultextension=".zip",
        filetypes=[
            ("ZIP Archive (*.zip)", "*.zip"),
            ("All Files (*.*)", "*.*")
        ]
    )
    root.destroy()
    return save_dest

@app.get("/api/download-stems")
async def download_stems_zip(stems_dir: str):
    """Packages 4 stems from stems_dir into a high-speed zip file for direct download."""
    import zipfile
    from fastapi.responses import FileResponse

    clean_dir = urllib.parse.unquote(stems_dir).strip().strip('"').strip("'")
    if not os.path.isdir(clean_dir):
        candidate = PROJECT_DIR / clean_dir
        if candidate.is_dir():
            clean_dir = str(candidate.resolve())

    if not os.path.isdir(clean_dir):
        raise HTTPException(status_code=404, detail="Stems directory not found")

    track_name = os.path.basename(clean_dir).replace("_Stems", "")
    zip_filename = f"{track_name} - STEMS.zip"
    cached_zip = os.path.join(clean_dir, zip_filename)

    def _pack_zip():
        with zipfile.ZipFile(cached_zip, "w", zipfile.ZIP_STORED) as zf:
            for f in os.listdir(clean_dir):
                if f.lower().endswith(('.wav', '.flac', '.mp3', '.ogg')) and not f.startswith('.'):
                    if not f.endswith('.zip'):
                        fp = os.path.join(clean_dir, f)
                        if os.path.isfile(fp):
                            zf.write(fp, arcname=f)

    await asyncio.to_thread(_pack_zip)

    return FileResponse(
        cached_zip,
        media_type="application/zip",
        filename=zip_filename
    )

@app.post("/api/save-stems-as")
async def save_stems_zip_as(request: Request):
    """Opens native Windows Save-As dialog and packages stems into user-selected ZIP file."""
    try:
        import zipfile
        body = await request.json()
        stems_dir = body.get("stems_dir", "").strip().strip('"').strip("'")
        if not stems_dir or not os.path.isdir(stems_dir):
            candidate = PROJECT_DIR / stems_dir
            if candidate.is_dir():
                stems_dir = str(candidate.resolve())

        if not stems_dir or not os.path.isdir(stems_dir):
            return {"success": False, "error": f"Stems directory not found: {stems_dir}"}

        track_name = os.path.basename(stems_dir).replace("_Stems", "")
        default_name = f"{track_name} - STEMS.zip"
        save_dest = await asyncio.to_thread(_run_save_stems_zip_dialog, default_name)

        if save_dest:
            save_dest = os.path.normpath(save_dest)
            with zipfile.ZipFile(save_dest, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for f in os.listdir(stems_dir):
                    if f.lower().endswith(('.wav', '.flac', '.mp3', '.ogg')) and not f.startswith('.'):
                        fp = os.path.join(stems_dir, f)
                        if os.path.isfile(fp):
                            zip_file.write(fp, arcname=f)
            return {"success": True, "saved_path": save_dest, "filename": os.path.basename(save_dest)}
        else:
            return {"success": False, "cancelled": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _run_save_as_dialog(master_path: str) -> str:
    """Threaded native Tkinter Save As dialog helper."""
    import tkinter as tk
    import tkinter.filedialog as fd

    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)

    default_name = os.path.basename(master_path)
    init_dir = os.path.expanduser("~/Music")
    if not os.path.exists(init_dir):
        init_dir = os.path.expanduser("~/Desktop")

    save_dest = fd.asksaveasfilename(
        title="PHARMAKON // Save Lossless Master As...",
        initialdir=init_dir,
        initialfile=default_name,
        defaultextension=".wav",
        filetypes=[
            ("WAV Lossless Audio (*.wav)", "*.wav"),
            ("All Files (*.*)", "*.*")
        ]
    )
    root.destroy()
    return save_dest

@app.post("/api/save-as")
async def save_master_as(request: Request):
    """Opens native Windows Save-As dialog to save master WAV to any user-chosen directory."""
    try:
        body = await request.json()
        master_path = body.get("master_path", "").strip().strip('"').strip("'")
        
        # Unquote and resolve relative path if needed
        master_path = urllib.parse.unquote(master_path)
        if master_path.startswith("file:///"):
            master_path = master_path[8:]
        
        if master_path and not os.path.isabs(master_path):
            candidate = PROJECT_DIR / master_path
            if candidate.exists():
                master_path = str(candidate.resolve())

        if not master_path or not os.path.isfile(master_path):
            raise HTTPException(status_code=400, detail="Master audio file not found")

        save_dest = await asyncio.to_thread(_run_save_as_dialog, master_path)

        if save_dest:
            save_dest = os.path.normpath(save_dest)
            shutil.copy2(master_path, save_dest)
            return {"success": True, "saved_path": save_dest, "filename": os.path.basename(save_dest)}
        return {"success": False, "cancelled": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/reveal")
async def reveal_in_explorer(request: Request):
    """Reveals target file or folder in native Windows Explorer."""
    try:
        body = await request.json()
        target_path = body.get("path", "").strip().strip('"').strip("'")
        if not target_path:
            return {"success": False, "error": "No path provided"}

        target_path = urllib.parse.unquote(target_path)
        if target_path.startswith("file:///"):
            target_path = target_path[8:]

        # Resolve relative path against project directory
        if not os.path.isabs(target_path):
            candidate = (PROJECT_DIR / target_path).resolve()
            if candidate.exists():
                target_path = str(candidate)

        target_path = os.path.normpath(target_path)

        if sys.platform == "win32":
            if os.path.isfile(target_path):
                subprocess.Popen(["explorer", f"/select,{target_path}"])
                return {"success": True, "opened": target_path}
            elif os.path.isdir(target_path):
                subprocess.Popen(["explorer", target_path])
                return {"success": True, "opened": target_path}
            else:
                # Try parent directory
                parent = os.path.dirname(target_path)
                if os.path.isdir(parent):
                    subprocess.Popen(["explorer", parent])
                    return {"success": True, "opened": parent}

        return {"success": False, "error": f"Folder not found: {target_path}"}
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
        return FileResponse(
            str(index_file),
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
    return HTMLResponse("<h1>PHARMAKON Studio Console</h1><p>UI initializing...</p>")

if __name__ == "__main__":
    uvicorn.run("server:app", host="127.0.0.1", port=7860, reload=False)
