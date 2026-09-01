#!/usr/bin/env python3
"""Lightweight microphone/file bridge for relay (Raspberry Pi 3B)."""

from __future__ import annotations

import argparse
import io
import os
import sys
import time
import wave
from pathlib import Path

import numpy as np
import requests
import sounddevice as sd


DEFAULT_URL = os.getenv("SCP079_DASHBOARD_URL", "http://dsam:7860").rstrip("/")
DEFAULT_TOKEN = os.getenv("SCP079_API_TOKEN", "")


def audio_device(value: str | None) -> str | int | None:
    """sounddevice accepts either a numeric index or a name substring."""
    if value is None:
        return None
    return int(value) if value.isdecimal() else value


def record_utterance(
    sample_rate: int = 16_000,
    block_ms: int = 100,
    threshold: float = 0.012,
    silence_seconds: float = 1.0,
    max_seconds: float = 15.0,
    input_device: str | int | None = None,
) -> bytes:
    """Record mono PCM until speech followed by silence; return a WAV in memory."""
    block_size = sample_rate * block_ms // 1000
    silent_limit = max(1, int(silence_seconds * 1000 / block_ms))
    max_blocks = max(1, int(max_seconds * 1000 / block_ms))
    preroll_limit = max(1, int(500 / block_ms))
    blocks: list[np.ndarray] = []
    preroll: list[np.ndarray] = []
    speech_started = False
    silent_blocks = 0

    print("Warte auf Sprache …", flush=True)
    with sd.InputStream(
        samplerate=sample_rate,
        channels=1,
        dtype="int16",
        blocksize=block_size,
        device=input_device,
    ) as stream:
        for _ in range(max_blocks):
            block, overflowed = stream.read(block_size)
            if overflowed:
                print("Warnung: Audio-Überlauf", file=sys.stderr)
            mono = block[:, 0].copy()
            rms = float(np.sqrt(np.mean((mono.astype(np.float32) / 32768.0) ** 2)))
            if not speech_started:
                preroll.append(mono)
                preroll = preroll[-preroll_limit:]
                if rms >= threshold:
                    speech_started = True
                    blocks.extend(preroll)
                    print("Sprache erkannt …", flush=True)
            else:
                blocks.append(mono)
                silent_blocks = silent_blocks + 1 if rms < threshold else 0
                if silent_blocks >= silent_limit:
                    break

    if not speech_started or not blocks:
        raise RuntimeError("Keine Sprache erkannt")
    pcm = np.concatenate(blocks).astype("<i2", copy=False).tobytes()
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm)
    return output.getvalue()


def send_audio(wav_bytes: bytes, dashboard_url: str, token: str, timeout: float = 240.0) -> bytes:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    response = requests.post(
        f"{dashboard_url}/api/audio",
        headers=headers,
        files={"audio": ("relay.wav", wav_bytes, "audio/wav")},
        timeout=(5.0, timeout),
    )
    if not response.ok:
        raise RuntimeError(f"Dashboard HTTP {response.status_code}: {response.text[:500]}")
    if "audio" not in response.headers.get("content-type", ""):
        raise RuntimeError("Dashboard lieferte kein Audio")
    return response.content


def play_wav(wav_bytes: bytes, output_device: str | int | None = None) -> None:
    with wave.open(io.BytesIO(wav_bytes), "rb") as wav:
        if wav.getsampwidth() != 2:
            raise RuntimeError("Nur 16-bit PCM-WAV wird unterstützt")
        channels = wav.getnchannels()
        sample_rate = wav.getframerate()
        samples = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2")
        if channels > 1:
            samples = samples.reshape(-1, channels)
        sd.play(samples, sample_rate, device=output_device, blocking=True)


def one_cycle(args: argparse.Namespace) -> None:
    if args.file:
        wav_bytes = Path(args.file).read_bytes()
    else:
        wav_bytes = record_utterance(
            sample_rate=args.sample_rate,
            threshold=args.threshold,
            silence_seconds=args.silence,
            max_seconds=args.max_seconds,
            input_device=audio_device(args.input_device),
        )
    print(f"Sende {len(wav_bytes) / 1024:.1f} KiB an dsam …", flush=True)
    answer = send_audio(wav_bytes, args.url, args.token)
    print("Antwort empfangen.", flush=True)
    if args.output:
        Path(args.output).write_bytes(answer)
    if not args.no_play:
        play_wav(answer, audio_device(args.output_device))


def main() -> None:
    parser = argparse.ArgumentParser(description="SCP-079 relay audio bridge")
    parser.add_argument("--url", default=DEFAULT_URL, help="z.B. http://dsam:7860")
    parser.add_argument("--token", default=DEFAULT_TOKEN)
    parser.add_argument("--continuous", action="store_true", help="Nach jeder Antwort erneut lauschen")
    parser.add_argument("--file", help="WAV senden statt Mikrofon aufzunehmen")
    parser.add_argument("--output", help="Antwort zusätzlich als WAV speichern")
    parser.add_argument("--no-play", action="store_true")
    parser.add_argument("--input-device", help="Name/Index der Aufnahmequelle, z.B. Discord-Monitor")
    parser.add_argument("--output-device", help="Name/Index des virtuellen Discord-Mikrofons")
    parser.add_argument("--list-devices", action="store_true")
    parser.add_argument("--sample-rate", type=int, default=16_000)
    parser.add_argument("--threshold", type=float, default=0.012, help="RMS-Sprachschwelle 0..1")
    parser.add_argument("--silence", type=float, default=1.0)
    parser.add_argument("--max-seconds", type=float, default=15.0)
    args = parser.parse_args()

    if args.list_devices:
        print(sd.query_devices())
        return

    while True:
        try:
            one_cycle(args)
        except KeyboardInterrupt:
            print("Beendet.")
            return
        except Exception as exc:
            print(f"Fehler: {exc}", file=sys.stderr, flush=True)
            if not args.continuous:
                raise SystemExit(1) from exc
            time.sleep(1.5)
        if not args.continuous or args.file:
            return


if __name__ == "__main__":
    main()
