"""Build the editable SVG diagram using only the Python standard library.

Run from any directory: python3 docs/assets/architecture-src/build-architecture.py
The two existing hardware photographs are embedded so the SVG is self-contained.
"""

import base64
from html import escape
from pathlib import Path

SOURCE = Path(__file__).resolve().parent
parts = []


def add(markup):
    parts.append(markup)


def rect(x, y, w, h, fill, stroke="none", radius=10, extra=""):
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="1.5" {extra}/>')


def text(x, y, value, size=20, weight=400, color="#10213d", anchor="start", extra=""):
    add(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" '
        f'fill="{color}" text-anchor="{anchor}" {extra}>{escape(value)}</text>')


def icon(name, x, y, color="#10213d", size=28):
    add(f'<use href="#icon-{name}" x="{x}" y="{y}" width="{size}" height="{size}" color="{color}"/>')


def chip(x, y, w, label, symbol=None, stroke="#ff6c9a", color="#10213d", size=19):
    rect(x, y, w, 48, "#ffffff", stroke, 7)
    # Keep the icon and label together, centered as one group.
    group_width = len(label) * size * .49 + (40 if symbol else 0)
    start = x + (w - group_width) / 2
    if symbol:
        icon(symbol, round(start), y + 10, color)
        text(round(start + 40), y + 31, label, size, color=color)
    else:
        text(x + w / 2, y + 31, label, size, color=color, anchor="middle")


def arrow(x, y1, y2, color="#2379ff", marker="blue"):
    add(f'<path d="M{x} {y1} V{y2}" fill="none" stroke="{color}" stroke-width="3" marker-end="url(#{marker})"/>')


def stage(y, h, number, title, subtitle, hint, accent, background):
    add(f'<g id="stage-{number}" aria-label="{escape(title)}">')
    rect(32, y, 1440, h, f"url(#{background})", accent, 14, 'stroke-dasharray="7 4"')
    add(f'<circle cx="72" cy="{y+40}" r="25" fill="{accent}" stroke="#fff" stroke-width="1.5"/>')
    text(72, y + 50, str(number), 31, 700, "#fff", "middle")
    text(48, y + 96, title, 27, 700)
    for i, line in enumerate(subtitle):
        text(48, y + 124 + i * 26, line, 21)
    for i, line in enumerate(hint):
        text(48, y + h - 39 + i * 23, line, 19, color="#49627f", extra='font-style="italic"')
    add('</g>')


def bullet(y, value):
    add(f'<circle cx="340" cy="{y-6}" r="3.4" fill="#10213d"/>')
    text(357, y, value, 19)


add('''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
  width="2048" height="1132" viewBox="0 0 2048 1132" role="img" aria-labelledby="title description">
<title id="title">Geek Mind — One Agent Runtime, Multiple Embodiments</title>
<desc id="description">A four-stage closed loop: perception converts vision, sound, state, location and LiDAR into a Natural Language Data Bus; a single or dual Cortex LLM reasons and selects tools; local or cloud MCP servers invoke tools; robot execution maps actions to hardware and returns feedback to perception, state and memory. The right column preserves the Unitree Go2 mobile embodiment and ARX X5 manipulation embodiment with their existing hardware photographs.</desc>
<defs>
  <linearGradient id="canvas" x2="0" y2="1"><stop stop-color="#ffffff"/><stop offset="1" stop-color="#f4f7fb"/></linearGradient>
  <linearGradient id="pink"><stop stop-color="#ffe8ef"/><stop offset="1" stop-color="#fff8fb"/></linearGradient>
  <linearGradient id="gold"><stop stop-color="#fff5d9"/><stop offset="1" stop-color="#fffdf5"/></linearGradient>
  <linearGradient id="blue-bg"><stop stop-color="#e5f3ff"/><stop offset="1" stop-color="#f6fbff"/></linearGradient>
  <linearGradient id="purple"><stop stop-color="#eee5ff"/><stop offset="1" stop-color="#f8f4ff"/></linearGradient>
  <linearGradient id="go2-bg" x2="0" y2="1"><stop stop-color="#ffffff"/><stop offset="1" stop-color="#f0f6ff"/></linearGradient>
  <linearGradient id="arx-bg" x2="0" y2="1"><stop stop-color="#ffffff"/><stop offset="1" stop-color="#edfcf6"/></linearGradient>
  <marker id="blue" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto" markerUnits="strokeWidth"><path d="M0 0 L7 3 L0 6Z" fill="#2379ff"/></marker>
  <marker id="navy" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto" markerUnits="strokeWidth"><path d="M0 0 L7 3 L0 6Z" fill="#10213d"/></marker>
  <symbol id="icon-camera" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><path d="M3 6h5l2-3h4l2 3h5v14H3z"/><circle cx="12" cy="12" r="4"/></g></symbol>
  <symbol id="icon-mic" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="9" y="2" width="6" height="13" rx="3"/><path d="M5 10v2a7 7 0 0 0 14 0v-2M12 19v3M8 22h8"/></g></symbol>
  <symbol id="icon-robot" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><rect x="6" y="5" width="12" height="9" rx="2"/><path d="M12 2v3M8 1h8M8 14l-3 7H2M16 14l3 7h3M6 9H3v6M18 9h3v6"/><path d="M9 8v3M15 8v3"/></g></symbol>
  <symbol id="icon-pin" viewBox="0 0 24 24"><path d="M12 22S4 14 4 9a8 8 0 0 1 16 0c0 5-8 13-8 13Z" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="9" r="2.5" fill="currentColor"/></symbol>
  <symbol id="icon-radio" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M5 4a12 12 0 0 0 0 16M19 4a12 12 0 0 1 0 16M8 7a7 7 0 0 0 0 10M16 7a7 7 0 0 1 0 10"/><circle cx="12" cy="12" r="2"/></g></symbol>
  <symbol id="icon-image" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><rect x="2" y="3" width="20" height="18" rx="1"/><path d="m3 18 6-6 4 4 4-6 5 6"/><circle cx="8" cy="8" r="1"/></g></symbol>
  <symbol id="icon-wave" viewBox="0 0 24 24"><path d="M2 10v4M7 6v12M12 2v20M17 7v10M22 10v4" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/></symbol>
  <symbol id="icon-doc" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><path d="M4 2h10l6 6v14H4zM14 2v6h6M8 12h8M8 16h8M8 19h4"/></g></symbol>
  <symbol id="icon-cube" viewBox="0 0 24 24"><path d="m12 2 10 5v10l-10 5-10-5V7zm0 10L2 7m10 5 10-5M12 12v10" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></symbol>
  <symbol id="icon-spark" viewBox="0 0 24 24"><path d="M12 1C12 8 8 12 1 12c7 0 11 4 11 11 0-7 4-11 11-11C16 12 12 8 12 1Z" fill="currentColor"/></symbol>
  <symbol id="icon-model" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" stroke-width="1.7"><path d="m12 2 8.7 5v10L12 22l-8.7-5V7Z"/><path d="m12 6 5.2 3v6L12 18l-5.2-3V9ZM12 2v4M20.7 7l-3.5 2M20.7 17l-3.5-2M12 22v-4M3.3 17l3.5-2M3.3 7l3.5 2"/></g></symbol>
  <symbol id="icon-nav" viewBox="0 0 24 24"><path d="m2 10 20-8-8 20-3-9Z" fill="currentColor"/><path d="m11 13 7-7" stroke="#fff" stroke-width="1.4"/></symbol>
  <symbol id="icon-wrench" viewBox="0 0 24 24"><path d="M20 3a6 6 0 0 0-8 8L3 20a2 2 0 0 0 3 3l9-9a6 6 0 0 0 7-8l-4 4-4-4Z" fill="currentColor" transform="translate(0 -1)"/></symbol>
  <symbol id="icon-eye" viewBox="0 0 24 24"><path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7S1 12 1 12Z" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="12" r="4" fill="currentColor"/></symbol>
  <symbol id="icon-globe" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><ellipse cx="12" cy="12" rx="4" ry="10"/><path d="M2 12h20"/></g></symbol>
  <symbol id="icon-speaker" viewBox="0 0 24 24"><path d="M2 8h5l6-5v18l-6-5H2Z" fill="currentColor"/><path d="M16 7a7 7 0 0 1 0 10M19 4a11 11 0 0 1 0 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></symbol>
  <symbol id="icon-chat" viewBox="0 0 24 24"><path d="M21 11a9 9 0 0 1-13 8l-6 3 2-6A9 9 0 1 1 21 11Z" fill="none" stroke="currentColor" stroke-width="2"/><g fill="currentColor"><circle cx="8" cy="11" r="1"/><circle cx="12" cy="11" r="1"/><circle cx="16" cy="11" r="1"/></g></symbol>
  <symbol id="icon-face" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><path d="M8 14q4 5 8 0M8 8v1M16 8v1"/></g></symbol>
</defs>
<g font-family="Arial, Helvetica, sans-serif">
<rect width="2048" height="1132" fill="url(#canvas)"/>
''')

text(32, 49, "Geek Mind — One Agent Runtime, Multiple Embodiments", 34, 700)
text(32, 86, "From perception to action, with tools and feedback", 24, color="#49627f")
rect(1630, 25, 386, 75, "#eaf0f9", "#cbd7e8")
text(1650, 55, "Same agent, different robots", 21, 600)
text(1650, 82, "Go2 (mobile)  ·  ARX X5 (manipulator)", 18)

stage(124, 245, 1, "Perception", ["(Sensors +", "World Understanding)"], ["See, hear, know the world"], "#ee527e", "pink")
for x, w, label, symbol in [(312,176,"Vision","camera"),(500,176,"Sound","mic"),(688,176,"State","robot"),(876,220,"Location/GPS","pin"),(1108,190,"LiDAR","radio"),(1310,142,"···",None)]:
    chip(x, 140, w, label, symbol)
for x in [400, 588, 816, 986, 1203]:
    arrow(x, 190, 206, "#10213d", "navy")
for x,w,label,symbol in [(312,255,"VLM / Vision","image"),(580,195,"ASR","wave"),(788,284,"Platform State","doc"),(1085,367,"Spatial / 3D","cube")]:
    chip(x, 214, w, label, symbol)
rect(312, 275, 1140, 77, "#eff7ff", "#9dccff", 8)
icon("doc", 335, 294, "#123d8f", 35)
text(386, 320, "Natural Language Data Bus (NLDB)", 19, 700)
for y, value in [(296,'Vision: You see Alex, a human. He looks happy and is pointing to a chair.'),(319,'Sound:  You just heard: “Bits, run to the chair.”'),(342,'Odometry: 1.3, 2.71, 0.32       Power: 73%      ...')]:
    text(784, y, value, 14.5, extra='font-family="Consolas, Menlo, monospace"')

stage(389, 212, 2, "Cortex LLM", ["(Planning & Reasoning)"], ["Understand, decide,", "plan and select tools"], "#efa91a", "gold")
rect(312, 406, 1140, 178, "#ffffff", "#efa91a")
text(882, 435, "Single LLM or Dual LLM", 25, 700, anchor="middle")
for x,w,label,symbol in [(335,176,"OpenAI","model"),(525,176,"Gemini","spark"),(715,108,"···",None),(839,252,"Local (Qwen)","model"),(1151,276,"Cloud (OpenAI)","model")]:
    chip(x, 449, w, label, symbol, "#98c6ff", "#176bfa")
text(1121, 481, "+", 27, 700, anchor="middle")
bullet(525, "Take fused inputs (perception + state + memory)")
bullet(550, "Reason, plan, and select tools/actions")
bullet(575, "Maintain short-term / long-term memory")

stage(621, 196, 3, "MCP / Tools", ["(Action Interface)"], ["Call the right tools", "and get structured results"], "#2681ff", "blue-bg")
rect(312, 638, 1140, 162, "#ffffff", "#4595ff")
text(882, 668, "MCP Servers (Local / Cloud)", 25, 700, anchor="middle")
for x,w,label,symbol in [(332,205,"Navigation","nav"),(551,217,"Manipulation","wrench"),(782,258,"Perception Tools","eye"),(1054,230,"Web / Search","globe"),(1298,137,"···",None)]:
    chip(x, 683, w, label, symbol, "#98c6ff", "#176bfa")
bullet(757, "Provide structured tools and APIs")
bullet(783, "Handle tool invocation and return structured results")

stage(837, 184, 4, "Robot Execution", ["(Hardware Abstraction)"], ["Execute on real robots", "and return status"], "#8b51f5", "purple")
for x,w,label,symbol in [(312,237,"Movement","robot"),(563,191,"Sound","speaker"),(768,222,"Speech","chat"),(1004,302,"Facial Expression","face"),(1320,132,"···",None)]:
    chip(x, 855, w, label, symbol, "#aa81fa")
bullet(936, "Map high-level actions to robot-specific controllers")
bullet(965, "Execute on real robot (e.g., Go2 / ARX X5)")
bullet(994, "Return execution status and results")

for start, end in [(369,395),(601,627),(817,843)]:
    arrow(882, start, end)
add('<path d="M1473 930H1510Q1543 930 1543 897V196Q1543 164 1510 164H1483" fill="none" stroke="#10213d" stroke-width="4" marker-end="url(#navy)"/>')
rect(1486, 493, 114, 146, "#f8fbff", "#10213d", 14)
text(1543, 528, "Feedback", 20, 700, anchor="middle")
for y, label in [(561,"Update state"),(587,"and memory"),(613,"for next step")]:
    text(1543, y, label, 16, anchor="middle")

for y, name, subtitle, asset, accent, bg, details in [
    (124, "GO2", "MOBILE MANIPULATION PROFILE", "unitree-go2.png", "#2868ed", "go2-bg", ["UNITREE SDK · NATIVE NAV", "D435 · MID360 · ROBOT STATE", "LOCOMOTION · OPTIONAL ARX ARM"]),
    (584, "ARX X5", "STATIONARY MANIPULATION PROFILE", "arx-x5.png", "#00a777", "arx-bg", ["ZENOH · GRASP CONNECTOR", "D435 RGB-D · JOINT / EEF STATE", "ARM · GRIPPER · GRASP / RESET"]),
]:
    add(f'<g id="embodiment-{name.lower().replace(" ", "-")}" aria-label="Embodiment {name}">')
    rect(1630, y, 386, 437, f"url(#{bg})", accent, 20)
    text(1823, y+40, f"EMBODIMENT · {name}", 23, 700, accent, "middle")
    text(1823, y+65, subtitle, 11.5, 700, "#64748b", "middle", 'letter-spacing="1.15"')
    encoded = base64.b64encode((SOURCE / asset).read_bytes()).decode("ascii")
    add(f'<image x="1660" y="{y+78}" width="326" height="228" preserveAspectRatio="xMidYMid meet" href="data:image/png;base64,{encoded}"/>')
    for i, label in enumerate(details):
        rect(1652, y+317+i*37, 342, 30, "#ffffff", accent, 8, 'stroke-opacity=".6"')
        text(1823, y+337+i*37, label, 11.5, 600, anchor="middle")
    add('</g>')

rect(32, 1041, 1984, 49, "#e4ebf3", "#a8bcd2")
text(1024, 1073, "Perceive → Reason (LLM) → Call Tools → Execute on Robot → Feedback  (Closed Loop)", 23, 600, anchor="middle")
text(32, 1115, "GEEK MIND · UNIVERSAL EMBODIMENT AGENT RUNTIME", 11, 600, "#64748b", extra='letter-spacing="1"')
text(2016, 1115, "Hardware imagery: Unitree Robotics · TidyBot++ (CC BY 4.0) · details in ATTRIBUTION.md", 11, color="#64748b", anchor="end")
add('</g></svg>')

output = SOURCE.parent / "geek-mind-architecture.svg"
output.write_text("\n".join(parts) + "\n")
print(f"Wrote {output} ({output.stat().st_size:,} bytes)")
