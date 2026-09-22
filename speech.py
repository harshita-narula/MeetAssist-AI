import os
import threading
from typing import Any

import azure.cognitiveservices.speech as speechsdk
from dotenv import load_dotenv

load_dotenv()


# =========================================================
# HELPERS
# =========================================================

def ticks_to_seconds(ticks: int) -> float:
    """
    Azure Speech timestamps use 100-nanosecond ticks.
    10,000,000 ticks = 1 second.
    """
    return ticks / 10_000_000


def format_timestamp(seconds: float) -> str:
    """
    Convert seconds to MM:SS or HH:MM:SS.
    """

    total_seconds = max(0, int(seconds))

    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    return f"{minutes:02d}:{secs:02d}"


# =========================================================
# TRANSCRIPTION
# =========================================================

def transcribe_audio(
    file_path: str,
    language: str = "en-IN",
) -> dict[str, Any]:
    """
    Convert a WAV meeting recording into text using Azure AI Speech.

    Returns:
        {
            "text": "...",
            "segments": [
                {
                    "start": 0.0,
                    "end": 4.2,
                    "start_time": "00:00",
                    "end_time": "00:04",
                    "text": "..."
                }
            ]
        }

    Azure Speech provides offset and duration for recognized
    speech, which allows us to build a timeline.
    """

    speech_key = os.getenv("SPEECH_KEY")
    speech_region = os.getenv("SPEECH_REGION")

    if not speech_key:
        raise ValueError(
            "SPEECH_KEY is missing in .env"
        )

    if not speech_region:
        raise ValueError(
            "SPEECH_REGION is missing in .env"
        )

    # -----------------------------------------------------
    # SPEECH CONFIG
    # -----------------------------------------------------

    speech_config = speechsdk.SpeechConfig(
        subscription=speech_key,
        region=speech_region,
    )

    speech_config.speech_recognition_language = language

    # Request detailed timing information.
    speech_config.request_word_level_timestamps()

    # -----------------------------------------------------
    # AUDIO
    # -----------------------------------------------------

    audio_config = speechsdk.audio.AudioConfig(
        filename=file_path
    )

    # -----------------------------------------------------
    # RECOGNIZER
    # -----------------------------------------------------

    recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config,
        audio_config=audio_config,
    )

    # -----------------------------------------------------
    # DOMAIN VOCABULARY
    # -----------------------------------------------------

    phrase_list = speechsdk.PhraseListGrammar.from_recognizer(
        recognizer
    )

    meeting_phrases = [
        "MeetAssist",
        "meeting",
        "project",
        "dashboard",
        "deployment",
        "deployment checklist",
        "customer feedback",
        "final approval",
        "action item",
        "action items",
        "deadline",
        "deadlines",
        "testing",
        "test",
        "support team",
        "support",
        "launch",
        "launch date",
        "launch plan",
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
        "review",
        "risk",
        "decision",
        "decisions",
        "unresolved issue",
        "open question",
        "status",
        "owner",
        "next steps",
    ]

    for phrase in meeting_phrases:
        phrase_list.addPhrase(phrase)

    phrase_list.setWeight(1.5)

    # -----------------------------------------------------
    # RESULT STORAGE
    # -----------------------------------------------------

    segments = []
    finished = threading.Event()
    real_error = []

    # -----------------------------------------------------
    # EVENT HANDLERS
    # -----------------------------------------------------

    def on_recognized(event):
        result = event.result

        if result.reason != speechsdk.ResultReason.RecognizedSpeech:
            return

        text = result.text.strip()

        if not text:
            return

        start_seconds = ticks_to_seconds(
            result.offset
        )

        duration_seconds = ticks_to_seconds(
            result.duration
        )

        end_seconds = (
            start_seconds + duration_seconds
        )

        segments.append(
            {
                "start": start_seconds,
                "end": end_seconds,
                "start_time": format_timestamp(
                    start_seconds
                ),
                "end_time": format_timestamp(
                    end_seconds
                ),
                "text": text,
            }
        )

    def on_session_stopped(event):
        finished.set()

    def on_canceled(event):
        details = event.result.cancellation_details

        if (
            details.reason
            == speechsdk.CancellationReason.Error
        ):
            error_text = details.error_details

            if error_text:
                real_error.append(error_text)
            else:
                real_error.append(
                    f"Azure Speech error: {details.reason}"
                )

        finished.set()

    # -----------------------------------------------------
    # CONNECT EVENTS
    # -----------------------------------------------------

    recognizer.recognized.connect(
        on_recognized
    )

    recognizer.session_stopped.connect(
        on_session_stopped
    )

    recognizer.canceled.connect(
        on_canceled
    )

    # -----------------------------------------------------
    # START
    # -----------------------------------------------------

    recognizer.start_continuous_recognition()

    finished.wait()

    recognizer.stop_continuous_recognition()

    # -----------------------------------------------------
    # ERROR HANDLING
    # -----------------------------------------------------

    if real_error:
        raise RuntimeError(
            f"Azure Speech error: {real_error[0]}"
        )

    if not segments:
        raise RuntimeError(
            "No speech was recognized. "
            "Please use a clear WAV or MP4 meeting recording."
        )

    # Sort by audio position
    segments.sort(
        key=lambda item: item["start"]
    )

    # -----------------------------------------------------
    # COMBINED RAW TEXT
    # -----------------------------------------------------

    full_text = " ".join(
        segment["text"]
        for segment in segments
    )

    return {
        "text": full_text,
        "segments": segments,
    }