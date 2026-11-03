"""Synchronous playback of saved VoiceStudio profiles through its local API."""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from windows_tts import TTSError

BASE_URL = "http://127.0.0.1:3900/v1"
HEADERS = {"Authorization": "Bearer local"}


def list_profiles() -> list[dict]:
    request = urllib.request.Request(f"{BASE_URL}/audio/voices", headers=HEADERS)
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            data = json.load(response)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise TTSError(f"VoiceStudio profiles unavailable: {exc}") from exc
    voices = data.get("voices", []) if isinstance(data, dict) else []
    return [{"voice_id": voice.get("voice_id"), "name": voice.get("name"),
             "language": voice.get("language")}
            for voice in voices if isinstance(voice, dict) and voice.get("type") == "profile"
            and isinstance(voice.get("voice_id"), str)]


class VoiceStudioTTS:
    def __init__(self, voices: dict[int, str]):
        if set(voices) != {1, 2, 3, 4} or any(not voice for voice in voices.values()):
            raise TTSError("Set a VoiceStudio profile ID for each of players 1 through 4")
        self.voices = voices.copy()

    def validate_profiles(self) -> None:
        available = {profile["voice_id"] for profile in list_profiles()}
        missing = {voice for voice in self.voices.values() if voice not in available}
        if missing:
            raise TTSError(f"VoiceStudio profile ID(s) not found: {', '.join(sorted(missing))}")

    def speak(self, seat: int, speech: str) -> None:
        if not speech:
            return
        payload = {"model": "tts-1", "voice": self.voices[seat], "input": speech,
                   "response_format": "wav"}
        request = urllib.request.Request(
            f"{BASE_URL}/audio/speech", data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={**HEADERS, "Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                audio = response.read(20_000_001)
        except urllib.error.HTTPError as exc:
            detail = exc.read(500).decode("utf-8", errors="replace")
            raise TTSError(f"VoiceStudio synthesis HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise TTSError(f"VoiceStudio synthesis failed: {exc}") from exc
        if len(audio) > 20_000_000 or audio[:4] != b"RIFF" or audio[8:12] != b"WAVE":
            raise TTSError("VoiceStudio did not return a usable WAV file")
        try:
            import winsound
            winsound.PlaySound(audio, winsound.SND_MEMORY | winsound.SND_SYNC)
        except (ImportError, RuntimeError, OSError) as exc:
            raise TTSError(f"VoiceStudio audio playback failed: {exc}") from exc
