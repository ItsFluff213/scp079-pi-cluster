#!/usr/bin/env python3
"""Windows/Linux desktop bridge for Discord + Voicemeeter.

This script does not install an audio driver. For Windows, Voicemeeter Banana
is recommended so you can hear Discord while the script hears the same audio.
"""

from __future__ import annotations

import argparse
from contextlib import ExitStack
import io
import json
import os
import sys
import threading
import time
import wave
from pathlib import Path
from urllib.parse import unquote

import numpy as np
import requests
import sounddevice as sd
try:
    import soundcard as sc
except ImportError:
    sc = None


DEFAULT_URL = os.getenv("SCP079_DASHBOARD_URL", "http://logic:7860").rstrip("/")
DEFAULT_TOKEN = os.getenv("SCP079_API_TOKEN", "")
CONFIG_DIR = Path(os.getenv("APPDATA", str(Path.home()))) / "scp079"
CONFIG_PATH = CONFIG_DIR / "desktop_bridge.json"


def audio_device(value: str | None) -> str | int | None:
    if value is None or value == "":
        return None
    return int(value) if value.isdecimal() else value


def list_devices() -> None:
    print(sd.query_devices())
    print()
    print("Simple VB-CABLE test routing:")
    print("  Script Input           -> your microphone")
    print("  Script Output          -> CABLE Input")
    print("  Script Monitor         -> your headphones")
    print("  Discord Mic            -> CABLE Output")
    if sc is not None:
        print("\nWASAPI loopback devices (for --loopback-device):")
        for i, mic in enumerate(sc.all_microphones(include_loopback=True)):
            print(f"  {i}: {mic.name}")


def resolve_loopback(value: str | int):
    if sc is None:
        raise RuntimeError("WASAPI loopback requires: python -m pip install soundcard")
    requested = str(value)
    if requested.isdecimal():
        try:
            requested = str(sd.query_devices(int(requested))["name"])
        except Exception:
            pass
    devices = sc.all_microphones(include_loopback=True)
    needle = requested.lower()
    for mic in devices:
        if needle in mic.name.lower() or mic.name.lower() in needle:
            return mic
    # Match the distinctive part (e.g. G733) when Windows localises names.
    words = [w for w in needle.replace("(", " ").replace(")", " ").split() if len(w) >= 4]
    for mic in devices:
        if any(w in mic.name.lower() for w in words):
            return mic
    raise RuntimeError(f"No WASAPI loopback device matched '{value}'. Run --list-devices.")
    print()
    print("Full Voicemeeter Banana routing:")
    print("  Your real mic          -> B1")
    print("  Discord Output         -> Voicemeeter AUX Input -> A1, not B1")
    print("  Script Input           -> Voicemeeter AUX Output")
    print("  Script Output          -> Voicemeeter Input -> B1")
    print("  Discord Mic            -> Voicemeeter Output")


def load_config() -> dict[str, str]:
    if not CONFIG_PATH.is_file():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_config(config: dict[str, str]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")


def show_numbered_devices() -> None:
    devices = sd.query_devices()
    for index, device in enumerate(devices):
        inputs = int(device.get("max_input_channels", 0))
        outputs = int(device.get("max_output_channels", 0))
        name = device.get("name", "")
        print(f"{index:>3}  in:{inputs:<2} out:{outputs:<2}  {name}")


def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{prompt}{suffix}: ").strip()
    return value or default


def setup_wizard(existing: dict[str, str]) -> dict[str, str]:
    print("SCP-079 desktop setup")
    print()
    print("Set Discord output to Voicemeeter Input or CABLE Input.")
    print("Set Discord microphone to CABLE Output, Voicemeeter AUX Output, or another return cable.")
    print("Set monitor device to your headphones if you still want to hear Discord through this script.")
    print()
    show_numbered_devices()
    print()
    config = dict(existing)
    config["url"] = ask("Voice-core URL", config.get("url", DEFAULT_URL)).rstrip("/")
    config["token"] = ask("SCP079_API_TOKEN", config.get("token", DEFAULT_TOKEN))
    config["speaker"] = ask("Speaker name", config.get("speaker", "discord"))
    config["input_device"] = ask(
        "Python input device index/name (usually Voicemeeter Output)",
        config.get("input_device", ""),
    )
    config["output_device"] = ask(
        "Python output device index/name (usually CABLE Input or Voicemeeter AUX Input)",
        config.get("output_device", ""),
    )
    config["monitor_device"] = ask(
        "Optional headphones/monitor device, empty for none",
        config.get("monitor_device", ""),
    )
    save_config(config)
    print()
    print(f"Saved config: {CONFIG_PATH}")
    return config


def apply_config(args: argparse.Namespace, config: dict[str, str]) -> argparse.Namespace:
    for key in ("url", "token", "speaker", "input_device", "output_device", "monitor_device"):
        if getattr(args, key) in (None, "") and config.get(key):
            setattr(args, key, config[key])
    return args


def record_utterance(
    input_device: str | int | None,
    loopback_device: str | int | None,
    monitor_device: str | int | None,
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
    monitor_stream = None
    loopback = resolve_loopback(loopback_device) if loopback_device is not None else None
    with ExitStack() as stack:
        desktop_stream = stack.enter_context(loopback.recorder(samplerate=sample_rate, channels=1, blocksize=block_size)) if loopback else None
        mic_stream = stack.enter_context(sd.InputStream(
            samplerate=sample_rate, channels=1, dtype="int16", blocksize=block_size, device=input_device
        )) if (input_device is not None or not loopback) else None
        try:
            if monitor_device is not None:
                monitor_stream = sd.OutputStream(
                    samplerate=sample_rate,
                    channels=2,
                    dtype="int16",
                    blocksize=block_size,
                    device=monitor_device,
                )
                monitor_stream.start()

            for _ in range(max_blocks):
                if desktop_stream is not None:
                    block = desktop_stream.record(numframes=block_size)
                    desktop = np.asarray(block[:, 0] if block.ndim > 1 else block, dtype=np.float32)
                    desktop = np.clip(desktop, -1.0, 1.0)
                    desktop = (desktop * 32767.0).astype(np.int16)
                else:
                    desktop = np.zeros(block_size, dtype=np.int16)
                if mic_stream is not None:
                    mic_block = mic_stream.read(block_size)[0]
                    mic = np.asarray(mic_block[:, 0], dtype=np.int16)
                else:
                    mic = np.zeros(block_size, dtype=np.int16)
                # Mix mic + desktop while avoiding int16 overflow.
                mono = np.clip(desktop.astype(np.int32) + mic.astype(np.int32), -32768, 32767).astype(np.int16)
                if monitor_stream is not None:
                    monitor_stream.write(np.column_stack((mono, mono)))
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
        finally:
            if monitor_stream is not None:
                monitor_stream.stop()
                monitor_stream.close()

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


def send_audio(url: str, token: str, speaker: str, wav_bytes: bytes, timeout: float) -> tuple[bytes, str, str]:
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
    transcript = unquote(response.headers.get("X-SCP079-Transcript", "")).strip()
    answer = unquote(response.headers.get("X-SCP079-Answer", "")).strip()
    return response.content, transcript, answer


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


def write_debug_wav(path: str | None, wav_bytes: bytes) -> None:
    if not path:
        return
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(wav_bytes)


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
            loopback_device=audio_device(args.loopback_device),
            monitor_device=audio_device(args.monitor_device),
            sample_rate=args.sample_rate,
            block_ms=args.block_ms,
            threshold=args.threshold,
            silence_seconds=args.silence,
            max_seconds=args.max_seconds,
            preroll_ms=args.preroll_ms,
        )
    write_debug_wav(args.save_input, wav_bytes)

    print(f"sending {len(wav_bytes) / 1024:.1f} KiB to {args.url}", flush=True)
    answer, transcript, reply_text = send_audio(args.url, args.token, args.speaker, wav_bytes, args.timeout)
    print("answer received", flush=True)
    print("-" * 60, flush=True)
    if transcript:
        print(f"heard    : {transcript}", flush=True)
    else:
        print("heard    : <not provided by voice-core>", flush=True)
    if reply_text:
        print(f"scp079   : {reply_text}", flush=True)
    else:
        print("scp079   : <not provided by voice-core>", flush=True)
    print("-" * 60, flush=True)

    if args.save_answer:
        write_debug_wav(args.save_answer, answer)
    if not args.no_play:
        play_answer(answer, audio_device(args.output_device), audio_device(args.monitor_device))


def main() -> None:
    parser = argparse.ArgumentParser(description="SCP-079 desktop bridge with optional Windows WASAPI loopback")
    parser.add_argument("--url", default=DEFAULT_URL, help="voice-core URL, e.g. http://logic:7860")
    parser.add_argument("--token", default=DEFAULT_TOKEN)
    parser.add_argument("--speaker", default=os.getenv("SCP079_SPEAKER", "discord"))
    parser.add_argument("--input-device", help="recording device that receives Discord output")
    parser.add_argument("--loopback-device", help="Windows WASAPI playback device to capture (no virtual cable needed)")
    parser.add_argument("--output-device", help="playback device that feeds Discord microphone")
    parser.add_argument("--monitor-device", help="optional headphones/speakers to hear SCP-079 locally")
    parser.add_argument("--list-devices", action="store_true")
    parser.add_argument("--setup", action="store_true", help="interactive setup and save config")
    parser.add_argument("--continuous", action="store_true")
    parser.add_argument("--once", action="store_true", help="process one utterance and exit")
    parser.add_argument("--file", help="send a WAV file instead of listening")
    parser.add_argument("--save-input", help="write the latest captured input WAV to this path")
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

    config = load_config()
    if args.setup or (not config and not args.input_device and not args.output_device):
        config = setup_wizard(config)
    args = apply_config(args, config)

    if not args.file and not args.once:
        args.continuous = True

    print("SCP-079 desktop bridge active")
    print(f"  url            : {args.url}")
    print(f"  speaker        : {args.speaker}")
    print(f"  input device   : {args.input_device or '<system default>'}")
    print(f"  loopback       : {args.loopback_device or '<disabled>'}")
    print(f"  output device  : {args.output_device or '<system default>'}")
    print(f"  monitor device : {args.monitor_device or '<none>'}")
    print(f"  sample rate    : {args.sample_rate}")
    print()

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
