from __future__ import annotations

import io
import json
import subprocess

import pytest
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
    calls: list[int] = []

    def fake_extract_frames(_path, indices):
        calls.extend(indices)
        return [Image.new("RGB", (80, 40), (20, 100, 200)) for _ in indices]

    monkeypatch.setattr(media, "_video_frame_timestamps", lambda _: list(range(12)))
    monkeypatch.setattr(media, "_extract_frames", fake_extract_frames)

    content, frame_count = media._contact_sheet(source, duration=12.0, requested_frames=99)

    assert frame_count == 8
    assert calls == [0, 2, 3, 5, 6, 8, 9, 11]
    with Image.open(io.BytesIO(content)) as result:
        assert result.format == "JPEG"
        assert result.size == (media.FRAME_COLUMNS * media.FRAME_WIDTH, 2 * (media.FRAME_HEIGHT + media.LABEL_HEIGHT))


def test_contact_sheet_uses_one_frame_for_short_video(monkeypatch, tmp_path):
    source = tmp_path / "short.mp4"
    source.write_bytes(b"synthetic-video-placeholder")
    calls: list[int] = []

    monkeypatch.setattr(media, "_video_frame_timestamps", lambda _: [0.0])
    monkeypatch.setattr(
        media,
        "_extract_frames",
        lambda _path, indices: (
            calls.extend(indices) or [Image.new("RGB", (40, 40), (10, 10, 10))]
        ),
    )

    _, frame_count = media._contact_sheet(source, duration=0.4, requested_frames=8)

    assert frame_count == 1
    assert calls == [0]


@pytest.mark.parametrize(
    "frames",
    [[], [{}], [{"best_effort_timestamp_time": "N/A"}],
     [{"best_effort_timestamp_time": "nan"}], [{"best_effort_timestamp_time": "inf"}],
     [{"best_effort_timestamp_time": "1"}, {"best_effort_timestamp_time": "0"}]],
)
def test_invalid_frame_timestamps_are_rejected(monkeypatch, tmp_path, frames):
    result = subprocess.CompletedProcess([], 0, stdout=json.dumps({"frames": frames}).encode())
    monkeypatch.setattr(media, "_run", lambda *_args, **_kwargs: result)

    with pytest.raises(media.HTTPException) as error:
        media._video_frame_timestamps(tmp_path / "sample.mp4")

    assert error.value.status_code == 422


@pytest.mark.parametrize(
    "timestamps,count,expected",
    [([0.0, 0.1, 0.3, 0.4], 3, [0, 1, 3]),
     ([0.0, 0.1, 0.2, 3.0], 4, [0, 2, 3]),
     ([0.0, 0.0, 0.0], 3, [0]),
     ([0.0, 1.0], 1, [0])],
)
def test_frame_selection_handles_midpoints_and_duplicates(timestamps, count, expected):
    assert media._sample_frame_indices(timestamps, count) == expected


def test_frame_extraction_rejects_missing_output(monkeypatch, tmp_path):
    monkeypatch.setattr(media, "_run", lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0))

    with pytest.raises(media.HTTPException) as error:
        media._extract_frames(tmp_path / "sample.mp4", [0, 1])

    assert error.value.status_code == 422
    assert error.value.detail == "视频抽帧数量与采样计划不一致"


def test_contact_sheet_labels_use_selected_frame_timestamps(monkeypatch, tmp_path):
    labels = []
    monkeypatch.setattr(media, "_video_frame_timestamps", lambda _: [0.0, 0.1, 0.2, 3.0])
    monkeypatch.setattr(media, "_extract_frames", lambda _, indices: [Image.new("RGB", (40, 40)) for _ in indices])
    monkeypatch.setattr(media.ImageDraw.ImageDraw, "text", lambda _self, _xy, text, **_: labels.append(text))

    _, count = media._contact_sheet(tmp_path / "sample.mp4", duration=3.1, requested_frames=4)

    assert count == 3
    assert labels == ["帧 1 · 0.00s", "帧 2 · 0.20s", "帧 3 · 3.00s"]


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
