from __future__ import annotations

import io

from fastapi.testclient import TestClient
from PIL import Image

from services import media_preprocess_server as media


client = TestClient(media.app)


def test_normalize_image_returns_rgb_jpeg(tmp_path):
    source = tmp_path / "sample.png"
    Image.new("RGBA", (32, 20), (20, 100, 200, 128)).save(source)

    content = media._normalize_image(source)

    with Image.open(io.BytesIO(content)) as result:
        assert result.format == "JPEG"
        assert result.mode == "RGB"
        assert result.size == (32, 20)


def test_contact_sheet_caps_video_samples_at_eight(monkeypatch, tmp_path):
    source = tmp_path / "sample.mp4"
    source.write_bytes(b"synthetic-video-placeholder")
    calls: list[float] = []

    def fake_extract_frame(_path, timestamp):
        calls.append(timestamp)
        return Image.new("RGB", (80, 40), (20, 100, 200))

    monkeypatch.setattr(media, "_extract_frame", fake_extract_frame)

    content, frame_count = media._contact_sheet(source, duration=12.0, requested_frames=99)

    assert frame_count == 8
    assert len(calls) == 8
    with Image.open(io.BytesIO(content)) as result:
        assert result.format == "JPEG"
        assert result.size == (media.FRAME_COLUMNS * media.FRAME_WIDTH, 2 * (media.FRAME_HEIGHT + media.LABEL_HEIGHT))


def test_contact_sheet_uses_one_frame_for_short_video(monkeypatch, tmp_path):
    source = tmp_path / "short.mp4"
    source.write_bytes(b"synthetic-video-placeholder")
    calls: list[float] = []

    monkeypatch.setattr(
        media,
        "_extract_frame",
        lambda _path, timestamp: (
            calls.append(timestamp) or Image.new("RGB", (40, 40), (10, 10, 10))
        ),
    )

    _, frame_count = media._contact_sheet(source, duration=0.4, requested_frames=8)

    assert frame_count == 1
    assert calls == [0.0]


def test_empty_upload_returns_structured_error():
    response = client.post(
        "/v1/media/prepare",
        files={"file": ("empty.jpg", b"", "image/jpeg")},
    )

    assert response.status_code == 400
    assert response.json() == {"error": {"message": "上传文件为空"}}


def test_oversized_upload_is_rejected(monkeypatch):
    monkeypatch.setattr(media, "MAX_INPUT_BYTES", 4)

    response = client.post(
        "/v1/media/prepare",
        files={"file": ("large.jpg", b"12345", "image/jpeg")},
    )

    assert response.status_code == 413
    assert response.json()["error"]["message"] == "上传媒体超过 100 MB 限制"


def test_video_processing_failure_returns_structured_error(monkeypatch):
    def fail(_path):
        raise media.HTTPException(status_code=422, detail="演示 FFmpeg 失败")

    monkeypatch.setattr(media, "_video_duration", fail)

    response = client.post(
        "/v1/media/prepare",
        files={"file": ("broken.mp4", b"not-a-video", "video/mp4")},
    )

    assert response.status_code == 422
    assert response.json() == {"error": {"message": "演示 FFmpeg 失败"}}
