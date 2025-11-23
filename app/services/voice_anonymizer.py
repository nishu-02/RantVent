"""
This module provides production-level voice anonymization utilities.

- Loads audio
- Converts to WAV if needed
- Applies specific preset transformation
- Returns path to anonymized audio
"""

import os
import uuid
from pathlib import Path
from typing import Optional

import parselmouth
from parselmouth.praat import call
from pydub import AudioSegment

class VoiceAnonymizer:

    def __init__(self, media_root: str, subdir: str, presets: list[tuple[float, float, float]]):
        self.base_dir = Path(media_root) / subdir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.PRESETS = presets

    def ensure_wav(self, path: str) -> str:
        """Convert audio file to WAV format if not already in WAV format."""
        if path.lower().endswith('.wav'):
            return path
        
        audio = AudioSegment.from_file(path)

        new_path = str(Path(path).with_suffix('.wav'))
        audio.export(new_path, format='wav')

        return new_path

    def apply_preset(self, wav_path: str, preset_index: int) -> str:
        """"Apply single preset only"""
        p, f_shift, time_factor = self.PRESETS[preset_index - 1]

        sound = parselmouth.Sound(wav_path)

        manipulation = call(sound, "To Manipulation", 0.01, 75, 600)

        pitch_tier = call(manipulation, "Extract pitch tier")
        call(pitch_tier, "Multiply frequencies", sound.xmin, sound.xmax, p)
        call([pitch_tier, manipulation], "Replace pitch tier")

        duration_tier = call(manipulation, "Extract duration tier")
        call(duration_tier, "Add point", sound.xmin, time_factor)
        call(duration_tier, "Add point", sound.xmax, time_factor)
        call([duration_tier, manipulation], "Replace duration tier")
        
        transformed = call(manipulation, "Get resynthesis (overlap-add)")

        final = call(transformed, "Change gender", 75, 600, f_shift, 0, 1.0, 1.0)

        out_file = self.base_dir / f"{uuid.uuid4().hex}_anon.wav"
        final.save(str(out_file), "WAV")

        return str(out_file)

    def anonymize(self, input_path: str, preset_index: int) -> str:
        """
        Master Method
        Accepts any input file.
        If preset_index is valid, applies that preset.
        Else -> No anonymization applied.
        """
        if preset_index == 0:
            return input_path
        
        if not (1 <= preset_index <= 6):
            raise ValueError("Preset index must be between 1 and 6.")

        wav_path = self.ensure_wav(input_path)
        return self.apply_preset(wav_path, preset_index)

# Initialized instance - shared globally
from app.core.config import settings
voice_anonymizer = VoiceAnonymizer(
    media_root=settings.MEDIA_ROOT,
    subdir=settings.AUDIO_SUBDIR,
    presets=settings.voice_presets,
)