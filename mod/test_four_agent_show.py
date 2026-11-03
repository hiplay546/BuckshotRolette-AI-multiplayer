"""Offline checks for style allocation and the show request shape."""
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from four_agent_show import DELIVERY_STYLES, Show, normalize_signature_style
from voicestudio_tts import VoiceStudioTTS


class FourAgentShowTests(unittest.TestCase):
    def make_show(self, directory: Path) -> Show:
        show = Show(directory, "unused", {seat: "deepseek/deepseek-v4-flash-0731" for seat in range(1, 5)},
                    max_calls=10, max_cost=1.0, max_shots=1)
        show.match_id = "test-match"
        return show

    def test_duplicate_style_is_replaced_and_not_offered(self):
        with tempfile.TemporaryDirectory() as temp:
            show = self.make_show(Path(temp))
            show.styles[1] = DELIVERY_STYLES[0]
            self.assertNotIn(DELIVERY_STYLES[0], show.available_styles(2))
            chosen, adjusted = normalize_signature_style(DELIVERY_STYLES[0], 2, show.available_styles(2))
            self.assertTrue(adjusted)
            self.assertNotEqual(chosen, show.styles[1])

    def test_duplicate_style_in_old_log_is_repaired(self):
        with tempfile.TemporaryDirectory() as temp:
            show = self.make_show(Path(temp))
            with show.log_path.open("w", encoding="utf-8") as file:
                for seat in (1, 2):
                    file.write(json.dumps({"match_id": show.match_id, "kind": "model_response",
                                           "seat": seat, "delivery_style": DELIVERY_STYLES[0]}) + "\n")
            show.restore_history()
            self.assertEqual(len({show.styles[1], show.styles[2]}), 2)

    def test_request_uses_low_reasoning_and_json_content(self):
        with tempfile.TemporaryDirectory() as temp:
            show = self.make_show(Path(temp))
            sent = []

            def fake_urlopen(request, timeout):
                sent.append(json.loads(request.data))
                content = {"private_thought": "Патроны: неизвестны; Риск: высок; План: ждать.",
                           "public_speech": "", "action": None, "signature_style": DELIVERY_STYLES[0]}
                reply = {"choices": [{"message": {"content": json.dumps(content, ensure_ascii=False)}}],
                         "usage": {"cost": 0.001}}
                return io.BytesIO(json.dumps(reply, ensure_ascii=False).encode("utf-8"))

            with patch("four_agent_show.urllib.request.urlopen", side_effect=fake_urlopen):
                show.ask(1, "first_negotiation", {"player_socket": 0, "players": []}, [], speech_only=True)
            self.assertEqual(sent[0]["reasoning"], {"effort": "low", "exclude": True})
            self.assertEqual(sent[0]["response_format"], {"type": "json_object"})
            self.assertEqual(show.styles[1], DELIVERY_STYLES[0])
            self.assertIn("Патроны:", show.private[1][0]["text"])

    def test_voicestudio_uses_assigned_profile_and_blocks_for_playback(self):
        assigned = {1: "voice-one", 2: "voice-two", 3: "voice-three", 4: "voice-four"}
        tts = VoiceStudioTTS(assigned)
        sent = []
        wav = b"RIFF" + (4).to_bytes(4, "little") + b"WAVE"

        def fake_urlopen(request, timeout):
            sent.append(json.loads(request.data))
            return io.BytesIO(wav)

        with patch("voicestudio_tts.urllib.request.urlopen", side_effect=fake_urlopen), \
                patch("winsound.PlaySound") as play:
            tts.speak(2, "Проверка голоса")
        self.assertEqual(sent[0]["voice"], "voice-two")
        self.assertEqual(sent[0]["response_format"], "wav")
        play.assert_called_once()


if __name__ == "__main__":
    unittest.main()
