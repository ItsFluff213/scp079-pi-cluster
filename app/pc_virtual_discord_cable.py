#!/usr/bin/env python3
"""Windows/Linux desktop bridge for Discord virtual audio cables.

This script does not install an audio driver. On Windows use VB-CABLE,
VB-CABLE A+B, or Voicemeeter, then select those devices here.
"""

from __future__ import annotations

import argparse
import io
import os
import sys
import threading
import time
import wave
from pathlib import Path

import numpy as np
import requests
import sounddevice as sd


DEFAULT_URL = os.getenv("SCP079_DASHBOARD_URL", "http://logic:7860").rstrip("/")
DEFAULT_TOKEN = os.getenv("SCP079_API_TOKEN", "")


def audio_device(value: str | None) -> str | int | None:
    if value is None or value == "":
        return None
    return int(value) if value.isdecimal() else value


def list_devices() -> None:
    print(sd.query_devices())
    print()
    print("Typical VB-CABLE routing:")
    print("  Discord Output  -> Cable A Input")
    print("  Script Input    -> Cable A Output")
    print("  Script Output   -> Cable B Input")
    print("  Discord Mic     -> Cable B Output")


def record_utterance(
    input_device: str | int | None,
    sample_rate: int,
    block_ms: int,
    threshold: float,
    silence_seconds: float,
    max_seconds: float,
    preroll_ms: int,
) -> bytes:
    block_size = max(1, sample_rate * block_ms // 1000)
    silent_limit = max(1, int(silence_seconds * 1000 / block_ms))
    max_blocks = max(1, int(max_seconds * 1000 / block_ms))
    preroll_limit = max(1, int(preroll_ms / block_ms))
    blocks: list[np.ndarray] = []
    preroll: list[np.ndarray] = []
    speech_started = False
    silent_blocks = 0

    print("listening...", flush=True)
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
                print("warning: input overflow", file=sys.stderr)
            mono = block[:, 0].copy()
            rms = float(np.sqrt(np.mean((mono.astype(np.float32) / 32768.0) ** 2)))
            if not speech_started:
                preroll.append(mono)
                preroll = preroll[-preroll_limit:]
                if rms >= threshold:
                    speech_started = True
                    blocks.extend(preroll)
                    print("speech detected", flush=True)
            else:
                blocks.append(mono)
                silent_blocks = silent_blocks + 1 if rms < threshold else 0
                if silent_blocks >= silent_limit:
                    break

    if not speech_started or not blocks:
        raise RuntimeError("no speech detected")

    pcm = np.concatenate(blocks).astype("<i2", copy=False).tobytes()
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm)
    return output.getvalue()


def send_audio(url: str, token: str, speaker: str, wav_bytes: bytes, timeout: float) -> bytes:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    response = requests.post(
        f"{url}/api/audio",
        headers=headers,
        data={"speaker": speaker},
        files={"audio": ("discord.wav", wav_bytes, "audio/wav")},
        timeout=(4.0, timeout),
    )
    if not response.ok:
        raise RuntimeError(f"voice-core HTTP {response.status_code}: {response.text[:500]}")
    if "audio" not in response.headers.get("content-type", ""):
        raise RuntimeError("voice-core did not return audio")
    return response.content


def read_wav(wav_bytes: bytes) -> tuple[np.ndarray, int]:
    with wave.open(io.BytesIO(wav_bytes), "rb") as wav:
        if wav.getsampwidth() != 2:
            raise RuntimeError("only 16-bit PCM WAV is supported")
        channels = wav.getnchannels()
        sample_rate = wav.getframerate()
        samples = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2")
        if channels > 1:
            samples = samples.reshape(-1, channels)
        return samples, sample_rate


def play_samples(samples: np.ndarray, sample_rate: int, device: str | int | None) -> None:
    sd.play(samples, sample_rate, device=device, blocking=True)


def play_answer(
    wav_bytes: bytes,
    output_device: str | int | None,
    monitor_device: str | int | None,
) -> None:
    samples, sample_rate = read_wav(wav_bytes)
    threads = [
        threading.Thread(target=play_samples, args=(samples, sample_rate, output_device), daemon=True)
    ]
    if monitor_device is not None:
        threads.append(
            threading.Thread(target=play_samples, args=(samples, sample_rate, monitor_device), daemon=True)
        )
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()


def one_turn(args: argparse.Namespace) -> None:
    if args.file:
        wav_bytes = Path(args.file).read_bytes()
    else:
        wav_bytes = record_utterance(
            input_device=audio_device(args.input_device),
            sample_rate=args.sample_rate,
            block_ms=args.block_ms,
            threshold=args.threshold,
            silence_seconds=args.silence,
            max_seconds=args.max_seconds,
            preroll_ms=args.preroll_ms,
        )

    print(f"sending {len(wav_bytes) / 1024:.1f} KiB to {args.url}", flush=True)
    answer = send_audio(args.url, args.token, args.speaker, wav_bytes, args.timeout)
    print("answer received", flush=True)

    if args.save_answer:
        Path(args.save_answer).write_bytes(answer)
    if not args.no_play:
        play_answer(answer, audio_device(args.output_device), audio_device(args.monitor_device))


def main() -> None:
    parser = argparse.ArgumentParser(description="SCP-079 desktop virtual cable bridge for Discord")
    parser.add_argument("--url", default=DEFAULT_URL, help="voice-core URL, e.g. http://logic:7860")
    parser.add_argument("--token", default=DEFAULT_TOKEN)
    parser.add_argument("--speaker", default=os.getenv("SCP079_SPEAKER", "discord"))
    parser.add_argument("--input-device", help="recording device that receives Discord output")
    parser.add_argument("--output-device", help="playback device that feeds Discord microphone")
    parser.add_argument("--monitor-device", help="optional headphones/speakers to hear SCP-079 locally")
    parser.add_argument("--list-devices", action="store_true")
    parser.add_argument("--continuous", action="store_true")
    parser.add_argument("--file", help="send a WAV file instead of listening")
    parser.add_argument("--save-answer", help="write returned SCP-079 WAV to this file")
    parser.add_argument("--no-play", action="store_true")
    parser.add_argument("--sample-rate", type=int, default=16_000)
    parser.add_argument("--block-ms", type=int, default=60)
    parser.add_argument("--threshold", type=float, default=0.010)
    parser.add_argument("--silence", type=float, default=0.55)
    parser.add_argument("--max-seconds", type=float, default=8.0)
    parser.add_argument("--preroll-ms", type=int, default=350)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--retry-delay", type=float, default=1.0)
    args = parser.parse_args()

    if args.list_devices:
        list_devices()
        return

    while True:
        try:
            one_turn(args)
        except KeyboardInterrupt:
            print("stopped")
            return
        except Exception as exc:
            print(f"error: {exc}", file=sys.stderr, flush=True)
            if not args.continuous:
                raise SystemExit(1) from exc
            time.sleep(args.retry_delay)
        if not args.continuous or args.file:
            return


if __name__ == "__main__":
    main()
