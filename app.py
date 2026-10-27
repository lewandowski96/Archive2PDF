"""
FastAPI Backend for ComicFlux Lossless Comic to PDF Web Application.
"""

import os
import io
import re
import uuid
import shutil
import zipfile
import tempfile
from typing import Dict, List, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from converter import (
    ComicExtractor,
    LosslessConverter,
    ComicMetadata,
    UNAR_PATH,
    VALID_IMAGE_EXTS,
    natural_sort_key
)

app = FastAPI(title="ComicFlux Lossless Comic Converter", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMP_SESSIONS_DIR = os.path.join(tempfile.gettempdir(), "comicflux_sessions")
os.makedirs(TEMP_SESSIONS_DIR, exist_ok=True)

# In-memory session tracking
# session_id -> { "files": { file_id: {...} } }
sessions: Dict[str, Dict] = {}

def get_session(session_id: str) -> Dict:
    if session_id not in sessions:
        session_folder = os.path.join(TEMP_SESSIONS_DIR, session_id)
        os.makedirs(session_folder, exist_ok=True)
        sessions[session_id] = {
            "folder": session_folder,
            "items": {}
        }
    return sessions[session_id]

@app.get("/api/system_info")
def system_info():
    return {
        "engine": "img2pdf direct stream injector (100% Lossless)",
        "unar_available": bool(UNAR_PATH and os.path.exists(UNAR_PATH)),
        "unar_path": UNAR_PATH or "Not found",
        "supported_formats": [".cbz", ".cbr", ".zip", ".rar", ".cbt", ".cb7"],
        "lossless_guarantee": "Direct DCT/Flate stream embedding without generational loss or pixel re-encoding."
    }

@app.post("/api/upload")
async def upload_comic(file: UploadFile = File(...), session_id: Optional[str] = Form(None)):
    if not session_id:
        session_id = str(uuid.uuid4())
    
    session = get_session(session_id)
    item_id = str(uuid.uuid4())
    filename = file.filename or "comic.cbz"
    ext = os.path.splitext(filename)[1].lower()
    
    item_dir = os.path.join(session["folder"], item_id)
    os.makedirs(item_dir, exist_ok=True)
    
    archive_path = os.path.join(item_dir, filename)
    with open(archive_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
        
    file_size = os.path.getsize(archive_path)

    # Extract pages and parse metadata
    extract_dir = os.path.join(item_dir, "extracted")
    os.makedirs(extract_dir, exist_ok=True)

    try:
        pages, metadata = ComicExtractor.extract_archive(archive_path, extract_dir)
        page_info = LosslessConverter.inspect_images(pages)
    except Exception as e:
        shutil.rmtree(item_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail=f"Failed to process archive: {str(e)}")

    if not pages:
        shutil.rmtree(item_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail="No readable comic book pages found in archive.")

    session["items"][item_id] = {
        "item_id": item_id,
        "filename": filename,
        "ext": ext,
        "size_bytes": file_size,
        "archive_path": archive_path,
        "extract_dir": extract_dir,
        "pages": pages,
        "page_info": page_info,
        "metadata": metadata.to_dict(),
        "status": "ready",
        "progress": 0.0,
        "status_message": "Ready to convert",
        "pdf_path": None,
        "stats": None
    }

    return {
        "session_id": session_id,
        "item": {
            "id": item_id,
            "filename": filename,
            "format": ext.replace(".", "").upper(),
            "size": file_size,
            "page_count": len(pages),
            "pages": page_info[:12], # return first 12 for quick gallery preview
            "total_pages": len(pages),
            "metadata": metadata.to_dict(),
            "status": "ready"
        }
    }

@app.get("/api/page_image/{session_id}/{item_id}/{page_index}")
def get_page_image(session_id: str, item_id: str, page_index: int):
    session = sessions.get(session_id)
    if not session or item_id not in session["items"]:
        raise HTTPException(status_code=404, detail="Item not found")

    item = session["items"][item_id]
    if page_index < 0 or page_index >= len(item["pages"]):
        raise HTTPException(status_code=404, detail="Page not found")

    image_path = item["pages"][page_index]
    ext = os.path.splitext(image_path)[1].lower()
    media_type = f"image/{ext.replace('.', '')}"
    if ext in ('.jpg', '.jpeg'):
        media_type = "image/jpeg"
    elif ext == '.png':
        media_type = "image/png"
    elif ext == '.webp':
        media_type = "image/webp"

    return FileResponse(image_path, media_type=media_type)

@app.post("/api/convert/{session_id}/{item_id}")
def convert_item(session_id: str, item_id: str):
    session = sessions.get(session_id)
    if not session or item_id not in session["items"]:
        raise HTTPException(status_code=404, detail="Item not found")

    item = session["items"][item_id]
    item["status"] = "converting"
    item["progress"] = 0.1
    item["status_message"] = "Starting conversion..."

    output_pdf_name = f"{os.path.splitext(item['filename'])[0]}.pdf"
    output_pdf_path = os.path.join(session["folder"], item_id, output_pdf_name)

    # Reconstitute metadata if available
    meta_dict = item.get("metadata", {})
    metadata = ComicMetadata()
    for k, v in meta_dict.items():
        if hasattr(metadata, k):
            setattr(metadata, k, v)

    def progress_callback(msg: str, prog: float):
        item["status_message"] = msg
        item["progress"] = prog

    try:
        stats = LosslessConverter.convert_to_pdf(
            item["pages"],
            output_pdf_path,
            metadata=metadata,
            progress_callback=progress_callback
        )
        item["status"] = "completed"
        item["progress"] = 1.0
        item["status_message"] = "Completed losslessly!"
        item["pdf_path"] = output_pdf_path
        item["stats"] = stats
        return {
            "success": True,
            "item_id": item_id,
            "stats": stats,
            "download_url": f"/api/download/{session_id}/{item_id}"
        }
    except Exception as e:
        item["status"] = "failed"
        item["status_message"] = f"Error: {str(e)}"
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/download/{session_id}/{item_id}")
def download_pdf(session_id: str, item_id: str):
    session = sessions.get(session_id)
    if not session or item_id not in session["items"]:
        raise HTTPException(status_code=404, detail="Item not found")

    item = session["items"][item_id]
    pdf_path = item.get("pdf_path")
    if not pdf_path or not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="PDF has not been generated yet.")

    filename = os.path.basename(pdf_path)
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=filename,
        content_disposition_type="attachment"
    )

@app.get("/api/download_all/{session_id}")
def download_all_zip(session_id: str):
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    completed_items = [
        item for item in session["items"].values()
        if item.get("status") == "completed" and item.get("pdf_path") and os.path.exists(item["pdf_path"])
    ]

    if not completed_items:
        raise HTTPException(status_code=400, detail="No completed PDFs to download.")

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in completed_items:
            pdf_path = item["pdf_path"]
            zf.write(pdf_path, arcname=os.path.basename(pdf_path))

    zip_buffer.seek(0)
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="converted_comics_lossless.zip"'}
    )

# Static files mounting
if os.path.exists(STATIC_DIR):
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=8765, reload=True)
