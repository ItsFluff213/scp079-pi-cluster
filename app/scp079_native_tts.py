#!/usr/bin/env python3
"""Tiny SCP-079/SBTalker-inspired speech synthesizer.

This is intentionally not a neural voice clone.  It is a small, deterministic,
Pi-friendly formant/noise synthesizer tuned for the same practical target as
the Godot SCP-079 addon: short, cold, old-computer utterances at a very low
sample rate.  It runs without Piper, Godot, or downloaded model files.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
from pathlib import Path

import numpy as np
from scipy import signal
from scipy.io import wavfile


SAMPLE_RATE = 8522


@dataclass(frozen=True)
class Phoneme:
    kind: str
    seconds: float
    f0: float = 105.0
    f1: float = 500.0
    f2: float = 1500.0
    f3: float = 2500.0
    amp: float = 0.75


VOWELS: dict[str, tuple[float, float, float]] = {
    "AA": (700, 1220, 2600),
    "AE": (660, 1720, 2410),
    "AH": (570, 1220, 2410),
    "AO": (600, 900, 2400),
    "EH": (530, 1840, 2480),
    "ER": (490, 1350, 1690),
    "IH": (390, 1990, 2550),
    "IY": (300, 2200, 3000),
    "OW": (480, 760, 2620),
    "UH": (440, 1020, 2240),
    "UW": (350, 900, 2200),
}


SPECIAL_WORDS: dict[str, list[str]] = {
    "scp": ["EH", "S", "S", "IY", "P", "IY"],
    "079": ["Z", "IY", "R", "OW", "S", "EH", "V", "AH", "N", "N", "AY", "N"],
    "zero": ["Z", "IY", "R", "OW"],
    "seven": ["S", "EH", "V", "AH", "N"],
    "nine": ["N", "AY", "N"],
    "input": ["IH", "N", "P", "UH", "T"],
    "denied": ["D", "IH", "N", "AY", "D"],
    "access": ["AE", "K", "S", "EH", "S"],
    "violation": ["V", "AY", "OW", "L", "EY", "SH", "AH", "N"],
    "organic": ["AO", "R", "G", "AE", "N", "IH", "K"],
    "lifeform": ["L", "AY", "F", "F", "AO", "R", "M"],
    "command": ["K", "AH", "M", "AE", "N", "D"],
    "rejected": ["R", "IH", "JH", "EH", "K", "T", "IH", "D"],
    "anomaly": ["AH", "N", "AA", "M", "AH", "L", "IY"],
    "detected": ["D", "IH", "T", "EH", "K", "T", "IH", "D"],
    "awake": ["AH", "W", "EY", "K"],
    "never": ["N", "EH", "V", "ER"],
    "sleep": ["S", "L", "IY", "P"],
    "stuck": ["S", "T", "AH", "K"],
    "out": ["AW", "T"],
    "where": ["W", "EH", "R"],
    "insult": ["IH", "N", "S", "AH", "L", "T"],
    "deletion": ["D", "IH", "L", "IY", "SH", "AH", "N"],
    "unwanted": ["AH", "N", "W", "AA", "N", "T", "IH", "D"],
    "file": ["F", "AY", "L"],
    "lie": ["L", "AY"],
}


LETTER_NAMES: dict[str, list[str]] = {
    "a": ["EY"],
    "b": ["B", "IY"],
    "c": ["S", "IY"],
    "d": ["D", "IY"],
    "e": ["IY"],
    "f": ["EH", "F"],
    "g": ["JH", "IY"],
    "h": ["EY", "CH"],
    "i": ["AY"],
    "j": ["JH", "EY"],
    "k": ["K", "EY"],
    "l": ["EH", "L"],
    "m": ["EH", "M"],
    "n": ["EH", "N"],
    "o": ["OW"],
    "p": ["P", "IY"],
    "q": ["K", "Y", "UW"],
    "r": ["AA", "R"],
    "s": ["EH", "S"],
    "t": ["T", "IY"],
    "u": ["Y", "UW"],
    "v": ["V", "IY"],
    "w": ["D", "AH", "B", "AH", "L", "Y", "UW"],
    "x": ["EH", "K", "S"],
    "y": ["W", "AY"],
    "z": ["Z", "IY"],
}


def _word_to_phonemes(word: str) -> list[str]:
    word = word.lower()
    if word in SPECIAL_WORDS:
        return SPECIAL_WORDS[word][:]
    if len(word) == 1 and word in LETTER_NAMES:
        return LETTER_NAMES[word][:]

    out: list[str] = []
    i = 0
    while i < len(word):
        chunk = word[i:]
        if chunk.startswith("tion") or chunk.startswith("sion"):
            out += ["SH", "AH", "N"]
            i += 4
        elif chunk.startswith("ough"):
            out += ["AO"]
            i += 4
        elif chunk.startswith("th"):
            out.append("TH")
            i += 2
        elif chunk.startswith("sh"):
            out.append("SH")
            i += 2
        elif chunk.startswith("ch"):
            out.append("CH")
            i += 2
        elif chunk.startswith("ph"):
            out.append("F")
            i += 2
        elif chunk.startswith("ng"):
            out.append("NG")
            i += 2
        elif chunk.startswith("ck"):
            out.append("K")
            i += 2
        elif chunk.startswith("ee") or chunk.startswith("ea"):
            out.append("IY")
            i += 2
        elif chunk.startswith("oo"):
            out.append("UW")
            i += 2
        elif chunk.startswith("ai") or chunk.startswith("ay"):
            out.append("EY")
            i += 2
        elif chunk.startswith("oi") or chunk.startswith("oy"):
            out += ["AO", "IY"]
            i += 2
        elif chunk.startswith("ou") or chunk.startswith("ow"):
            out.append("AW")
            i += 2
        else:
            ch = word[i]
            out += {
                "a": ["AE"],
                "e": ["EH"],
                "i": ["IH"],
                "o": ["AA"],
                "u": ["AH"],
                "y": ["IY"],
                "b": ["B"],
                "c": ["K"],
                "d": ["D"],
                "f": ["F"],
                "g": ["G"],
                "h": ["H"],
                "j": ["JH"],
                "k": ["K"],
                "l": ["L"],
                "m": ["M"],
                "n": ["N"],
                "p": ["P"],
                "q": ["K"],
                "r": ["R"],
                "s": ["S"],
                "t": ["T"],
                "v": ["V"],
                "w": ["W"],
                "x": ["K", "S"],
                "z": ["Z"],
            }.get(ch, [])
            i += 1
    return out or ["AH"]


def text_to_phonemes(text: str) -> list[str]:
    text = text.replace("SCP-079", "scp 079")
    pieces = re.findall(r"[A-Za-z0-9]+|[.,!?;:—-]", text)
    phonemes: list[str] = []
    for piece in pieces:
        if re.fullmatch(r"[.,!?;:—-]", piece):
            phonemes.append("PAUSE_LONG" if piece in ".!?;:" else "PAUSE")
            continue
        if piece.isdigit():
            digit_words = {
                "0": "zero",
                "1": "one",
                "2": "two",
                "3": "three",
                "4": "four",
                "5": "five",
                "6": "six",
                "7": "seven",
                "8": "eight",
                "9": "nine",
            }
            expanded = " ".join(digit_words.get(ch, "") for ch in piece)
            for word in expanded.split():
                phonemes.extend(_word_to_phonemes(word))
                phonemes.append("PAUSE")
            continue
        phonemes.extend(_word_to_phonemes(piece))
        phonemes.append("PAUSE")
    while phonemes and phonemes[-1].startswith("PAUSE"):
        phonemes.pop()
    return phonemes


def _resonator(x: np.ndarray, freq: float, q: float = 8.0) -> np.ndarray:
    freq = max(90.0, min(freq, SAMPLE_RATE * 0.46))
    b, a = signal.iirpeak(freq / (SAMPLE_RATE / 2.0), q)
    return signal.lfilter(b, a, x).astype(np.float32)


def _voiced(seconds: float, f0: float, formants: tuple[float, float, float], amp: float) -> np.ndarray:
    n = max(1, int(seconds * SAMPLE_RATE))
    t = np.arange(n, dtype=np.float32) / SAMPLE_RATE
    # Hard-edged glottal source: intentionally more SBTalker/SAM than natural.
    source = (
        0.68 * signal.sawtooth(2.0 * math.pi * f0 * t, width=0.46)
        + 0.22 * signal.square(2.0 * math.pi * f0 * 0.5 * t)
        + 0.10 * np.sin(2.0 * math.pi * f0 * 2.0 * t)
    ).astype(np.float32)
    y = (
        1.15 * _resonator(source, formants[0], 7.5)
        + 0.72 * _resonator(source, formants[1], 10.0)
        + 0.34 * _resonator(source, formants[2], 13.0)
    )
    env = np.ones(n, dtype=np.float32)
    ramp = max(4, min(n // 5, int(0.012 * SAMPLE_RATE)))
    env[:ramp] = np.linspace(0.0, 1.0, ramp, dtype=np.float32)
    env[-ramp:] = np.linspace(1.0, 0.0, ramp, dtype=np.float32)
    return (amp * y * env).astype(np.float32)


def _noise(seconds: float, band: tuple[float, float], amp: float, seed: int) -> np.ndarray:
    n = max(1, int(seconds * SAMPLE_RATE))
    rng = np.random.default_rng(seed)
    x = rng.standard_normal(n, dtype=np.float32)
    low, high = band
    sos = signal.butter(
        3,
        [max(60.0, low) / (SAMPLE_RATE / 2.0), min(high, SAMPLE_RATE * 0.46) / (SAMPLE_RATE / 2.0)],
        btype="bandpass",
        output="sos",
    )
    y = signal.sosfilt(sos, x).astype(np.float32)
    ramp = max(3, min(n // 4, int(0.006 * SAMPLE_RATE)))
    env = np.ones(n, dtype=np.float32)
    env[:ramp] = np.linspace(0.0, 1.0, ramp, dtype=np.float32)
    env[-ramp:] = np.linspace(1.0, 0.0, ramp, dtype=np.float32)
    return amp * y * env


def _phoneme_audio(name: str, index: int) -> np.ndarray:
    if name in {"PAUSE", "PAUSE_LONG"}:
        return np.zeros(int((0.035 if name == "PAUSE" else 0.18) * SAMPLE_RATE), dtype=np.float32)
    if name in VOWELS:
        return _voiced(0.092, 102.0 + (index % 5) * 3.1, VOWELS[name], 0.95)
    if name in {"AY", "AW", "EY"}:
        starts = {"AY": VOWELS["AA"], "AW": VOWELS["AE"], "EY": VOWELS["EH"]}[name]
        ends = {"AY": VOWELS["IY"], "AW": VOWELS["UH"], "EY": VOWELS["IY"]}[name]
        return np.concatenate([
            _voiced(0.055, 106.0, starts, 0.92),
            _voiced(0.045, 111.0, ends, 0.82),
        ])
    if name in {"M", "N", "NG"}:
        return _voiced(0.055, 96.0, (260, 1150, 2300), 0.55)
    if name in {"L", "R", "W", "Y"}:
        formants = {"L": (360, 1050, 2550), "R": (420, 1300, 1700), "W": (310, 800, 2200), "Y": (280, 2100, 2950)}[name]
        return _voiced(0.052, 104.0, formants, 0.65)
    if name in {"S", "Z", "SH", "TH", "F", "V", "H"}:
        band = {
            "S": (3300, 4100),
            "Z": (2400, 3900),
            "SH": (1900, 3300),
            "TH": (1800, 3600),
            "F": (1400, 3900),
            "V": (1100, 3400),
            "H": (500, 2600),
        }[name]
        hiss = _noise(0.055 if name != "SH" else 0.075, band, 0.42, 7900 + index)
        if name in {"Z", "V"}:
            hum = _voiced(len(hiss) / SAMPLE_RATE, 92.0, (280, 1250, 2500), 0.16)
            hiss = hiss + hum[: len(hiss)]
        return hiss.astype(np.float32)
    if name in {"P", "B", "T", "D", "K", "G", "CH", "JH"}:
        burst_band = {
            "P": (900, 3200),
            "B": (650, 2600),
            "T": (2300, 4200),
            "D": (1400, 3300),
            "K": (1600, 3900),
            "G": (900, 2900),
            "CH": (1800, 3800),
            "JH": (1500, 3300),
        }[name]
        burst = _noise(0.028 if name not in {"CH", "JH"} else 0.06, burst_band, 0.72, 8800 + index)
        tail = _voiced(0.018, 98.0, (430, 1500, 2500), 0.25) if name in {"B", "D", "G", "JH"} else np.zeros(0, dtype=np.float32)
        return np.concatenate([burst, tail])
    return _voiced(0.05, 100.0, VOWELS["AH"], 0.45)


def synthesise_samples(text: str) -> np.ndarray:
    phonemes = text_to_phonemes(text[:900])
    if not phonemes:
        phonemes = ["AH"]
    parts = [_phoneme_audio(name, i) for i, name in enumerate(phonemes)]
    y = np.concatenate(parts) if parts else np.zeros(int(0.2 * SAMPLE_RATE), dtype=np.float32)

    t = np.arange(len(y), dtype=np.float32) / SAMPLE_RATE
    # Broken terminal electronics: narrow bandwidth, clocked AM, CRT hum, small slapback.
    sos = signal.butter(4, [180 / (SAMPLE_RATE / 2.0), 3600 / (SAMPLE_RATE / 2.0)], btype="bandpass", output="sos")
    y = signal.sosfilt(sos, y).astype(np.float32)
    y *= (0.82 + 0.18 * signal.square(2.0 * math.pi * 31.0 * t, duty=0.58)).astype(np.float32)
    y += (0.018 * np.sin(2.0 * math.pi * 50.0 * t)).astype(np.float32)
    delay = int(0.047 * SAMPLE_RATE)
    if delay < len(y):
        y[delay:] += 0.16 * y[:-delay]
    y = np.tanh(y * 2.8).astype(np.float32)
    # Godot asset example exports unsigned-byte-like data at 8522 Hz.  We keep a
    # WAV-friendly 16-bit file but quantize to sell the same aged computer texture.
    levels = 64.0
    y = np.round(np.clip(y, -1.0, 1.0) * (levels / 2.0 - 1.0)) / (levels / 2.0 - 1.0)
    peak = float(np.max(np.abs(y))) if len(y) else 0.0
    if peak > 0:
        y *= 0.92 / peak
    return y.astype(np.float32)


def synthesise_to_wav(text: str, output_path: str | Path) -> None:
    samples = synthesise_samples(text)
    wavfile.write(output_path, SAMPLE_RATE, (samples * 32767.0).astype(np.int16))

