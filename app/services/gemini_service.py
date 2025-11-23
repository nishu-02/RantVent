"""
Handles:
- file upload
- romanized Hinglish transcription
- summary
- tldr
- language id
"""

import os
import logging
import time
import json
import re
from typing import Optional
from pathlib import Path
from google import genai
from app.core.config import settings


class GeminiService:
    def __init__(self):
        key = settings.GEMINI_API_KEY
        self.available = bool(key)
        if key:
            # Create client with API key
            self.client = genai.Client(api_key=key)
            self.model = 'gemini-2.0-flash'
        else:
            self.client = None
            self.model = None
        self.log = logging.getLogger("GeminiService")
        if not self.available:
            self.log.warning("GEMINI_API_KEY not set; Gemini features will be unavailable")

    def transcribe_romanized_full(self, audio_filepath: str):
        
        if not self.available or not self.client:
            raise RuntimeError("GEMINI_API_KEY is not configured. Gemini service is unavailable.")
        
        # Resolve to absolute path
        if not os.path.isabs(audio_filepath):
            audio_filepath = os.path.abspath(audio_filepath)
        
        if not os.path.exists(audio_filepath):
            raise FileNotFoundError(f"Audio file not found: {audio_filepath}")
        
        file_size = os.path.getsize(audio_filepath)
        is_readable = os.access(audio_filepath, os.R_OK)
        
        if not is_readable:
            raise PermissionError(f"Cannot read file: {audio_filepath}")
        
        if file_size == 0:
            raise ValueError(f"File is empty: {audio_filepath}")
        
        # Now attempt file upload
        uploaded = None
        
        try:
            start = time.time()
            
            # Upload file
            uploaded = self.client.files.upload(file=audio_filepath)
            
            elapsed = time.time() - start
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise
        
        # Generate content with the uploaded file
        response = None
        try:
            print("\n[Gemini] Calling generate_content...")
            start = time.time()
            
            response = self.client.models.generate_content(
                model=self.model,
                contents=[
                    "Transcribe this audio file. Provide the output in JSON format with these exact keys:\n"
                    '{"TRANSCRIPT": "full romanized Hinglish transcript", '
                    '"SUMMARY": "2-4 sentences clean summary", '
                    '"TLDR": "10 words or less", '
                    '"LANGUAGE": "detected language"}\n\n'
                    "Return ONLY the JSON, no markdown code blocks or extra text.",
                    uploaded
                ]
            )
            
            elapsed = time.time() - start
            
        except Exception as e:
            print(f"[Gemini] Generate content error: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            raise
        finally:
            # Clean up uploaded file
            if uploaded:
                try:
                    print(f"\n[Gemini] Deleting uploaded file: {uploaded.name}")
                    self.client.files.delete(name=uploaded.name)
                    print(f"[Gemini] File deleted successfully")
                except Exception as e:
                    print(f"[Gemini] Error deleting file: {type(e).__name__}: {e}")
        
        if not response or not response.text:
            raise RuntimeError("No response from Gemini")
        
        result = self.parse_output(response.text)
        
        return result

    def parse_output(self, raw: str):
        """Parses Gemini output - handles both JSON and plain text formats."""
        
        class Result:
            def __init__(self):
                self.transcript = ""
                self.summary = ""
                self.tldr = ""
                self.language = ""
        
        result = Result()
        
        # Try JSON parsing first (remove markdown code blocks if present)
        cleaned = raw.strip()
        
        # Remove markdown code blocks
        if cleaned.startswith('```'):
            # Remove opening ```json or ```
            cleaned = re.sub(r'^```(?:json)?\s*\n?', '', cleaned)
            # Remove closing ```
            cleaned = re.sub(r'\n?```\s*$', '', cleaned)
        
        try:
            data = json.loads(cleaned)
            result.transcript = data.get("TRANSCRIPT", "").strip()
            result.summary = data.get("SUMMARY", "").strip()
            result.tldr = data.get("TLDR", "").strip()
            result.language = data.get("LANGUAGE", "").strip()
            return result
        except json.JSONDecodeError:
            print("[Gemini] Not JSON format, trying plain text parsing...")
        
        # Fallback to plain text parsing
        block = {
            "transcript": "",
            "summary": "",
            "tldr": "",
            "language": ""
        }
        current_key = None
        
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            
            if line == "TRANSCRIPT:":
                current_key = "transcript"
                continue
            if line == "SUMMARY:":
                current_key = "summary"
                continue
            if line == "TLDR:":
                current_key = "tldr"
                continue
            if line == "LANGUAGE:":
                current_key = "language"
                continue
            
            if current_key:
                block[current_key] += (line + " ")
        
        result.transcript = block["transcript"].strip()
        result.summary = block["summary"].strip()
        result.tldr = block["tldr"].strip()
        result.language = block["language"].strip()
        
        # Validate that we got something meaningful
        if not result.transcript:
            print("[WARNING] No transcript found in response")
        if not result.summary:
            print("[WARNING] No summary found in response")
        if not result.tldr:
            print("[WARNING] No TLDR found in response")
        if not result.language:
            print("[WARNING] No language found in response")
        
        return result


gemini_service = GeminiService()