import subprocess

from video_processor.ffmpeg_service import FFmpegService


def test_ffmpeg_creates_hls_and_thumbnail(tmp_path):
    source = tmp_path / "source.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=320x240:rate=10",
            "-t",
            "1",
            "-pix_fmt",
            "yuv420p",
            str(source),
        ],
        check=True,
        capture_output=True,
    )

    service = FFmpegService(max_duration_seconds=60)
    metadata = service.inspect(source)
    manifest = service.create_hls(source, tmp_path / "hls")
    thumbnail = tmp_path / "thumbnail.jpg"
    service.create_thumbnail(source, thumbnail, metadata["duration_seconds"])

    assert 0 < metadata["duration_seconds"] <= 2
    assert manifest.exists()
    assert list((tmp_path / "hls").glob("*.ts"))
    assert thumbnail.exists()
