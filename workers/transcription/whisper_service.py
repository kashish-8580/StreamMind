from pathlib import Path


class WhisperService:
    def __init__(self, model_name: str) -> None:
        from faster_whisper import WhisperModel

        self.model = WhisperModel(model_name, device="cpu", compute_type="int8")

    def transcribe(self, audio: Path) -> tuple[str | None, list[dict]]:
        segments, info = self.model.transcribe(str(audio), beam_size=5, vad_filter=True)
        results = [
            {
                "start_seconds": float(segment.start),
                "end_seconds": float(segment.end),
                "text": segment.text.strip(),
            }
            for segment in segments
            if segment.text.strip()
        ]
        return info.language, results
