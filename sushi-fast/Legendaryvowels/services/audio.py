import subprocess
from pathlib import Path

import numpy as np

from ..schemas import AudioMetrics
from .rules import AUDIO_RULES


def _count_long_pauses(silent_frames: np.ndarray) -> int:
    minimum_frames = max(
        1,
        round(
            AUDIO_RULES.long_pause_sec
            * AUDIO_RULES.sample_rate
            / AUDIO_RULES.hop_length
        ),
    )
    count = 0
    run_length = 0

    for is_silent in silent_frames:
        if is_silent:
            run_length += 1
        else:
            if run_length >= minimum_frames:
                count += 1
            run_length = 0

    if run_length >= minimum_frames:
        count += 1

    return count


def analyze_audio(
    audio_path: str,
    spoken_character_count: int = 0,
    filler_count: int = 0,
) -> AudioMetrics:
    signal, sample_rate = decode_audio(audio_path)
    duration = float(signal.size / sample_rate)
    if signal.size < AUDIO_RULES.frame_length:
        signal = np.pad(
            signal,
            (0, AUDIO_RULES.frame_length - signal.size),
        )
    frame_count = (
        1
        + (signal.size - AUDIO_RULES.frame_length)
        // AUDIO_RULES.hop_length
    )
    frames = np.lib.stride_tricks.sliding_window_view(
        signal,
        AUDIO_RULES.frame_length,
    )[::AUDIO_RULES.hop_length][:frame_count]
    rms = np.sqrt(np.mean(np.square(frames), axis=1))
    peak_rms = float(np.max(rms)) if rms.size else 0.0
    average_rms = float(np.mean(rms)) if rms.size else 0.0
    speech_threshold = max(
        AUDIO_RULES.silence_rms_floor,
        peak_rms * AUDIO_RULES.silence_peak_ratio,
    )
    silent_frames = rms < speech_threshold
    silence_ratio = float(np.mean(silent_frames)) if rms.size else 1.0
    silence_duration = min(duration, duration * silence_ratio)
    speech_duration = max(0.0, duration - silence_duration)
    speaking_rate = (
        spoken_character_count / speech_duration * 60.0
        if speech_duration > 0.0 and spoken_character_count
        else None
    )

    return AudioMetrics(
        duration_sec=round(duration, 3),
        speech_duration_sec=round(speech_duration, 3),
        silence_duration_sec=round(silence_duration, 3),
        silence_ratio=round(silence_ratio, 4),
        long_pause_count=_count_long_pauses(silent_frames),
        average_rms=round(average_rms, 6),
        peak_rms=round(peak_rms, 6),
        speaking_rate_cpm=(round(speaking_rate, 2) if speaking_rate else None),
        filler_count=filler_count,
    )


def decode_audio(audio_path: str) -> tuple[np.ndarray, int]:
    path = Path(audio_path)
    if not path.exists():
        raise FileNotFoundError(f"음성 파일을 찾을 수 없습니다: {audio_path}")

    process = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(path),
            "-f",
            "f32le",
            "-ac",
            "1",
            "-ar",
            str(AUDIO_RULES.sample_rate),
            "pipe:1",
        ],
        capture_output=True,
        check=False,
        timeout=AUDIO_RULES.decode_timeout_sec,
    )
    if process.returncode != 0:
        message = process.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(f"음성 파일을 디코딩할 수 없습니다: {message}")

    signal = np.frombuffer(process.stdout, dtype="<f4")
    if signal.size == 0:
        raise ValueError("음성 데이터가 비어 있습니다.")
    return signal.copy(), AUDIO_RULES.sample_rate

