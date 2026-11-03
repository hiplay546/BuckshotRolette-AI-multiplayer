"""Blocking Russian speech through the Windows voice installed on this PC."""
from __future__ import annotations

import os
import subprocess


class TTSError(RuntimeError):
    pass


class WindowsTTS:
    RATES = {1: -2, 2: 0, 3: 1, 4: 2}

    def speak(self, seat: int, speech: str) -> None:
        if not speech:
            return
        rate = self.RATES[seat]
        script = (
            "$ErrorActionPreference = 'Stop'; "
            "[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false); "
            "Add-Type -AssemblyName System.Speech; "
            "$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            "try { "
            "$voice = $speaker.GetInstalledVoices() | Where-Object { $_.Enabled -and $_.VoiceInfo.Culture.Name -eq 'ru-RU' } | Select-Object -First 1; "
            "if ($null -eq $voice) { throw 'No Russian Windows speech voice installed' }; "
            "$speaker.SelectVoice($voice.VoiceInfo.Name); "
            f"$speaker.Rate = {rate}; "
            "$speaker.Speak([Console]::In.ReadToEnd()) "
            "} finally { $speaker.Dispose() }"
        )
        environment = os.environ.copy()
        environment.pop("OPENROUTER_API_KEY", None)
        try:
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                input=speech, text=True, encoding="utf-8", capture_output=True,
                timeout=120, env=environment, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise TTSError(f"Windows speech failed: {exc}") from exc
        if result.returncode != 0:
            raise TTSError(f"Windows speech failed: {result.stderr.strip()[-300:]}")
