SCP-079 / SBTalker voice data
=============================

These files are copied from Eibriel's MIT licensed Godot addon:

- Project: godot-tts-079
- Source: https://codeberg.org/Eibriel/godot-tts-079
- Published asset: https://store.godotengine.org/asset/eibriel/tts-079/
- Copyright: 2026 Eibriel
- License: MIT, see LICENSE in this directory

The Python voice-core uses these tables and sample blocks through
`app/scp079_godot_tts.py`, a Python runtime port of the addon logic.  This
avoids launching Godot on every Discord reply and keeps latency low on the
Raspberry Pi voice node.

