"""脱敏视觉工作流 Demo 的媒体预处理服务。

图片会被规范化为 JPEG；视频会使用 FFmpeg 均匀抽取最多 8 帧，生成联系表。
服务只处理上传文件，不接受 URL 或任意命令参数。
"""

from __future__ import annotations

import io
import json
import math
import os
import subprocess
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response
from PIL import Image, ImageDraw, ImageOps


HOST = os.environ.get("MEDIA_PREPROCESS_HOST", "0.0.0.0")
PORT = int(os.environ.get("MEDIA_PREPROCESS_PORT", "8002"))
MAX_INPUT_BYTES = int(os.environ.get("MEDIA_PREPROCESS_MAX_INPUT_BYTES", str(100 * 1024 * 1024)))
MAX_VIDEO_SECONDS = float(os.environ.get("MEDIA_PREPROCESS_MAX_VIDEO_SECONDS", "120"))
MAX_FRAMES = 8
FRAME_COLUMNS = 4
FRAME_WIDTH = 480
FRAME_HEIGHT = 300
LABEL_HEIGHT = 30

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}

app = FastAPI(title="Sanitized Vision Demo Media Preprocessor")


def _run(command: list[str], *, timeout: float) -> subprocess.CompletedProcess[str | bytes]:
    try:
        return subprocess.run(
            command,
            check=True,
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=504, detail="媒体处理超时") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail="服务器未找到 FFmpeg 工具") from exc
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.decode("utf-8", errors="replace")[-600:] if exc.stderr else ""
        raise HTTPException(status_code=422, detail=f"媒体解码失败：{detail or 'FFmpeg 返回错误'}") from exc


def _media_kind(filename: str, content_type: str | None) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix in IMAGE_EXTENSIONS or (content_type or "").lower().startswith("image/"):
        return "image"
    if suffix in VIDEO_EXTENSIONS or (content_type or "").lower().startswith("video/"):
        return "video"
    return "unknown"


async def _save_upload(upload: UploadFile, destination: Path) -> int:
    total = 0
    with destination.open("wb") as output:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_INPUT_BYTES:
                raise HTTPException(status_code=413, detail="上传媒体超过 100 MB 限制")
            output.write(chunk)
    if total == 0:
        raise HTTPException(status_code=400, detail="上传文件为空")
    return total


def _normalize_image(path: Path) -> bytes:
    try:
        with Image.open(path) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
            output = io.BytesIO()
            image.save(output, format="JPEG", quality=92, optimize=True)
            return output.getvalue()
    except Exception as exc:
        raise HTTPException(status_code=422, detail="无法识别上传图片") from exc


def _video_duration(path: Path) -> float:
    result = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(path),
        ],
        timeout=20,
    )
    try:
        duration = float(json.loads(result.stdout.decode("utf-8"))["format"]["duration"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail="无法读取视频时长") from exc
    if not math.isfinite(duration) or duration <= 0:
        raise HTTPException(status_code=422, detail="视频时长无效")
    if duration > MAX_VIDEO_SECONDS:
        raise HTTPException(status_code=422, detail="演示视频不能超过 120 秒")
    return duration


def _extract_frame(path: Path, timestamp: float) -> Image.Image:
    result = _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{timestamp:.3f}",
            "-i",
            str(path),
            "-frames:v",
            "1",
            "-f",
            "image2pipe",
            "-vcodec",
            "mjpeg",
            "pipe:1",
        ],
        timeout=30,
    )
    try:
        with Image.open(io.BytesIO(result.stdout)) as frame:
            return frame.convert("RGB").copy()
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"无法读取视频帧（{timestamp:.2f}s）") from exc


def _contact_sheet(path: Path, duration: float, requested_frames: int) -> tuple[bytes, int]:
    frame_count = min(MAX_FRAMES, max(1, requested_frames, 1))
    frame_count = min(frame_count, max(1, math.ceil(duration)))
    # 给 FFmpeg 的末帧解码留出安全边界，避免短视频在 duration 附近取不到完整帧。
    end_time = max(0.0, duration - 0.25)
    timestamps = [0.0] if frame_count == 1 else [end_time * i / (frame_count - 1) for i in range(frame_count)]

    canvas_height = (FRAME_HEIGHT + LABEL_HEIGHT) * 2
    canvas = Image.new("RGB", (FRAME_COLUMNS * FRAME_WIDTH, canvas_height), (24, 24, 24))
    draw = ImageDraw.Draw(canvas)
    for index, timestamp in enumerate(timestamps):
        frame = _extract_frame(path, timestamp)
        frame = ImageOps.contain(frame, (FRAME_WIDTH, FRAME_HEIGHT), method=Image.Resampling.LANCZOS)
        x = (index % FRAME_COLUMNS) * FRAME_WIDTH
        y = (index // FRAME_COLUMNS) * (FRAME_HEIGHT + LABEL_HEIGHT)
        draw.rectangle((x, y, x + FRAME_WIDTH, y + LABEL_HEIGHT - 1), fill=(0, 0, 0))
        draw.text((x + 8, y + 7), f"帧 {index + 1} · {timestamp:.2f}s", fill=(255, 255, 255))
        frame_x = x + (FRAME_WIDTH - frame.width) // 2
        frame_y = y + LABEL_HEIGHT + (FRAME_HEIGHT - frame.height) // 2
        canvas.paste(frame, (frame_x, frame_y))

    output = io.BytesIO()
    canvas.save(output, format="JPEG", quality=88, optimize=True)
    return output.getvalue(), len(timestamps)


@app.get("/healthz")
def healthz() -> dict[str, object]:
    return {
        "status": "ok",
        "service": "media_preprocess",
        "max_frames": MAX_FRAMES,
        "max_video_seconds": MAX_VIDEO_SECONDS,
    }


@app.post("/v1/media/prepare")
async def prepare_media(
    file: UploadFile = File(...),
    max_frames: int = Form(MAX_FRAMES),
) -> Response:
    requested_frames = max(1, min(MAX_FRAMES, max_frames))
    filename = file.filename or "upload"
    kind = _media_kind(filename, file.content_type)

    with tempfile.TemporaryDirectory(prefix="vision_media_prepare_") as temp_dir:
        source = Path(temp_dir) / "input.bin"
        await _save_upload(file, source)

        if kind == "image":
            content = _normalize_image(source)
            source_kind = "image"
            frame_count = 1
        else:
            if kind == "unknown":
                try:
                    content = _normalize_image(source)
                    source_kind = "image"
                    frame_count = 1
                except HTTPException:
                    kind = "video"
            if kind == "video":
                duration = _video_duration(source)
                content, frame_count = _contact_sheet(source, duration, requested_frames)
                source_kind = "video"

    return Response(
        content=content,
        media_type="image/jpeg",
        headers={
            "Content-Disposition": 'attachment; filename="prepared-media.jpg"',
            "X-Media-Source": source_kind,
            "X-Frame-Count": str(frame_count),
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(_, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"error": {"message": str(exc.detail)}})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
