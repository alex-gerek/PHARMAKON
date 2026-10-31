# Физика аналоговой ленты: мягкий клиппинг, асимметричный tanh и подавление цифрового скрежета
**Автор:** Lex Gerek (Sound Architect / Engineer)  
**Проект:** PHARMAKON 2.0 Studio Console  
**Графическое доказательство:** `Waveform_Proof_HardClip_vs_Tanh.png`  
**Код реализации:** `remaster_engine.py` (`analog_tape_saturation`)

---

## Русская версия

### 1. Метафора: Бетонный потолок против аналогового батута

Представьте звуковую волну как прыгуна на батуте. В тихих куплетах прыжки спокойны. Но в плотном припеве с мощной бочкой и гитарами амплитуда устремляется в критическую зону.

Что происходит на абсолютном пике громкости?

#### Цифровой жесткий срез (Hard Clipping) — Бетонный потолок:
В цифровом аудио есть непреодолимый порог — 0 dBFS. Когда не отмастеренные транзиенты ИИ-генераторов (Suno, Udio) превышают этот порог, цифровой процессор просто отсекает верхушки дискретных сэмплов по горизонтали.

Когда эти срезанные сэмплы поступают на ЦАП смартфона или звуковой карты, восстанавливающий sinc-фильтр пытается сгладить ступенчатую функцию. Это порождает:
1. Вылет межсэмпловых пиков (Inter-Sample Peaks) до $+1.5...+3.0\text{ dBFS}$ в аналоговом тракте.
2. Массивный веер нечетных гармоник, которые отражаются от частоты Найквиста обратно в слышимый спектр (алиасинг). Для уха это звучит как звон разбитого стекла, металлический скрежет и мгновенная слуховая усталость.

#### Аналоговая лента и транзисторная сатурация — Мягкий батут:
В классических студийных аппаратах (катушечные магнитофоны Studer A800, консоли Neve и Ampex 440) жесткого обрыва не было. При приближении к пределу уровень сигнала плавно компрессируется и мягко скругляется в гладкий купол.

---

### 2. Математика гармоник: почему симметричный `tanh` не дает 2-й гармоники

В среде начинающих разработчиков бытует миф: *«Просто пропусти аудио через `np.tanh` — и получишь теплоту ленты со 2-й и 3-ей гармониками»*.

С точки зрения высшей математики это грубая ошибка:
* Функция гиперболического тангенса является **строго нечетной**:
  $$\tanh(-x) = -\tanh(x)$$
* Симметричный нечетный вейвшейпер математически **не способен сгенерировать ни одной четной гармоники** (ни 2-й, ни 4-й). На выходе чистой синусоиды будут исключительно нечетные гармоники ($3\omega, 5\omega, 7\omega \dots$).
* Нечетные гармоники (особенно 3-я) дают плотность, напор и динамическую «склейку», но ту самую бархатную лампово-трансформаторную «теплоту» обеспечивает **четная 2-я гармоника**.

#### Откуда берется 2-я гармоника на реальной ленте?
В физическом магнитофоне 2-я гармоника рождается исключительно за счет **асимметрии**: небольшого постоянного смещения тока подмагничивания (bias current) и нелинейности входных трансформаторов.

#### Инженерное решение PHARMAKON 2.0:
Чтобы вдохнуть в математику живую 2-ю гармонику, мы ввели в передаточную функцию асимметричный сдвиг (Asymmetric Bias):
$$y = \left(\tanh(x \cdot \text{Drive} + \text{Bias}) - \tanh(\text{Bias})\right) \cdot \text{Ceiling}$$
Вычитание $\tanh(\text{Bias})$ начисто компенсирует постоянную составляющую (DC offset), а наведенная асимметрия насыщения обогащает спектр и благородной 3-й, и теплой 2-й гармониками!

---

### 3. Опасность алиасинга и оверсэмплинг

Разложение $\tanh(x)$ в бесконечный ряд Тейлора:
$$\tanh(x) = x - \frac{x^3}{3} + \frac{2x^5}{15} - \frac{17x^7}{315} + \dots$$
Если применить `np.tanh` «в одну строчку» на стандартной частоте дискретизации 44.1/48 кГц, высшие гармоники ярких тарелок и гитар неизбежно улетят выше Найквиста и зеркально отразятся вниз в виде цифровой грязи.

Поэтому в ядре PHARMAKON сатуратор `analog_tape_saturation` работает строго с **полифазным оверсэмплингом (`resample_poly`)**:
1. Сигнал апсемплится в расширенный частотный домен.
2. Нелинейность формирует гармоники без риска отражения от Найквиста.
3. Полифазный фильтр срезает высшие гармоники и чисто возвращает аудио в 1X.

---

### 4. Частотная физика ленты: Pre-Emphasis (Tape HF Softening)

В реальных магнитофонах Studer и Ampex по стандартам NAB/IEC перед записью на ленту верха принудительно задираются, а при воспроизведении — зеркально опускаются.  
Из-за этого высокочастотные транзиенты (тарелки, сибилянты) насыщаются и мягко компрессируются **первыми** (эффект Tape Softening), а энергоемкий бас не превращается в интермодуляционную кашу.

В модуле `analog_tape_saturation` мы внедрили ту же физику:
- Мягкий пре-фильтр верхних частот (выше 3.5 кГц) направляет транзиенты в зону мягкого насыщения.
- В результате тарелки и шипящие вокала в ИИ-треках мгновенно теряют свой ядовитый металлический звон, приобретая плотный студийный бархат.

---

### 5. Рабочий код на SciPy

```python
def analog_tape_saturation(audio, sr, drive=1.05, ceiling=0.98, bias=0.035, oversample=2):
    orig_len = len(audio)
    nyq = 0.5 * sr
    
    # 1. NAB-style предыскажения: верха насыщаются и смягчаются первыми
    f0 = min(3500.0, nyq - 50.0) / nyq
    b_pre, a_pre = signal.butter(1, f0, btype='high')
    audio_pre = audio + 0.20 * signal.filtfilt(b_pre, a_pre, audio, axis=0)
    
    # 2. Полифазный оверсэмплинг для предотвращения алиасинга ряда Тейлора
    audio_up = signal.resample_poly(audio_pre, oversample, 1, axis=0)
    
    # 3. Асимметричный тангенс: порождает 2-ю (Bias) и 3-ю (tanh) гармоники
    bias_offset = np.tanh(bias)
    sat_up = (np.tanh(audio_up * drive + bias) - bias_offset) * ceiling
    
    # 4. Полифазное прореживание обратно в 1X
    sat_down = signal.resample_poly(sat_up, 1, oversample, axis=0)
    return sat_down[:orig_len].astype(np.float32)
```

---

## English Version

### The Physics of Analog Tape Saturation: Soft Clipping, Asymmetric tanh, and Eliminating Digital Harshness

#### 1. The Analogy: The Concrete Ceiling vs The Rubber Trampoline
Think of an audio waveform as an athlete jumping on a trampoline. During quiet passages, jumps are effortless. But in a dense chorus with heavy drums and walls of guitars, amplitude pushes into the danger zone.

What happens at the absolute peak?

##### Digital Hard Clipping — The Concrete Ceiling:
In digital audio, 0 dBFS is an impassable ceiling. When unmastered generative peaks (Suno, Udio) hit this threshold, the digital system shears off the sample values horizontally.

When these flatlined samples reach a digital-to-analog converter (DAC), the reconstruction sinc filter overshoots violently, resulting in:
1. Inter-Sample Peaks (ISP) blasting up to $+1.5...+3.0\text{ dBFS}$ into analog gear.
2. A dense comb of high-order odd harmonics folding over Nyquist as inharmonic aliasing hash. To human ears, this registers as shattered glass and immediate auditory fatigue.

##### Analog Tape and BJT Saturation — The Rubber Trampoline:
In vintage studio hardware (Studer A800, Neve console preamps, Ampex 440), there was no concrete ceiling. As amplitude approached saturation, the wave was progressively cushioned and rounded into a continuous organic crest.

#### 2. Harmonic Mathematics: Why Symmetric tanh Cannot Produce 2nd Harmonics
A pervasive myth among junior developers is: *"Just pass your audio through `np.tanh` to get analog tape warmth with 2nd and 3rd harmonics."*

In mathematical analysis, this is fundamentally false:
* The hyperbolic tangent function is **strictly odd**:
  $$\tanh(-x) = -\tanh(x)$$
* A symmetric odd waveshaper **cannot mathematically generate even harmonics** (no 2nd, 4th, or 6th harmonics). It exclusively produces odd harmonics ($3\omega, 5\omega \dots$).
* Odd harmonics (specifically the 3rd) provide dynamic density and glue. But that legendary vintage "warmth" is driven primarily by the **even 2nd harmonic**.

##### How Real Tape Produces 2nd Harmonics:
Real tape machines generate 2nd-order harmonics through physical **asymmetry**: magnetic bias current asymmetry, core hysteresis non-linearities, and input transformer saturation.

##### The PHARMAKON 2.0 Solution:
To synthesize authentic 2nd-order warmth without DC offset, we inject an asymmetric bias term into the transfer function:
$$y = \left(\tanh(x \cdot \text{Drive} + \text{Bias}) - \tanh(\text{Bias})\right) \cdot \text{Ceiling}$$
Subtracting $\tanh(\text{Bias})$ zeroes out DC offset while the induced saturation asymmetry enriches the signal with both the 2nd and 3rd harmonics simultaneously.

#### 3. Taylor Series Aliasing & Polyphase Oversampling
The Taylor series expansion of $\tanh(x)$ is infinite:
$$\tanh(x) = x - \frac{x^3}{3} + \frac{2x^5}{15} - \frac{17x^7}{315} + \dots$$
Executing `np.tanh` at standard 44.1/48 kHz without oversampling causes higher-order odd harmonics from cymbals and sibilance to fold back across Nyquist into digital hash.

Inside PHARMAKON, `analog_tape_saturation` runs in an oversampled polyphase domain (`resample_poly`), ensuring clean non-linear harmonic transfer with zero foldover aliasing.

#### 4. Frequency-Dependent Saturation (NAB Pre-Emphasis)
Real tape recorders employ NAB/IEC pre-emphasis curves: high frequencies are boosted prior to tape contact, causing high-frequency transients to saturate and compress **first** (Tape Softening), while low-end punch remains clear and un-muddled.

PHARMAKON replicates this physical behavior with a pre-filter stage, ensuring generative sibilance and harsh cymbals are transformed into smooth, velvety studio silk.

---
*Repository:* [https://github.com/alex-gerek/PHARMAKON](https://github.com/alex-gerek/PHARMAKON)
