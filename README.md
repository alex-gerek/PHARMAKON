<p align="center">
  <img src="studio_icon.png" width="130" height="130" alt="Lex Gerek Studio Remaster Logo">
</p>

# LEX GEREK // STUDIO REMASTER DSP
## Universal Studio-Grade Audio Restoration, De-Harshing & Stem Mastering Pipeline

<p align="center">
  <b><a href="#-русская-версия">🇷🇺 Читать на русском</a></b> &nbsp;|&nbsp; 
  <b><a href="#-english-version">🇬🇧 Read in English</a></b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9+-blue.svg?style=flat-square" alt="Python">
  <img src="https://img.shields.io/badge/DSP-SciPy%20SoundFile-red.svg?style=flat-square" alt="DSP">
  <img src="https://img.shields.io/badge/Artist-Lex%20Gerek-black.svg?style=flat-square&logo=youtube" alt="Lex Gerek">
  <img src="https://img.shields.io/badge/True--Peak--0.3%20dBFS-brightgreen.svg?style=flat-square" alt="True Peak">
  <img src="https://img.shields.io/badge/License-MIT-orange.svg?style=flat-square" alt="License">
</p>

---

# 🇷🇺 Русская версия

## 1. Предыстория проекта
Привет, я **Lex Gerek** — электронный продюсер и саунд-архитектор.

Этот проект родился в моих ночных студийных сессиях во время сведения и мастеринга.

Когда работаешь с приглашенными вокалистами и сессионными музыкантами, присылающими дорожки из неподготовленных комнат и с разных микрофонов, неизбежно сталкиваешься с одним и тем же техническим адом: паразитные комнатные резонансы, микрофонная грязь, ядовитый свистящий скрежет на буквах С/Ш ($4.5\text{--}6.5\text{ кГц}$) и мутный размазанный саб-бас, убивающий давление на мощных клубных акустических системах (Funktion-One, L-Acoustics).

Чтобы не тратить драгоценные часы на рутинную зачистку каждого трека, я разработал эту математическую DSP-цепочку как автоматизированный студийный процессор:
- **Запирание баса ниже $120\text{ Гц}$ в строгое монолитное моно** — максимальный панч в грудь и ноль фазовых конфликтов в клубе.
- **Крутой срез инфра-гула ниже $32\text{ Гц}$**, освобождающий полезный динамический запас громкости (*headroom*).
- **Хирургический режекторный фильтр** ядовитых обертонов и сибилянтов на $5\text{ кГц}$ с сохранением яркости и воздуха.
- **Нелинейная плёночная сатурация ($\tanh$)** для склеивания микса и теплого аналогового тела.
- **3D Mid-Side пространственная матрица** для расширения синтов и атмосферы на $+25\%$ при монолитном центре.

### 💡 Потрясающий побочный эффект:
С появлением генеративных нейросетей (Suno, Udio и др.) я пропустил через этот процессор сырые генерации. Оказалось, что студийная математика, созданная для живых записей, абсолютно бесследно стирает цифровой шум квантования, фазовую «кашу» и жестяной ИИ-призвук, превращая сырой материал в плотный, готовый к релизу коммерческий саунд.

---

## 2. Архитектура DSP-обработки

```text
 RAW STEMS (.WAV)
 ├── VOCALS.WAV  ──> [Highpass 85Hz] ──> [5kHz Surgical Notch Filter] ──> [Tape Saturation] ──┐
 ├── BASS.WAV    ──> [Highpass 32Hz] ──> [120Hz Crossover -> True Mono] ──> [Warmth Tanh]   ──┼─> [Master Sum] ─> [True-Peak Limiter -0.3dBFS] ─> STUDIO_REMASTER.WAV
 ├── DRUMS.WAV   ──> [Highpass 28Hz] ──> [Transient Attack Punch Boost] ──> [Soft Clip]     ──┤
 └── OTHER.WAV   ──> [Highpass 115Hz] ──> [Mid-Side Matrix -> +25% Side Width] ───────────────┘
```

---

## 3. Быстрый старт

### Требования
* Python 3.9+
* Зависимости: `pip install -r requirements.txt` (`numpy`, `scipy`, `soundfile`)

### Использование в Windows (в 1 клик через ярлык)
1. Раздели любой трек на стемсы с помощью Demucs:
   ```bash
   python -m demucs.separate -d cuda track.wav
   ```
2. Просто **перетащи папку со стемсами** (`vocals.wav`, `drums.wav`, `bass.wav`, `other.wav`) на ярлык **`Studio Remaster`** на Рабочем столе!
3. Движок мгновенно создаст подпапку `Remaster/`:
   - `vocals_cleaned.wav`
   - `drums_punched.wav`
   - `bass_monofied.wav`
   - `other_widened.wav`
   - **`[TRACK] - STUDIO_REMASTER.wav`** — финальный коммерческий мастер!

### Использование через терминал
```bash
python remaster_engine.py "путь/к/папке_со_стемсами"
```

---

## 4. Обо мне
Я электронный музыкант, саунд-архитектор и аудиовизуальный продюсер, создающий цельную вселенную в стиле нео-нуар техно.

* 🎬 **Смотреть 98-минутный визуальный техно-альбом на YouTube**:  
  [**Lex Gerek — Center of Gravity (Full Mix)**](https://youtu.be/fCYPHCnbq2Y)
* ⚡️ **X / Twitter**: [@LexGerek](https://x.com/LexGerek)
* 💿 **Bandcamp**: [lexgerek.bandcamp.com](https://lexgerek.bandcamp.com)

---

## 5. Лицензия
Проект распространяется с открытым исходным кодом по лицензии [MIT](LICENSE) © 2026 Lex Gerek.

---

# 🇬🇧 English Version

## 1. The Origin Story
Hi, I'm **Lex Gerek** — electronic music producer and sound architect.

This engine was born directly out of my late-night studio mixing and mastering sessions.

When tracking and mixing with guest vocalists and demanding session musicians who record in varied, imperfect acoustic environments, I constantly faced the same engineering nightmare: mic bleed, nasty room flutter resonances, piercing metallic sibilance on consonants ($4.5\text{--}6.5\text{ kHz}$), and muddy, out-of-phase sub-bass that drains punch and destroys club sound systems (like *Funktion-One* or *L-Acoustics*).

Instead of wasting hours manually repairing the same audio flaws across dozens of stem tracks, I engineered this mathematical DSP (Digital Signal Processing) pipeline as an automated studio channel strip:
- **Locking sub-bass below $120\text{ Hz}$ into pure, focused mono** (maximum headroom, zero phase issues on big subs).
- **Sub-harmonic cut below $32\text{ Hz}$** to remove invisible speaker-shaking mud and restore mix punch.
- **Surgical dynamic notch filtering** to tame harsh $5\text{ kHz}$ sibilance and brittle overtones without dulling the vocal presence.
- **Non-linear analog tape saturation modeling ($\tanh$)** for rich harmonic warmth and cohesion.
- **3D Mid-Side spatial matrix** expanding side elements by $+25\%$ while keeping the kick and bass dead center.

### 💡 The Unexpected "Side Effect":
As generative neural audio tools (Suno, Udio, and AI synthesizers) entered the scene, I tested this exact DSP chain on raw generated stems. The result was staggering: the same mathematical filters that tamed harsh vocalists effortlessly eliminated digital quantization grain, robotic phase smearing, and "AI soup" — instantly transforming raw, flat stems into a warm, punchy, commercial-grade master.

---

## 2. DSP Processing Architecture

```text
 RAW STEMS (.WAV)
 ├── VOCALS.WAV  ──> [Highpass 85Hz] ──> [5kHz Surgical Notch Filter] ──> [Tape Saturation] ──┐
 ├── BASS.WAV    ──> [Highpass 32Hz] ──> [120Hz Crossover -> True Mono] ──> [Warmth Tanh]   ──┼─> [Master Sum] ─> [True-Peak Limiter -0.3dBFS] ─> STUDIO_REMASTER.WAV
 ├── DRUMS.WAV   ──> [Highpass 28Hz] ──> [Transient Attack Punch Boost] ──> [Soft Clip]     ──┤
 └── OTHER.WAV   ──> [Highpass 115Hz] ──> [Mid-Side Matrix -> +25% Side Width] ───────────────┘
```

---

## 3. Quick Start

### Requirements
* Python 3.9+
* Dependencies: `pip install -r requirements.txt` (`numpy`, `scipy`, `soundfile`)

### Windows 1-Click Drag & Drop
1. Split any track into stems using Demucs:
   ```bash
   python -m demucs.separate -d cuda track.wav
   ```
2. Simply **drag and drop** the folder containing `vocals.wav`, `drums.wav`, `bass.wav`, `other.wav` onto the **`Studio Remaster`** desktop shortcut!
3. The engine creates a `Remaster/` subfolder with:
   - `vocals_cleaned.wav`
   - `drums_punched.wav`
   - `bass_monofied.wav`
   - `other_widened.wav`
   - **`[TRACK] - STUDIO_REMASTER.wav`** (Full commercial master!)

### Command Line Usage
```bash
python remaster_engine.py "path/to/stems_folder"
```

---

## 4. About Lex Gerek
I am an electronic music producer, sound architect, and audiovisual artist creating ongoing neo-noir techno universes.

* 🎬 **Watch the 98-Minute Neo-Noir Techno Visual Album on YouTube**:  
  [**Lex Gerek — Center of Gravity (Full Mix)**](https://youtu.be/fCYPHCnbq2Y)
* ⚡️ **X / Twitter**: [@LexGerek](https://x.com/LexGerek)
* 💿 **Bandcamp**: [lexgerek.bandcamp.com](https://lexgerek.bandcamp.com)

---

## 5. License
This project is open-source under the [MIT License](LICENSE) © 2026 Lex Gerek. Free for artists, producers, and developers worldwide.
