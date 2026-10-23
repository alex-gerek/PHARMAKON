# LEX GEREK // STUDIO REMASTER DSP ENGINE
> **Universal Studio-Grade Audio Restoration, De-Harshing & Stem Mastering Pipeline**  
> *Универсальный студийный DSP-процессор ремастеринга, очистки звука и сведения стемсов*

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![DSP: SciPy](https://img.shields.io/badge/DSP-SciPy%20SoundFile-red.svg)](https://scipy.org/)
[![Artist: Lex Gerek](https://img.shields.io/badge/Producer-Lex%20Gerek-black.svg?style=flat&logo=youtube)](https://youtu.be/fCYPHCnbq2Y)

---

## 🌐 The Origin Story / Предыстория проекта

### [EN] English
This project was born out of late-night mixing sessions in producer **Lex Gerek's** studio. 

When working with diverse guest vocalists, remote session musicians, and varied tracking environments, every audio engineer faces the same nightmare: microphone bleed, room resonances, harsh sibilance on consonants ($4.5\text{--}6.5\text{ kHz}$), and muddy sub-bass that destroys clarity and causes severe phase cancellation on high-end club sound systems (like *Funktion-One* or *L-Acoustics*).

Lex developed this mathematical DSP (Digital Signal Processing) pipeline as an automated studio channel strip to cure these chronic production headaches in seconds:
- Locking low frequencies below $120\text{ Hz}$ into rock-solid mono
- Carving out infrasonic rumble ($<32\text{ Hz}$) that wastes dynamic headroom
- Surgical notch filtering of harsh metallic sibilance
- Warm analog tape saturation modeling ($\tanh$)
- 3D Mid-Side spatial stereo widening

**The Breakthrough "Side Effect":**  
As generative neural audio tools (Suno, Udio, neural synthesizers) emerged, we discovered that this exact mathematical filter chain effortlessly obliterates modern digital quantization noise, phase smearing, and "AI soup" — transforming raw generated audio stems into club-ready, punchy commercial-grade masters.

---

### [RU] Русский
Этот проект родился в ночных студийных сессиях продюсера **Lex Gerek**.

При сведении треков с сессионными вокалистами и музыкантами, присылающими дорожки из разных комнат и с разных микрофонов, звукорежиссёр всегда сталкивается с одним и тем же адом: паразитные комнатные резонансы, микрофонная грязь, ядовитый свист на буквах С/Ш ($4.5\text{--}6.5\text{ кГц}$) и мутный бас, который размывается по стерео и убивает отдачу клубных сабвуферов.

Лекс создал эту математическую DSP-цепочку как автоматический студийный процессор, решающий главные боли сведения в один клик:
- Запирание саб-баса ниже $120\text{ Гц}$ в строгое монолитное моно
- Срез инфра-гула ниже $32\text{ Гц}$, пожирающего громкость микса
- Хирургическое удаление жестяных резонансов
- Нелинейная плёночная сатурация теплых гармоник ($\tanh$)
- 3D Mid-Side расширение панорамы атмосферы и синтов на $+25\%$

**Потрясающий побочный эффект:**  
С появлением генеративных нейросетей выяснилось, что эта студийная аналоговая цепочка абсолютно бесследно стирает в пыль любые современные цифровые ИИ-артефакты, фазовый шум и металлическую «кашу», превращая любой сырой материал в плотный коммерческий мастер!

---

## ⚡️ DSP Processing Architecture / Архитектура обработки

```
 RAW STEMS (.WAV)
 ├── VOCALS.WAV  ──> [Highpass 85Hz] ──> [5kHz Surgical Notch Filter] ──> [Tape Saturation] ──┐
 ├── BASS.WAV    ──> [Highpass 32Hz] ──> [120Hz Crossover -> True Mono] ──> [Warmth Tanh]   ──┼─> [Master Sum] ─> [True-Peak Limiter -0.3dBFS] ─> STUDIO_REMASTER.WAV
 ├── DRUMS.WAV   ──> [Highpass 28Hz] ──> [Transient Attack Punch Boost] ──> [Soft Clip]     ──┤
 └── OTHER.WAV   ──> [Highpass 115Hz] ──> [Mid-Side Matrix -> +25% Side Width] ───────────────┘
```

---

## 🚀 Quick Start / Быстрый старт

### 1. Requirements / Требования
- Python 3.9+
- `pip install -r requirements.txt` (only `numpy`, `scipy`, `soundfile`)

### 2. Usage (Windows Drag & Drop / В один клик)
1. Split any track into stems using Demucs:
   ```bash
   python -m demucs.separate -d cuda track.wav
   ```
2. Simply **drag and drop** the folder containing `vocals.wav`, `drums.wav`, `bass.wav`, `other.wav` onto **`Studio Remaster.bat`**!
3. The engine creates a `Remaster/` subfolder with:
   - `vocals_cleaned.wav`
   - `drums_punched.wav`
   - `bass_monofied.wav`
   - `other_widened.wav`
   - **`[TRACK] - STUDIO_REMASTER.wav`** (Full commercial master!)

### 3. Usage via Terminal / Через командную строку
```bash
python remaster_engine.py "path/to/stems_folder"
```

---

## 👤 About Lex Gerek / Об авторе

**Lex Gerek** is an electronic music producer, sound architect, and audiovisual artist creating ongoing neo-noir techno universes.

- 🎬 **Watch the 98-Minute Neo-Noir Techno Visual Album on YouTube**:  
  [**Lex Gerek — Center of Gravity (Full Mix)**](https://youtu.be/fCYPHCnbq2Y)
- ⚡️ **X / Twitter**: [@LexGerek](https://x.com/LexGerek)
- 💿 **Bandcamp**: [lexgerek.bandcamp.com](https://lexgerek.bandcamp.com)

---

## 📄 License
This project is open-source under the [MIT License](LICENSE) © 2026 Lex Gerek. Free for artists, producers, and developers worldwide.
