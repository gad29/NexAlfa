"""
NexAlfa Voice Tools
STT (Speech-to-Text) via OpenAI Whisper, TTS (Text-to-Speech) via OpenAI TTS.
FFmpeg integration for audio format conversion.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import re
import time
from pathlib import Path
from typing import Optional

from agent.tools.base import Tool

logger = logging.getLogger("nex.tools.voice")


# ── Configuration ──────────────────────────────────────────

class VoiceConfig:
    """Voice configuration from environment."""

    @property
    def stt_provider(self) -> str:
        return os.environ.get("NEX_STT_PROVIDER", "openai")

    @property
    def stt_model(self) -> str:
        return os.environ.get("NEX_STT_MODEL", "whisper-1")

    @property
    def tts_provider(self) -> str:
        return os.environ.get("NEX_TTS_PROVIDER", "openai")

    @property
    def tts_model(self) -> str:
        return os.environ.get("NEX_TTS_MODEL", "tts-1")

    @property
    def tts_voice(self) -> str:
        return os.environ.get("NEX_TTS_VOICE", "alloy")

    @property
    def voice_mode(self) -> str:
        return os.environ.get("NEX_VOICE_MODE", "auto")

    @property
    def ffmpeg_path(self) -> str:
        return os.environ.get("NEX_FFMPEG_PATH", "ffmpeg")

    @property
    def tts_speed(self) -> float:
        return float(os.environ.get("NEX_TTS_SPEED", "1.0"))

    def has_ffmpeg(self) -> bool:
        return shutil.which(self.ffmpeg_path) is not None


voice_config = VoiceConfig()


# ── FFmpeg helpers ─────────────────────────────────────────

def convert_audio(input_path: str, output_format: str = "wav", sample_rate: int = 16000) -> str:
    if not voice_config.has_ffmpeg():
        raise RuntimeError("FFmpeg not found.")
    output_path = str(Path(input_path).with_suffix(f".{output_format}"))
    cmd = [voice_config.ffmpeg_path, "-y", "-i", input_path, "-ar", str(sample_rate), "-ac", "1", output_path]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed: {result.stderr[:500]}")
    return output_path


def get_audio_duration(path: str) -> float:
    if not voice_config.has_ffmpeg():
        return 0.0
    cmd = [voice_config.ffmpeg_path, "-i", path, "-f", "null", "-"]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    match = re.search(r"Duration: (\d+):(\d+):(\d+)\.(\d+)", result.stderr)
    if match:
        h, m, s, ms = match.groups()
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 100
    return 0.0


# ── STT (Speech-to-Text) ──────────────────────────────────

async def stt_transcribe(audio_path: str, language: Optional[str] = None) -> str:
    path = Path(audio_path)
    if not path.exists():
        return f"ERROR: Audio file not found: {audio_path}"
    duration = get_audio_duration(str(path))
    if duration > 1500:
        return f"ERROR: Audio too long ({duration/60:.1f} min). Max is 25 minutes."
    supported = {".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm", ".ogg", ".flac"}
    work_path = str(path)
    if path.suffix.lower() not in supported:
        try:
            work_path = convert_audio(str(path), "wav")
        except Exception as e:
            return f"ERROR: Cannot convert audio: {e}"
    if voice_config.stt_provider == "openai":
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI()
            with open(work_path, "rb") as f:
                params = {"model": voice_config.stt_model, "file": f}
                if language:
                    params["language"] = language
                transcript = await client.audio.transcriptions.create(**params)
            return transcript.text
        except Exception as e:
            return f"ERROR: STT failed: {type(e).__name__}: {e}"
    return f"ERROR: Unsupported STT provider: {voice_config.stt_provider}"


# ── TTS (Text-to-Speech) ──────────────────────────────────

async def tts_generate(text: str, voice: Optional[str] = None, output_path: Optional[str] = None, output_format: str = "mp3") -> str:
    if not text.strip():
        return "ERROR: Empty text"
    if len(text) > 4096:
        text = text[:4096]
    voice = voice or voice_config.tts_voice
    if not output_path:
        storage = Path("storage/audio")
        storage.mkdir(parents=True, exist_ok=True)
        output_path = str(storage / f"tts_{int(time.time() * 1000)}.{output_format}")
    if voice_config.tts_provider == "openai":
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI()
            response = await client.audio.speech.create(
                model=voice_config.tts_model,
                voice=voice,
                input=text,
                speed=voice_config.tts_speed,
                response_format=output_format,
            )
            with open(output_path, "wb") as f:
                async for chunk in response.iter_bytes():
                    f.write(chunk)
            return output_path
        except Exception as e:
            return f"ERROR: TTS failed: {type(e).__name__}: {e}"
    return f"ERROR: Unsupported TTS provider: {voice_config.tts_provider}"


# ── Voice mode logic ───────────────────────────────────────

def should_respond_with_voice(incoming_has_audio: bool) -> bool:
    mode = voice_config.voice_mode
    if mode == "always":
        return True
    if mode == "never":
        return False
    if mode in ("auto", "voice_only"):
        return incoming_has_audio
    return False


def get_voice_status() -> dict:
    return {
        "stt_provider": voice_config.stt_provider,
        "stt_model": voice_config.stt_model,
        "tts_provider": voice_config.tts_provider,
        "tts_model": voice_config.tts_model,
        "tts_voice": voice_config.tts_voice,
        "voice_mode": voice_config.voice_mode,
        "ffmpeg_available": voice_config.has_ffmpeg(),
        "tts_speed": voice_config.tts_speed,
    }


# ── Tool Classes ───────────────────────────────────────────

class VoiceTranscribeTool(Tool):
    name = "voice_transcribe"
    description = "Transcribe an audio/voice file to text using OpenAI Whisper. Supports: mp3, mp4, wav, ogg, webm, flac, m4a."

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "audio_path": {"type": "string", "description": "Path to the audio file"},
                    "language": {"type": "string", "description": "Language code (e.g. 'en', 'he', 'ar'). Auto-detected if not specified."},
                },
                "required": ["audio_path"],
            },
        }

    async def execute(self, audio_path: str, language: str = None) -> str:
        return await stt_transcribe(audio_path, language)


class VoiceGenerateTool(Tool):
    name = "voice_generate"
    description = "Generate speech audio from text using OpenAI TTS. Returns path to the generated audio file."

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to convert to speech"},
                    "voice": {
                        "type": "string",
                        "description": "Voice: alloy, echo, fable, onyx, nova, shimmer (default: alloy)",
                        "enum": ["alloy", "echo", "fable", "onyx", "nova", "shimmer"],
                    },
                    "output_format": {
                        "type": "string",
                        "description": "Output format: mp3, opus, aac, flac, wav (default: mp3)",
                    },
                },
                "required": ["text"],
            },
        }

    async def execute(self, text: str, voice: str = None, output_format: str = "mp3") -> str:
        return await tts_generate(text, voice, output_format=output_format)


def get_voice_tools() -> list[Tool]:
    return [VoiceTranscribeTool(), VoiceGenerateTool()]
