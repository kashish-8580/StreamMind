from types import SimpleNamespace

from transcription.audio_service import AudioService
from transcription.whisper_service import WhisperService


def test_audio_extraction_creates_mono_wav(tmp_path):
    import subprocess

    source = tmp_path / "source.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=160x120:r=10",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=16000",
            "-t",
            "1",
            "-shortest",
            str(source),
        ],
        check=True,
        capture_output=True,
    )
    output = tmp_path / "audio.wav"

    AudioService().extract(source, output)

    assert output.exists()
    assert output.stat().st_size > 44


def test_whisper_service_normalizes_segments_without_loading_model(tmp_path):
    segment = SimpleNamespace(start=1.25, end=2.5, text="  useful words  ")
    model = SimpleNamespace(
        transcribe=lambda *_args, **_kwargs: (iter([segment]), SimpleNamespace(language="en"))
    )
    service = WhisperService.__new__(WhisperService)
    service.model = model

    language, segments = service.transcribe(tmp_path / "audio.wav")

    assert language == "en"
    assert segments == [{"start_seconds": 1.25, "end_seconds": 2.5, "text": "useful words"}]
