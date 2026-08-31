<div align="center">

# 🍪 Cookie Run Classic Bot

**A hands-free Cookie Run Classic farming bot that runs entirely in the background — no need to keep the emulator window focused.**

<img src="https://img.shields.io/badge/Python-3.10-blue?style=for-the-badge&logo=python" />
<img src="https://img.shields.io/badge/UI-PyQt6-orange?style=for-the-badge" />
<img src="https://img.shields.io/badge/Emulators-LDPlayer%20%7C%20MuMu%20%7C%20Nox-brightgreen?style=for-the-badge" />
<img src="https://img.shields.io/badge/Platform-Windows-0078D6?style=for-the-badge&logo=windows" />

<br/>

*Automated loop · Vision-driven · Human-like input · Zero setup*

</div>

---

## ✨ Features

<table>
  <tr>
    <td width="33%">
      <h3>🖱️ Background Click</h3>
      <p>Clicks are sent directly to the emulator via Win32 <code>PostMessage</code>. Keep working or browsing while it farms.</p>
    </td>
    <td width="33%">
      <h3>📸 Hybrid Vision</h3>
      <p>Combines OpenCV template matching (fast) with Tesseract OCR (accurate) to detect buttons, buffs, and game state.</p>
    </td>
    <td width="33%">
      <h3>🔄 Full Auto Loop</h3>
      <p>Lobby → Prep → Gameplay → Results, then back again. Claims relics, buys boosts, handles level-ups automatically.</p>
    </td>
  </tr>
  <tr>
    <td>
      <h3>⚙️ Self-Healing Setup</h3>
      <p>Startup splash checks every dependency and auto-installs missing ones (including Tesseract via winget) before launch.</p>
    </td>
    <td>
      <h3>🎯 Human-like Input</h3>
      <p>Randomized jitter, tap delay, and hold time make every click feel natural while staying precise on target.</p>
    </td>
    <td>
      <h3>📊 Live Dashboard</h3>
      <p>Real-time emulator preview, activity log with filters, run counter, session timer, and a DEBUG toggle.</p>
    </td>
  </tr>
</table>

---

## 🧭 How It Works

```
┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│ 📸 Capture │→│ 🧠 Detect │→│ 🖱️ Act    │→│ 🔄 Repeat │
│ PrintWindow│ │ template │ │ background │ │ next stage │
│   (35ms)   │ │  + OCR   │ │    click   │ │            │
└──────────┘   └──────────┘   └──────────┘   └──────────┘
```

1. **Capture** — Screenshot the emulator's render window with `PrintWindow`.
2. **Detect** — Identify the current stage (lobby / prep / gameplay / results) using template matching or OCR.
3. **Act** — Click the right button with human-like jitter via `PostMessage` — no window focus required.
4. **Repeat** — Loop every 0.3s through the full farm cycle.

---

## 🚀 Quick Start

### 1. Install requirements

```bash
pip install -r requirements.txt
```

> The bot uses `pywin32` and `pytesseract` on top of the usual ML stack. If they are missing, the startup **splash screen will install them for you automatically**.

### 2. Install Tesseract OCR (optional but recommended)

```bash
winget install --id UB-Mannheim.TesseractOCR -e
```

Without it the bot still runs, but text detection (buff names, Jump/Slide labels) is disabled.

### 3. Launch

```bash
python main.pyw
```

Wait for the splash to verify everything, then press **Start** on the dashboard.

---

## ⚙️ Configuration

Settings are stored in `config.json` (auto-created next to `main.pyw`):

| Setting | Default | Description |
|---|---|---|
| `emulator` | `LDPlayer` | Emulator type to auto-detect (`LDPlayer`, `MuMu`, `Nox`, `BlueStacks`) |
| `farm_mode` | `farm_box` | See [Farm Modes](#-farm-modes) |
| `jump_interval` | `0.40` | Min seconds between jumps during gameplay |
| `click_delay_min` | `0.05` | Random pre-click delay — minimum (s) |
| `click_delay_max` | `0.15` | Random pre-click delay — maximum (s) |
| `click_hold` | `0.05` | Hold duration of each tap (s) |
| `click_jitter_pct` | `0.5` | Jitter radius in percent of viewport (±%) |
| `click_jitter_px` | `1` | Extra jitter radius in pixels (±px) |
| `target_buff` | `Double Coins` | Buff to wait for in prep before starting |
| `buff_list` | — | Selectable buff list shown in the settings UI |

## 🐾 Farm Modes

| Mode | Jumps? | Best for |
|---|---|---|
| `farm_gold` | ✅ Yes | Coins and general farming |
| `farm_exp` | ✅ Yes | Experience points |
| `farm_box` | ❌ No | Safe grinding on the no-jump track |

## 📐 Coordinates

All click points are stored as **percentages** `[name, x%, y%, w%, h%]`, so they scale to any window size automatically. Edit them from the **Coordinates** page in the app — each point supports template or OCR detection.

```python
['Play Button', 74.3, 89.6, 14.0, 8.0]   # name, x%, y%, width%, height%
```

---

## 📁 Project Structure

```
cookie-run-bot/
├── main.pyw               # Entry point (splash → main window)
├── requirements.txt
├── config.json            # User settings (gitignored)
├── core/                  # Window system + dependency checker
├── emulator/              # Viewport finder, background tap, screenshot
├── game/                  # State machine + stage handlers (lobby/prep/gameplay/results)
├── vision/                # Template matching + OCR engine + templates
└── ui/                    # PyQt6 dashboard, settings, coordinates, splash
```

---

## 🛠️ Troubleshooting

<details>
<summary><b>Emulator not detected</b></summary>

Make sure the emulator is running before pressing Start. Supported render windows: LDPlayer `RenderWindow`, MuMu `subWin`. The bot auto-retries every 5 seconds.
</details>

<details>
<summary><b>Buttons not recognized / wrong taps</b></summary>

Capture a fresh screenshot from the Coordinates page and update the point position. Lower the detection threshold if the template no longer matches your in-game resolution.
</details>

<details>
<summary><b>Black or frozen screen when minimized</b></summary>

Some emulators pause rendering when hidden. Enable the emulator's *"render when minimized"* option, or keep the window visible but unfocused — background clicks still work.
</details>

<details>
<summary><b>OCR not reading buff names</b></summary>

Install Tesseract OCR (see Quick Start) and confirm `pytesseract` is installed. Detection for `Jump`, `Slide`, and `SelectFo` relies on OCR.
</details>

<details>
<summary><b>Activity log looks empty</b></summary>

The **DEBUG** toggle on the dashboard hides `info`-level messages by default. Switch it to **ON** to see detailed per-tap logs.
</details>

---

<div align="center">

**Made with 🍪 for Cookie Run Classic**

[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

</div>
