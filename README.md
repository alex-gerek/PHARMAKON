<p align="center">
  <img src="gui/static/studio_icon.png" width="130" height="130" alt="PHARMAKON Logo">
</p>

# PHARMAKON 2.0 PRO
## Studio-Grade Audio Antidote, AI De-Harshing & Mastering Console
### Created by Lex Gerek // Abbey Road 1974 × Blade Runner 2049

<p align="center">
  <a href="https://github.com/alex-gerek/PHARMAKON/archive/refs/heads/master.zip">
    <img src="https://img.shields.io/badge/📥%20Скачать%20ZIP%20%7C%20Download%20ZIP%20(Direct%20Link)-238636?style=for-the-badge&logo=github&logoColor=white" alt="Download ZIP">
  </a>
</p>

<p align="center">
  <b><a href="#-русская-версия">🇷🇺 Читать руководство на русском</a></b> &nbsp;|&nbsp; 
  <b><a href="#-english-version">🇬🇧 Read User Guide in English</a></b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Version-2.0%20PRO-emerald.svg?style=flat-square&color=10b981" alt="Version 2.0 PRO">
  <img src="https://img.shields.io/badge/DSP-Dynamic%20Ducker%20%2B%20Exciter-blue.svg?style=flat-square" alt="DSP Core">
  <img src="https://img.shields.io/badge/Oscilloscope-60%20FPS%20CRT%20%2B%20Phase%20Scope-brightgreen.svg?style=flat-square" alt="CRT Scope">
  <img src="https://img.shields.io/badge/Limiter-4x%20True--Peak%20(-0.3%20dBFS)-amber.svg?style=flat-square&color=f59e0b" alt="True Peak">
  <img src="https://img.shields.io/badge/Monitoring-A%20%2F%20B%20%2F%20Δ%20Delta-purple.svg?style=flat-square" alt="Monitoring">
  <img src="https://img.shields.io/badge/Loudness-ITU--R%20BS.1770--4%20LUFS-cyan.svg?style=flat-square" alt="LUFS">
  <img src="https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-0078d7?style=flat-square" alt="Platform">
  <img src="https://img.shields.io/badge/Author-Lex%20Gerek-black.svg?style=flat-square&logo=youtube" alt="Lex Gerek">
  <img src="https://img.shields.io/badge/License-MIT-orange.svg?style=flat-square" alt="License">
</p>

---

# 🇷🇺 Русская версия

## 1. Зачем создан PHARMAKON: Анатомия «Нейросетевого Яда»

> **Pharmakon** *(др.-греч. φάρμακον)* — античный философский концепт: вещество, являющееся одновременно **ядом**, **лекарством** и **противоядием**.

Появление генеративных нейросетей (**Suno v3/v3.5/v4**, **Udio 1.5**, Stable Audio) навсегда изменило создание музыки. Но каждый продюсер, композитор и звукорежиссёр сталкивается с суровой реальностью: **прямо из коробки нейросетевые треки звучат грязно, резко и фазово-разрушительно**.

### Главные родовые травмы нейро-аудио:
1. **Ядовитый металлический свист (AI Harshness / 4.5–7 кГц):**  
   Нейросетевые вокодеры генерируют неестественные узкополосные резонансные пики на согласных «С/Ш», тарелках и верхах вокала. Звук режет слух и вызывает мгновенную слуховую усталость («стеклянный песок»).
2. **Ампутация спектра выше 15.5 кГц:**  
   Большинство генеративных моделей обучаются со сжатием спектра (32–44.1 кГц со спадом выше 15–16 кГц). Обычный эквалайзер не может вернуть «воздух», потому что там **физически нет информации** — он лишь поднимает шипение квантования.
3. **Размазанный по фазе суб-бас (Sub Mud):**  
   Низкие частоты (20–120 Гц) в AI-треках часто размазаны по стереопанораме в противофазе. При воспроизведении на моно-акустике (смартфон, клубный сабвуфер Funktion-One) бочка и бас схлопываются и исчезают.
4. **Удушенные транзиенты и фазовый конфликт бочки с басом:**  
   Ударные теряют атаку и панч, а полуволны саб-баса и бочки гасят друг друга при наложении.
5. **Межсэмпловый клиппинг (Inter-Sample Peaks / ISP):**  
   AI-сервисы нормализуют аудио впритык к 0 dBFS. При цифро-аналоговом преобразовании (ЦАП) и кодировании стримингами (Spotify, Apple Music, YouTube) возникают искажения свыше +1.5 dBFS.

**PHARMAKON 2.0 PRO — это профессиональная аналого-цифровая реанимационная станция.**  
Он не просто сглаживает звук «мыльными» фильтрами, а хирургически вырезает нейросетевой яд, восстанавливает утраченную акустическую материю и склеивает трек аналоговой лентой по золотым стандартам звукозаписи **Abbey Road 1974**.

---

## 2. Ключевые инновации ядра DSP (Что под капотом)

### 🔬 1. Автоматический детектор резонансов (Auto Spectral Antidote)
Движок производит спектральный анализ плотности мощности (Welch PSD FFT) и алгоритмически через `scipy.signal.find_peaks` локализует точную частоту паразитного AI-свиста (например, 5307.9 Гц с превышением +9.1 dB) и автоматически настраивает добротность $Q$.

### ⚡ 2. Динамический De-Harshing Ducker (Анти-AI)
В отличие от примитивных статичных фильтров, которые вырезают полосу на протяжении всего трека и делают вокал глухим («ватным»), **PHARMAKON использует адаптивный динамический дакер с баллистическими огибающими** (5 мс атака, 45 мс релиз). Фильтр утапливает частоту только в те доли секунды, когда ядовитый резонанс превышает психоакустический порог.

### 💨 3. Harmonic Air Exciter (>16 кГц Silk Synthesizer)
Уникальный психоакустический синтезатор гармоник. Он извлекает полезный сигнал из донорной полосы 8–13 кГц, генерирует богатые четные и нечетные обертона через нелинейное асимметричное насыщение, отсекает всё лишнее фильтром выше 15.5 кГц и вдувает в микс чистейший шелковистый воздух 16–22 кГц.

### 🎯 4. Low-End Phase Alignment (Sub Sync для стэмов)
При мастеринге стэмов (Drums + Bass + Vocals + Other) модуль вычисляет кросс-корреляцию между бочкой и басом в диапазоне 30–100 Гц. Микро-сдвиг фазы на доли миллисекунды гарантирует, что пик бочки и гребень басовой волны бьют строго синфазно.

### 🛡 5. 4x Polyphase True-Peak Limiter & OOM Streaming Chunking
Лимитер с 4-кратным полифазным оверсэмплингом (`scipy.signal.resample_poly`), lookahead-буфером 1.5 мс и мягким релизом гарантирует потолок **-0.3 dBFS True-Peak** без единого межсэмплового клипа. Потоковый чанкинг с косинусным кроссфейдом защищает от переполнения оперативной памяти (OOM) даже на 2-часовых сетах.

### 📊 6. Измеритель громкости по стандарту ITU-R BS.1770-4 / EBU R128 LUFS
Честный расчёт интегральной громкости (Integrated LUFS) с K-weighting фильтрами (High-Shelf + High-Pass) и двойным стробированием (-70 LKFS / -10 dB Relative Gate).

---

## 3. Режимы мониторинга: A / B / Δ (Delta Residue)

В блоке мониторинга доступны три режима сквозного прослушивания (с мгновенным переключением без щелчков):

| Кнопка | Клавиша | Режим | Назначение |
|---|:---:|---|---|
| **[A] RAW** | `A` | Исходный трек | Необработанный оригинальный AI-файл с цифровым песком и клиппингом (рубиновый CRT). |
| **[B] MASTER** | `B` | Мастер PHARMAKON | Готовый отмастеренный результат: плотный аналоговый низ, шелковистый верх (изумрудный CRT). |
| **[Δ] DELTA** | `D` | Режим вычитания | **Прослушивание исключительно удалённого яда** ($\text{Raw} - \text{Master}$ с инверсией фазы и бустом $+6\text{ dB}$). |

> **Секрет звукорежиссёра:**  
> Переключитесь в режим **`[Δ] DELTA`** во время воспроизведения. Если вы слышите только противный металлический свист, щелчки клиппинга и грязный инфразвуковой гул, а тело голоса и гармония музыки не пробиваются — **мастеринг настроен ювелирно**!

---

## 4. Визуализация и CRT Осциллографы

- **⚡ DUAL BEAMS (Клавиша `1`):** Два параллельных кинескопа 60 FPS на зеленом фосфоре P1 с независимой отрисовкой RAW и MASTER.
- **📺 SINGLE SCOPE (Клавиша `2`):** Сфокусированный кинескоп крупного плана.
- **📊 RTA SPECTRUM (Клавиша `3`):** Анализатор спектра в реальном времени с сеткой от 20 Гц до 20 кГц и dB-шкалой.
- **🎯 DSP CURVES (Клавиша `4`):** Кривые частотной характеристики фильтрации, режекции и экситера.
- **🌊 WAVEFORM (Клавиша `5`):** Обзорная форма волны с таймкодами.
- **🧭 PHASE SCOPE (Клавиша `6`):** **Векторный гониометр Лиссажу** стереобазы ($X = \text{Side}$, $Y = -\text{Mid}$) с круговой шкалой радара 45° и измерителем фазовой корреляции от **-1.0 (противофаза)** через **0.0 (широкое стерео)** до **+1.0 (моно-совместимость)**.

---

## 5. Хирургический режим (Surgical Punch-In)

Если в треке испорчен только один фрагмент (например, скрипучий вокальный фальцет на 45-й секунде):
1. Выделите диапазон прямо на вейвформе мышью.
2. Зафиксируются лазерные калиперы `IN` и `OUT` (или нажмите `+3s`, `+5s`).
3. При рендере движок применит бесшовный **35-мс raised-cosine кроссфейд**.
4. **100% аудио за пределами калиперов останется нетронутым байт-в-байт!**

---

## 6. Пресеты AI-профилей

| Профиль | Описание | Параметры по умолчанию |
|---|---|---|
| **⚡ AUTO SCAN** | Автоматический спектральный сканер резонансов Welch PSD | Интеллектуальный поиск пика, адаптивный Q |
| **🟡 SUNO v3.5/v4** | Детокс от металлического свиста вокодера, синтез верха | Notch: 5200 Гц, Exciter: 18%, Sub: 34 Гц |
| **🟣 UDIO 1.5** | Сглаживание стеклянной резкости, 3D M/S расширение | Notch: 6100 Гц, Exciter: 14%, Tape: 1.06x |
| **🔴 CLUB PUNCH** | Максимальная плотность бочки и саб-баса, EDM-панчер | Mono < 140 Гц, Drum Punch: +35%, -0.1 dBFS |
| **⚪ AUDIOPHILE** | Прозрачная аналоговая коррекция для акустики и джаза | Минимальная окраска, True-Peak: -0.5 dBFS |

---

## 7. Сертификат мастеринга и сохранение файлов

1. **📄 OPEN FULL REPORT:** Открывает автономный интерактивный диагностический отчёт в основном браузере (HTML с векторными SVG-спектрограммами, таблицей метрик LUFS/True-Peak/RMS и серийным номером).
2. **📸 EXPORT PNG CARD:** Генерирует графическую карточку студийного паспорта качества с вызовом нативного диалога Windows «Сохранить как...» в любую выбранную папку.
3. **⬇ DOWNLOAD MASTER (.WAV):** Скачивание 24-битного lossless мастер-файла с выбором пути сохранения.

---

## 8. 🚀 Быстрый запуск

### 1. Клонирование репозитория
```bash
git clone https://github.com/alex-gerek/PHARMAKON.git
cd PHARMAKON
```

### 2. Установка зависимостей
Требуется Python 3.9+:
```bash
pip install -r requirements.txt
```

### 3. Запуск студийной консоли
Дважды кликните по:
```text
Pharmakon_GUI.bat
```
*(Или запустите в терминале: `python gui/server.py`)*

Консоль откроется по адресу: 👉 **`http://127.0.0.1:7860`**

### Горячие клавиши (Hotkeys):
* `Space` — Воспроизведение / Пауза
* `A` — Мониторинг RAW
* `B` — Мониторинг MASTER
* `D` — Мониторинг DELTA (вырезанный яд)
* `1` ... `6` — Переключение экранов (Dual, Single, RTA, DSP, Wave, Phase Scope)
* `L` — Зацикливание 5-секундного отрезка (Loop 5s)
* `Escape` — Сброс хирургического региона

---

# 🇬🇧 English Version

## 1. Why PHARMAKON: The Anatomy of "AI Poison"

> **Pharmakon** *(Ancient Greek: φάρμακον)* — an ancient philosophical paradox denoting simultaneously **poison**, **remedy**, and **antidote**.

Generative audio models (**Suno v3/v3.5/v4**, **Udio 1.5**, Stable Audio) have revolutionized music creation. Yet producers and engineers face an inescapable reality: **raw AI audio suffers from severe systemic sonic defects**.

### Common AI Audio Pathologies:
1. **Metallic AI Harshness (4.5–7 kHz):** Neural vocoders create synthetic resonant spikes on sibilants and cymbals, causing acute listener fatigue.
2. **High-Frequency Cutoff (>15.5 kHz):** Neural codecs truncate audio above 15.5 kHz. Static high-shelf boosts fail because there is no acoustic information to boost—only quantization hiss.
3. **Phase-Smudged Sub-Bass:** Low frequencies (20–120 Hz) are smeared out-of-phase across stereo, causing devastating phase cancellation in mono and club sound systems.
4. **Transient Smearing & Kick-Bass Phase Clashing:** Attack transients are blunted, and drum kicks cancel out bass wave crests.
5. **Inter-Sample Peak (ISP) Clipping:** Files rendered near 0 dBFS cause severe clipping on DAC reconstruction and streaming transcoding (Spotify, Apple Music).

**PHARMAKON 2.0 PRO is a dedicated analog-digital resuscitation console.**  
Fusing **Abbey Road 1974** analog tape warmth with **Blade Runner 2049** telemetry, it surgically extracts digital venom and restores lost acoustic silk.

---

## 2. DSP Core Innovations

- **Auto Spectral Antidote:** Welch PSD FFT scanner detects narrow AI resonance whistles with adaptive Q-factor.
- **Dynamic De-Harshing Ducker:** Envelope-followed notch (5ms attack, 45ms release) that attenuates frequencies only when harshness exceeds threshold, preserving natural vocal presence.
- **Harmonic Air Exciter (>16 kHz):** Synthesizes authentic silky air by generating 2nd and 3rd harmonics from the 8–13 kHz donor band and high-passing above 15.5 kHz.
- **Low-End Phase Alignment (Sub Sync):** Micro-aligns drum and bass stems via cross-correlation in the 30–100 Hz band to lock sub-phase.
- **4x Polyphase True-Peak Limiter:** Guarantees -0.3 dBFS ceiling with zero inter-sample peaks and chunked streaming protection against OOM memory errors on long tracks.
- **ITU-R BS.1770-4 LUFS Metering:** Integrated loudness measurements with K-weighting and relative gating.

---

## 3. Monitoring Bay: A / B / Δ (Delta Residue)

- **[A] RAW (Key `A`):** Original untreated AI input.
- **[B] MASTER (Key `B`):** Polished, glued analog master.
- **[Δ] DELTA (Key `D`):** Phase-inverted real-time difference ($\text{Raw} - \text{Master}$) with $+6\text{ dB}$ boost. **Audition exclusively the extracted AI poison!**

---

## 4. Visualizers & CRT Scopes

- **Dual 60 FPS CRT Scopes:** Real-time dual-beam phosphor visualization.
- **Phase Scope & Correlation Meter (Key `6`):** 45° rotated Lissajous goniometer ($X = \text{Side}$, $Y = -\text{Mid}$) with reticle grid and $[-1.0 \dots +1.0]$ phase correlation needle.
- **RTA Spectrum, DSP Curves & Waveform Scopes.**

---

## 5. Surgical Punch-In Caliper

- Drag directly on the waveform to isolate a damaged segment.
- 35ms raised-cosine equal-power crossfade seamlessly splices the processed fix.
- **100% of audio outside the calipers remains byte-for-byte untouched.**

---

## 6. Studio Mastering Certificate & Export

- **Interactive Diagnostic HTML Report:** Complete spectral analysis, LUFS readings, and serial number.
- **Save As File Dialogs:** Direct destination folder selection for Master WAV files and PNG Certificate cards via modern File System Access API and native desktop dialogs.

---

## 7. Author & Credits
Created with acoustic passion by **Lex Gerek**  
- Sound Architect, Mastering Engineer & Producer  
- YouTube / Portfolio: [Lex Gerek](https://www.youtube.com/@alex-gerek)  
- GitHub: [@alex-gerek](https://github.com/alex-gerek)

## 8. License
Released under the **MIT License**. Free for personal, commercial, and studio use.
