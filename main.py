"""FastAPI application for Milestone video export."""

import logging
import os
import subprocess
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException

# Configure logging - set DEBUG level for image_server module
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logging.getLogger('image_server').setLevel(logging.DEBUG)
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from milestone_client import MilestoneClient
from image_server import ImageServerClient
from config import MILESTONE_SERVER_URL

# Create exports directory
EXPORTS_DIR = Path(__file__).parent / "exports"
EXPORTS_DIR.mkdir(exist_ok=True)

# Maximum export duration in minutes
MAX_EXPORT_MINUTES = 10

app = FastAPI(title="Milestone Video Export")

# Global client instance
milestone_client: Optional[MilestoneClient] = None


class ExportRequest(BaseModel):
    camera_id: str
    start_time: str  # ISO format
    end_time: str    # ISO format


class ExportResponse(BaseModel):
    success: bool
    filename: Optional[str] = None
    download_url: Optional[str] = None
    error: Optional[str] = None


def get_milestone_client() -> MilestoneClient:
    """Get or create authenticated Milestone client."""
    global milestone_client
    if milestone_client is None:
        milestone_client = MilestoneClient()
        milestone_client.authenticate()
    return milestone_client


def check_ffmpeg() -> bool:
    """Check if FFmpeg is available."""
    return shutil.which("ffmpeg") is not None


def iso_to_unix_ms(iso_string: str) -> int:
    """Convert ISO 8601 timestamp to Unix milliseconds."""
    # Handle various ISO formats
    iso_string = iso_string.replace("Z", "+00:00")
    dt = datetime.fromisoformat(iso_string)
    return int(dt.timestamp() * 1000)


@app.on_event("startup")
async def startup_event():
    """Validate configuration on startup."""
    if not MILESTONE_SERVER_URL:
        print("WARNING: MILESTONE_SERVER_URL not configured")
    if not check_ffmpeg():
        print("WARNING: FFmpeg not found - exports will fail")


@app.get("/api/cameras")
async def list_cameras():
    """List all available cameras."""
    try:
        client = get_milestone_client()
        cameras = client.get_cameras()
        return {"cameras": cameras}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/export", response_model=ExportResponse)
async def export_video(request: ExportRequest):
    """Export video from specified camera and time range."""

    # Check FFmpeg availability
    if not check_ffmpeg():
        return ExportResponse(success=False, error="FFmpeg not installed on server")

    # Parse timestamps
    try:
        start_ms = iso_to_unix_ms(request.start_time)
        end_ms = iso_to_unix_ms(request.end_time)
    except ValueError as e:
        return ExportResponse(success=False, error=f"Invalid timestamp format: {e}")

    # Validate time range
    if end_ms <= start_ms:
        return ExportResponse(success=False, error="End time must be after start time")

    duration_minutes = (end_ms - start_ms) / 1000 / 60
    if duration_minutes > MAX_EXPORT_MINUTES:
        return ExportResponse(
            success=False,
            error=f"Time range exceeds {MAX_EXPORT_MINUTES} minute limit ({duration_minutes:.1f} minutes requested)"
        )

    try:
        client = get_milestone_client()

        # Get recording server for this camera
        host, port = client.get_camera_recording_server(request.camera_id)
        # Use ImageServer token (from SOAP Login), NOT OAuth token
        token = client.get_imageserver_token()

        # Generate output filename
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_filename = f"export_{timestamp}.mp4"
        output_path = EXPORTS_DIR / output_filename

        # Connect to ImageServer
        image_client = ImageServerClient()
        try:
            image_client.connect(host, port, request.camera_id, token)

            # Seek to start time
            image_client.goto(start_ms)

            # Start FFmpeg process
            ffmpeg_cmd = [
                "ffmpeg",
                "-y",  # Overwrite output
                "-f", "image2pipe",
                "-framerate", "15",
                "-i", "-",
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-preset", "fast",
                str(output_path)
            ]

            ffmpeg_proc = subprocess.Popen(
                ffmpeg_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            frame_count = 0
            last_timestamp = None

            try:
                while True:
                    headers, jpeg_data = image_client.next_frame()

                    if not jpeg_data:
                        # No more frames
                        break

                    frame_timestamp = image_client.get_frame_timestamp(headers)

                    if frame_timestamp is None:
                        continue

                    # Check if we've passed the end time
                    if frame_timestamp >= end_ms:
                        break

                    # Write frame to FFmpeg
                    ffmpeg_proc.stdin.write(jpeg_data)
                    frame_count += 1
                    last_timestamp = frame_timestamp

            finally:
                ffmpeg_proc.stdin.close()
                ffmpeg_proc.wait()

        finally:
            image_client.close()

        # Check if export succeeded
        if not output_path.exists() or output_path.stat().st_size == 0:
            stderr = ffmpeg_proc.stderr.read().decode() if ffmpeg_proc.stderr else ""
            return ExportResponse(
                success=False,
                error=f"Export failed - no video data. FFmpeg: {stderr[:500]}"
            )

        if frame_count == 0:
            output_path.unlink(missing_ok=True)
            return ExportResponse(
                success=False,
                error="No frames found in the specified time range"
            )

        return ExportResponse(
            success=True,
            filename=output_filename,
            download_url=f"/api/export/{output_filename}/download"
        )

    except Exception as e:
        return ExportResponse(success=False, error=str(e))


@app.get("/api/export/{filename}/download")
async def download_export(filename: str):
    """Download a completed export file."""
    # Sanitize filename to prevent directory traversal
    safe_filename = Path(filename).name
    file_path = EXPORTS_DIR / safe_filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Export file not found")

    return FileResponse(
        path=file_path,
        filename=safe_filename,
        media_type="video/mp4"
    )


# Mount static files last to not override API routes
app.mount("/", StaticFiles(directory="static", html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
