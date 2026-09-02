#!/usr/bin/env python3
"""Python runtime for Eibriel's MIT licensed Godot SCP-079 TTS addon.

The source addon lives at https://codeberg.org/Eibriel/godot-tts-079 and is
published as "Voice Synthesizer SCP079" for Godot.  This module ports the
runtime path to Python so the Raspberry Pi voice-core can synthesize the
SBTalker/SCP-079 voice directly without launching Godot for every response.

Bundled data files in ``app/tts_079_data`` are copied from the MIT addon:
``tables.json``, ``g2p_rules.json`` and ``blocks.bin``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import numpy as np
from scipy.io import wavfile


SAMPLE_RATE = 8522
SPEED_TABLE = [32, 36, 43, 56, 96, 10000, 128, 64, 42, 32]

VOWELS = set("AEIOUY")
FRONT_VOWELS = set("EIY")
VOICED_CONS = set("BDJGLMNRVWZ")
AT_CLASS = set("DJLNRSTWZ")
VOWEL_STARTS = set("AEIOU")
TERM_PUNCT = set("!.;?")

DIGRAPHS = {
    "AA": 7,
    "AH": 5,
    "AX": 6,
    "AY": 37,
    "AE": 4,
    "EH": 3,
    "AW": 42,
    "EY": 38,
    "AO": 10,
    "DH": 26,
    "DX": 15,
    "OY": 41,
    "ZH": 28,
    "UH": 8,
    "OW": 9,
    "IH": 1,
    "IX": 2,
    "IY": 39,
    "UW": 40,
    "TH": 22,
    "TX": 14,
    "SH": 24,
    "KX": 17,
    "PX": 12,
    "ER": 43,
    "NG": 32,
}

LOWERCASE = {
    "b": 18,
    "d": 19,
    "f": 21,
    "g": 20,
    "h": 34,
    "k": 16,
    "l": 29,
    "m": 30,
    "n": 31,
    "p": 11,
    "r": 35,
    "s": 23,
    "t": 13,
    "v": 25,
    "w": 36,
    "y": 33,
    "z": 27,
}

SPECIALS = {"[": 44, "]": 45, "\\": 57, "/": 56}
DIGITS = {str(i): 55 - i for i in range(10)}


class TTS079Godot:
    def __init__(self, data_dir: str | Path | None = None) -> None:
        self.data_dir = Path(data_dir) if data_dir else Path(__file__).resolve().parent / "tts_079_data"
        with (self.data_dir / "tables.json").open("r", encoding="utf-8") as f:
            tables = json.load(f)
        with (self.data_dir / "g2p_rules.json").open("r", encoding="utf-8") as f:
            self.rules: dict[str, list[dict[str, str]]] = json.load(f)
        self.transition_table: dict[str, dict[str, Any]] = tables["transition_table"]
        self.segment_lists: dict[str, list[dict[str, Any]]] = tables["segment_lists"]
        for entries in self.segment_lists.values():
            for entry in entries:
                entry["block_idx"] = int(entry["block_idx"])
        self.blocks = self._load_blocks(self.data_dir / "blocks.bin")

    @staticmethod
    def _load_blocks(path: Path) -> list[list[int]]:
        buf = path.read_bytes()
        pos = 0
        blocks: list[list[int]] = []
        while pos < len(buf):
            ln = buf[pos]
            blocks.append(list(buf[pos + 1 : pos + 1 + ln]))
            pos += 1 + ln
        return blocks

    @staticmethod
    def is_alpha(ch: str) -> bool:
        return len(ch) == 1 and "A" <= ch <= "Z"

    @staticmethod
    def is_space(ch: str) -> bool:
        return bool(ch) and ch.strip() == ""

    @staticmethod
    def is_vowel(ch: str) -> bool:
        return ch in VOWELS or ch == "\x00"

    @classmethod
    def is_consonant(cls, ch: str) -> bool:
        return cls.is_alpha(ch) and ch not in VOWELS

    def match_rctx(self, word: str, pos: int, pattern: str) -> tuple[bool, int]:
        i = pos
        for ch in pattern:
            if i >= len(word):
                return False, pos
            if ch in {"'", "."} or self.is_alpha(ch):
                if word[i] != ch:
                    return False, pos
            else:
                return False, pos
            i += 1
        return True, i

    def _match_suffix_percent(self, word: str, pos: int) -> tuple[bool, int]:
        for suf in ("ERS", "ELY", "ING", "ER", "ED", "ES", "E"):
            end = pos + len(suf)
            if word[pos:end] == suf and (end >= len(word) or word[end] in {" ", "\x00"}):
                return True, end
        return False, pos

    def _match_suffix_bang(self, word: str, pos: int) -> tuple[bool, int]:
        if pos >= len(word) or not self.is_alpha(word[pos]):
            return True, pos
        ch = word[pos]
        nx = word[pos + 1] if pos + 1 < len(word) else ""
        if ch == "S" and not self.is_alpha(nx):
            return True, pos + 1
        if ch == "L" and nx == "Y" and (pos + 2 >= len(word) or not self.is_alpha(word[pos + 2])):
            return True, pos + 2
        if word[pos : pos + 4] == "MENT" and (pos + 4 >= len(word) or not self.is_alpha(word[pos + 4])):
            return True, pos + 4
        if word[pos : pos + 4] == "NESS" and (pos + 4 >= len(word) or not self.is_alpha(word[pos + 4])):
            return True, pos + 4
        return False, pos

    def _match_suffix_dash(self, word: str, pos: int) -> tuple[bool, int]:
        ch = word[pos] if pos < len(word) else ""
        nx = word[pos + 1] if pos + 1 < len(word) else ""
        if ch == "Y" and not self.is_alpha(nx):
            return True, pos + 1
        if ch == "I" and nx == "E" and (pos + 2 >= len(word) or not self.is_alpha(word[pos + 2])):
            return True, pos + 2
        return False, pos

    def match_bctx(self, word: str, pos: int, pattern: str) -> bool:
        i = pos
        p = 0
        while p < len(pattern):
            ch = pattern[p]
            wch = word[i] if i < len(word) else "\x00"
            if ch == "#":
                if not self.is_vowel(wch):
                    return False
                i += 1
                while i < len(word) and self.is_vowel(word[i]):
                    i += 1
            elif ch == "^":
                if wch == "Q" and i + 1 < len(word) and word[i + 1] == "U":
                    i += 2
                elif self.is_consonant(wch):
                    i += 1
                else:
                    return False
            elif ch == "*":
                if not self.is_consonant(wch) and not (wch == "Q" and i + 1 < len(word) and word[i + 1] == "U"):
                    return False
                i += 2 if wch == "Q" and i + 1 < len(word) and word[i + 1] == "U" else 1
                while i < len(word) and self.is_consonant(word[i]):
                    i += 1
            elif ch == ":":
                while i < len(word) and self.is_consonant(word[i]):
                    i += 1
            elif ch == "+":
                if wch not in FRONT_VOWELS:
                    return False
                i += 1
            elif ch == ".":
                if wch not in VOICED_CONS:
                    return False
                i += 1
            elif ch == "%":
                ok, _ = self._match_suffix_percent(word, i)
                if not ok:
                    return False
            elif ch == "!":
                ok, _ = self._match_suffix_bang(word, i)
                if not ok:
                    return False
            elif ch == "-":
                ok, _ = self._match_suffix_dash(word, i)
                if not ok:
                    return False
            elif ch in {" ", "'"}:
                if wch != ch:
                    return False
                i += 1
            elif self.is_alpha(ch):
                if wch != ch:
                    return False
                i += 1
            else:
                return False
            p += 1
        return True

    def match_lctx(self, word: str, pos: int, pattern: str) -> bool:
        i = pos - 1
        for ch in pattern:
            wch = word[i] if 0 <= i < len(word) else "\x00"
            if ch == "#":
                if not self.is_vowel(wch):
                    return False
                i -= 1
                while i >= 0 and self.is_vowel(word[i]):
                    i -= 1
            elif ch == "^":
                if not self.is_consonant(wch):
                    return False
                i -= 1
            elif ch == "*":
                if not self.is_consonant(wch):
                    if wch == "U" and i - 1 >= 0 and word[i - 1] == "Q":
                        i -= 2
                    else:
                        return False
                else:
                    i -= 1
                    while i >= 0 and self.is_consonant(word[i]):
                        i -= 1
            elif ch == ":":
                while i >= 0 and self.is_consonant(word[i]):
                    i -= 1
            elif ch == "+":
                if wch not in FRONT_VOWELS:
                    return False
                i -= 1
            elif ch == ".":
                if wch not in VOICED_CONS:
                    return False
                i -= 1
            elif ch == "@":
                if wch == "H":
                    prev = word[i - 1] if i - 1 >= 0 else "\x00"
                    if prev not in {"C", "S", "T"}:
                        return False
                    i -= 2
                elif wch in AT_CLASS:
                    i -= 1
                else:
                    return False
            elif ch == "&":
                if wch == "H" and i - 1 >= 0 and word[i - 1] in {"C", "S"}:
                    i -= 2
                elif wch in {"S", "Z"}:
                    i -= 1
                else:
                    return False
            elif ch in {" ", "'"}:
                if wch != ch:
                    return False
                i -= 1
            elif self.is_alpha(ch):
                if wch != ch:
                    return False
                i -= 1
            else:
                return False
        return True

    def preprocess(self, sentence: str) -> list[str]:
        upper = sentence.upper().replace(".", "")
        cleaned = re.sub(r"[^A-Z', ]", "", upper)
        return [w for w in cleaned.split() if re.search(r"[A-Z,]", w)]

    def g2p_sentence(self, sentence: str) -> str:
        words = self.preprocess(sentence)
        full = " " + " ".join(words) + " "
        result: list[str] = []
        i = 1
        while i < len(full):
            ch = full[i]
            if ch in {" ", "'", "."}:
                i += 1
                continue
            if ch == ",":
                result.append("  ")
                i += 1
                continue
            if not self.is_alpha(ch):
                i += 1
                continue
            phoneme = ""
            advance = 1
            for rule in self.rules.get(ch, []):
                ok, rpos = self.match_rctx(full, i + 1, rule["rctx"])
                if not ok:
                    continue
                if not self.match_lctx(full, i, rule["lctx"]):
                    continue
                if not self.match_bctx(full, rpos, rule["bctx"]):
                    continue
                phoneme = rule["phon"]
                advance = rpos - i
                break
            result.append(phoneme)
            i += max(1, advance)
        stripped = sentence.rstrip()
        if stripped and stripped[-1] in TERM_PUNCT:
            result.append(stripped[-1])
        return "".join(result)

    @staticmethod
    def _count_vowels_and_terminal(s: str) -> tuple[int, str]:
        n = 0
        term = ""
        i = 1
        while i < len(s):
            c = s[i]
            if c in VOWEL_STARTS:
                n += 1
                i += 1
            if i < len(s) and s[i] in TERM_PUNCT:
                term = s[i]
                break
            i += 1
        return min(n, 100), term

    @staticmethod
    def _build_prosody_array(n: int, term: str) -> list[int]:
        if n < 1:
            return []
        array = [0] + [7 - ((n // 2 + 4 * i) // n) for i in range(1, n + 1)]
        if term == ".":
            if n >= 1:
                array[n] = 0
            if n >= 2:
                array[n - 1] = 1
            if n >= 3:
                array[n - 2] = 2
        elif term == ";":
            if n >= 1:
                array[n] = 2
        elif term == "?":
            if n >= 1:
                array[n] = 9
            if n >= 2:
                array[n - 1] = 7
        elif term == "!":
            for i in range(1, n + 1):
                if array[i] < 8:
                    array[i] += 2
            array[1] = 9
            if n >= 1:
                array[n] = 9
            if n >= 2:
                array[n - 1] = 8
        return array

    def insert_digit_prosody(self, display: str) -> str:
        n, term = self._count_vowels_and_terminal(display)
        array = self._build_prosody_array(n, term)
        if not array:
            return display
        out = [display[:1]] if display else []
        di = 0
        last_emitted = 5
        delta = 0
        stress = 0
        i = 1
        while i < len(display):
            c = display[i]
            if c == "#":
                stress += 1
                i += 1
                continue
            if c == "@":
                stress = max(0, stress - 1)
                i += 1
                continue
            if c == "/":
                delta += 1
                i += 1
                continue
            if c == "\\":
                delta -= 1
                i += 1
                continue
            if c in VOWEL_STARTS:
                di += 1
                if 1 < di <= n and stress == 0:
                    v = max(0, min(9, array[di] + delta))
                    if v != last_emitted:
                        out.append(chr(ord("0") + v))
                        last_emitted = v
                out.append(c)
                i += 1
                if i < len(display):
                    out.append(display[i])
                i += 1
            else:
                out.append(c)
                i += 1
        return "".join(out)

    def convert_phoneme_to_binary(self, display: str) -> list[int]:
        out: list[int] = []
        i = 1 if display.startswith(" ") else 0
        while i < len(display):
            c = display[i]
            if c in TERM_PUNCT:
                break
            if self.is_space(c):
                out.append(0)
                i += 1
                continue
            if c in DIGITS:
                out.append(DIGITS[c])
                i += 1
                continue
            if c in SPECIALS:
                out.append(SPECIALS[c])
                i += 1
                continue
            if c in LOWERCASE:
                out.append(LOWERCASE[c])
                i += 1
                continue
            if "A" <= c <= "Z" and i + 1 < len(display):
                digraph = c + display[i + 1]
                if digraph in DIGRAPHS:
                    out.append(DIGRAPHS[digraph])
                    i += 2
                    continue
            i += 1
        out.append(0)
        return out

    def get_synth_binary(self, text: str, pitch_level: int = 5) -> list[int]:
        text_norm = normalize_text(text).rstrip()
        if text_norm and text_norm[-1] not in "!.;?":
            text_norm += "."
        g2p = self.g2p_sentence(text_norm)
        display = self.insert_digit_prosody(" " + g2p)
        body = self.convert_phoneme_to_binary(display)
        return [0] + body + [0] * 10

    @staticmethod
    def _idiv_trunc(num: int, den: int) -> int:
        return int(num / den)

    def parse_synth_binary(self, raw: list[int], pitch_level: int) -> list[tuple[int, int, int]]:
        b8a = 0
        a7c = 0
        result: list[tuple[int, int, int]] = []
        i = 0
        while i < len(raw):
            byte = raw[i]
            if byte < 44:
                result.append((byte, b8a, a7c))
                a7c = 0
                i += 1
            elif byte in {44, 45}:
                nxt = raw[i + 1] if i + 1 < len(raw) else 0
                if 46 <= nxt <= 55:
                    a7c = (55 - nxt) if byte == 44 else (nxt - 55)
                    i += 2
                else:
                    a7c = 5 if byte == 44 else -5
                    i += 1
            elif 46 <= byte <= 55:
                b8a = (byte - 45 - pitch_level) * 10
                nxt = raw[i + 1] if i + 1 < len(raw) else 0
                if 46 <= nxt <= 55:
                    b8a += nxt - 55
                    i += 2
                else:
                    i += 1
            elif byte == 57:
                b8a = min(70, b8a + 10)
                i += 1
            elif byte == 56:
                b8a = max(-50, b8a - 10)
                i += 1
            else:
                i += 1
        return result

    @classmethod
    def _speed_idx(cls, b8a: int, pitch_level: int, a7a: int = 0) -> int:
        return max(0, min(9, pitch_level + a7a + cls._idiv_trunc(2 * b8a, 19)))

    def play_chain_blocks(
        self,
        ptr: int | None,
        t_rev: bool,
        out: list[int],
        b88: int,
        b89: int,
        a80: int,
        speed_idx: int,
    ) -> tuple[int, int]:
        if ptr is None:
            return b88, a80
        entries = list(self.segment_lists.get(str(ptr), []))
        if not entries:
            return b88, a80
        has_voiced_path = any(not entry["is_voiced"] for entry in entries)
        if t_rev and has_voiced_path:
            entries.reverse()

        di = speed_idx * 2
        for entry in entries:
            period_len = int(entry["period_len"])
            a82 = 1
            block = self.blocks[int(entry["block_idx"])]

            if not entry["is_voiced"]:
                while a82 > 0:
                    diff = b89 - b88
                    step = 0
                    if diff > 0:
                        step = (diff >> 4) + 1
                    elif diff < 0:
                        step = diff >> 4
                    b88 += step

                    if b88 > 0:
                        last_val = out[-1] if out else 0
                        out.extend([last_val] * b88)
                        b86 = period_len
                    else:
                        b86 = (period_len + b88) if period_len >= 75 else period_len
                        b86 = max(0, b86)

                    a80 -= 16
                    if a80 <= 0:
                        a80 += SPEED_TABLE[speed_idx]
                        if di > 10:
                            a82 -= 1
                            if a82 == 0:
                                break
                        elif di < 10:
                            a82 += 1

                    if b86 > 0 and block:
                        out.extend(block[:b86])
                    a82 -= 1
            else:
                b87 = period_len >> 3
                b86 = period_len + b87
                while a82 > 0:
                    b86 -= b87
                    if b86 < b87:
                        b86 = b87

                    if t_rev:
                        a80 -= 16
                        if a80 <= 0:
                            a80 += SPEED_TABLE[speed_idx]
                            if di > 10:
                                a82 -= 1
                                if a82 == 0:
                                    break
                            elif di < 10:
                                a82 += 1

                    if b86 > 0 and block:
                        out.extend(block[:b86])
                    a82 -= 1

        return b88, a80

    def synthesise_u8(self, text: str, pitch_level: int = 5) -> np.ndarray:
        raw = self.get_synth_binary(text, pitch_level)
        seq = self.parse_synth_binary(raw, pitch_level)
        samples: list[int] = []
        last = len(seq) - 2
        b88 = 0
        a80 = SPEED_TABLE[5]

        for i in range(max(0, len(seq) - 1)):
            prev_idx, prev_b8a, prev_a7a = seq[i]
            curr_idx, curr_b8a, curr_a7a = seq[i + 1]
            entry = self.transition_table.get(f"{prev_idx},{curr_idx}")
            if entry is None:
                continue
            if i > 0 and entry["t1"] is not None:
                b88, a80 = self.play_chain_blocks(
                    entry["t1"],
                    bool(entry["t1_rev"]),
                    samples,
                    b88,
                    prev_b8a,
                    a80,
                    self._speed_idx(prev_b8a, pitch_level, prev_a7a),
                )
            if i < last and entry["t2"] is not None:
                si = self._speed_idx(curr_b8a, pitch_level, curr_a7a)
                a80 = SPEED_TABLE[si]
                b88, a80 = self.play_chain_blocks(
                    entry["t2"],
                    bool(entry["t2_rev"]),
                    samples,
                    b88,
                    curr_b8a,
                    a80,
                    si,
                )

        if not samples:
            samples = [128] * int(0.2 * SAMPLE_RATE)
        return np.asarray(samples, dtype=np.uint8)

    @staticmethod
    def u8_to_i16(samples: np.ndarray) -> np.ndarray:
        high = np.bitwise_xor(samples.astype(np.uint8), np.uint8(0x80)).astype(np.int16)
        signed_high = np.where(high >= 128, high - 256, high).astype(np.int16)
        return (signed_high.astype(np.int32) * 256).astype(np.int16)

    def synthesise_i16(self, text: str, pitch_level: int = 5) -> np.ndarray:
        return self.u8_to_i16(self.synthesise_u8(text, pitch_level))

    def synthesise_to_wav(self, text: str, output_path: str | Path, pitch_level: int = 5) -> None:
        wavfile.write(output_path, SAMPLE_RATE, self.synthesise_i16(text, pitch_level))


_ENGINE: TTS079Godot | None = None


def normalize_text(text: str) -> str:
    """Make LLM output pronounceable by the original English G2P rules."""
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

    text = re.sub(r"\bSCP[- ]?079\b", "S C P zero seven nine", text, flags=re.IGNORECASE)
    text = re.sub(r"\bSCP\b", "S C P", text, flags=re.IGNORECASE)

    def expand_number(match: re.Match[str]) -> str:
        return " ".join(digit_words[ch] for ch in match.group(0))

    text = re.sub(r"\d+", expand_number, text)
    text = text.replace("&", " and ")
    text = text.replace("@", " at ")
    text = text.replace("%", " percent ")
    return text


def engine() -> TTS079Godot:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = TTS079Godot()
    return _ENGINE


def synthesise_to_wav(text: str, output_path: str | Path, pitch_level: int = 5) -> None:
    engine().synthesise_to_wav(text, output_path, pitch_level=pitch_level)
