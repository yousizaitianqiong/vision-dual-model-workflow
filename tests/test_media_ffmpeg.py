"""使用纯合成媒体验证真实 FFmpeg 抽帧链路。"""

import io
import json
import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from services import media_preprocess_server as media


client = TestClient(media.app)


def _frame_color(index):
    return ((37 * index + 30) % 200 + 20, (73 * index + 40) % 200 + 20, (19 * index + 80) % 200 + 20)


def _make_video(tmp_path, rate, frame_count, *, select=None, offset=0, second_stream=False, codec="ffv1"):
    assert shutil.which("ffmpeg"), "合成视频测试需要安装 FFmpeg"
    assert shutil.which("ffprobe"), "合成视频测试需要安装 FFprobe"
    for index in range(frame_count):
        Image.new("RGB", (64, 48), _frame_color(index)).save(tmp_path / f"frame-{index:03d}.png")

    output = tmp_path / ("synthetic.mp4" if codec == "mpeg4" else "synthetic.mkv")
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-framerate", rate, "-i", str(tmp_path / "frame-%03d.png"),
    ]
    if second_stream:
        command += ["-f", "lavfi", "-i", "color=c=lime:s=160x120:r=1:d=2"]
    command += ["-map", "0:v:0"]
    if second_stream:
        command += ["-map", "1:v:0"]
    if select is not None:
        command += ["-filter:v:0", select, "-fps_mode:v:0", "vfr"]
    command += ["-c:v", codec]
    command += ["-bf", "2", "-pix_fmt", "yuv420p"] if codec == "mpeg4" else ["-pix_fmt", "bgr0"]
    command += ["-output_ts_offset", str(offset), str(output)]
    subprocess.run(command, check=True, capture_output=True, timeout=20)
    return output


def _assert_video_response(path, expected_indices, *, requested_frames=None):
    data = {} if requested_frames is None else {"max_frames": str(requested_frames)}
    response = client.post(
        "/v1/media/prepare",
        files={"file": (path.name, path.read_bytes(), "video/mp4" if path.suffix == ".mp4" else "video/x-matroska")},
        data=data,
    )

    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "image/jpeg"
    assert response.headers["x-media-source"] == "video"
    assert int(response.headers["x-frame-count"]) == len(expected_indices)
    with Image.open(io.BytesIO(response.content)) as sheet:
        assert sheet.format == "JPEG"
        assert sheet.mode == "RGB"
        assert sheet.size == (1920, 660)
        for cell, source_index in enumerate(expected_indices):
            x = (cell % 4) * 480 + 240
            y = (cell // 4) * 330 + 180
            actual = sheet.getpixel((x, y))
            expected = _frame_color(source_index)
            assert all(abs(a - b) <= 10 for a, b in zip(actual, expected)), (cell, actual, expected)
    return response


@pytest.mark.parametrize(
    "rate,frame_count,requested_frames,expected_indices",
    [
        ("1", 2, None, [0, 1]),
        ("1/2", 2, 8, [0, 1]),
        ("30", 60, 8, [0, 59]),
        ("1", 12, 99, [0, 2, 3, 5, 6, 8, 9, 11]),
        ("1", 12, 4, [0, 4, 7, 11]),
        ("1", 12, 1, [0]),
        ("1", 12, 0, [0]),
        ("30", 1, 8, [0]),
    ],
    ids=["low-fps", "sub-fps", "ordinary-fps", "cap-eight", "four", "one", "clamp-one", "single-frame"],
)
def test_real_video_sampling(tmp_path, rate, frame_count, requested_frames, expected_indices):
    path = _make_video(tmp_path, rate, frame_count)
    _assert_video_response(path, expected_indices, requested_frames=requested_frames)


def test_real_variable_frame_rate_uses_time_and_deduplicates(tmp_path):
    # 四帧位于 0、0.1、0.2、3 秒；均匀时间目标会重复选中末帧。
    path = _make_video(tmp_path, "10", 31, select=r"select=eq(n\,0)+eq(n\,1)+eq(n\,2)+eq(n\,30)")
    _assert_video_response(path, [0, 2, 30], requested_frames=4)


def test_real_video_with_nonzero_start_time(tmp_path):
    path = _make_video(tmp_path, "1", 2, offset=5)
    _assert_video_response(path, [0, 1])


def test_real_video_uses_first_stream_for_probe_and_extraction(tmp_path):
    path = _make_video(tmp_path, "1", 2, second_stream=True)
    _assert_video_response(path, [0, 1])


@pytest.mark.parametrize("rate,frame_count,expected_indices", [("1", 2, [0, 1]), ("2", 12, [0, 2, 4, 7, 9, 11])])
def test_real_mp4_sampling_with_reordered_frames(tmp_path, rate, frame_count, expected_indices):
    path = _make_video(tmp_path, rate, frame_count, codec="mpeg4")
    if frame_count > 2:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "frame=pict_type", "-of", "json", str(path)],
            check=True, capture_output=True, timeout=20,
        )
        assert "B" in [frame["pict_type"] for frame in json.loads(probe.stdout)["frames"]]
    _assert_video_response(path, expected_indices)


@pytest.mark.parametrize("later_size", ["128x96", "128x64"])
def test_real_video_resolution_change_preserves_frame_indices_and_aspect_ratio(tmp_path, later_size):
    segments = []
    for index, size in enumerate(["64x48", "64x48", later_size, later_size]):
        color = "0x" + "".join(f"{channel:02x}" for channel in _frame_color(index))
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
             "-i", f"color=c={color}:s={size}:r=1:d=1", "-frames:v", "1",
             "-c:v", "libx264", "-bf", "0", "-f", "h264", "pipe:1"],
            check=True, capture_output=True, timeout=20,
        )
        segments.append(result.stdout)
    path = tmp_path / "resolution-change.mkv"
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-fflags", "+genpts",
         "-r", "1", "-f", "h264", "-i", "pipe:0", "-c:v", "copy", str(path)],
        input=b"".join(segments), check=True, capture_output=True, timeout=20,
    )

    response = _assert_video_response(path, [0, 3], requested_frames=2)
    if later_size == "128x64":
        with Image.open(io.BytesIO(response.content)) as sheet:
            for y in (45, 315):
                assert all(abs(channel - 24) <= 5 for channel in sheet.getpixel((720, y)))
            for y in (75, 285):
                assert all(
                    abs(actual - expected) <= 10
                    for actual, expected in zip(sheet.getpixel((720, y)), _frame_color(3))
                )
