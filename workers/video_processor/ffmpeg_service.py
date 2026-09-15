import json
import subprocess
from pathlib import Path


class VideoValidationError(Exception):
    pass


class FFmpegService:
    def __init__(self, max_duration_seconds: int) -> None:
        self.max_duration_seconds = max_duration_seconds

    def inspect(self, source: Path) -> dict:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_streams",
                "-show_format",
                "-of",
                "json",
                str(source),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        metadata = json.loads(result.stdout)
        if not any(stream.get("codec_type") == "video" for stream in metadata.get("streams", [])):
            raise VideoValidationError("The uploaded file has no video stream")
        duration = float(metadata.get("format", {}).get("duration", 0))
        if duration <= 0 or duration > self.max_duration_seconds:
            raise VideoValidationError("Video duration is invalid or exceeds the configured limit")
        return {"duration_seconds": duration}

    def create_hls(self, source: Path, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        manifest = output_dir / "index.m3u8"
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(source),
                "-vf",
                "scale=w=1280:h=720:force_original_aspect_ratio=decrease:force_divisible_by=2",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "23",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-hls_time",
                "6",
                "-hls_playlist_type",
                "vod",
                "-hls_segment_filename",
                str(output_dir / "segment_%05d.ts"),
                str(manifest),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return manifest

    def create_thumbnail(self, source: Path, destination: Path, duration_seconds: float) -> None:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-ss",
                str(min(1.0, duration_seconds / 2)),
                "-i",
                str(source),
                "-frames:v",
                "1",
                "-vf",
                "scale=640:-2",
                str(destination),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
