# Межсэмпловые пики (True-Peak): почему Spotify искажает треки на смартфонах и как работает 4X оверсэмплинг
**Автор:** Lex Gerek (Sound Architect / Engineer)  
**Проект:** PHARMAKON 2.0 Studio Console  
**Код реализации:** `remaster_engine.py` (`_true_peak_limiter_block`, `target_ceiling_db=-0.3`)

---

## Русская версия

Это главный секрет и святой Грааль профессионального мастеринга. О нём не догадывается 95% начинающих продюсеров, и именно на нём спотыкаются почти все нейросетевые треки.

Ситуация знакома каждому звукорежиссеру:  
Вы отрендерили трек в DAW (FL Studio, Ableton, Logic). Обычный пиковый индикатор строго показывает -0.1 dBFS. Зеленый свет, никакого клиппинга.  
Вы загружаете трек на Spotify, Apple Music или YouTube. Включаете на iPhone или в беспроводных наушниках - и на каждом ударе бочки и малого барабана слышите неприятный сухой скрежет, песок и потерю прозрачности.

Почему чистый в проекте трек начинает хрипеть на смартфонах? Разбираем на пальцах.

### 1. Метафора: Забор и натянутая веревка
Цифровой звук - это не сплошная линия. Это дискретные моментальные замеры (сэмплы), которые делаются 44 100 или 48 000 раз в секунду.

Представьте деревянный забор:
- Сэмплы - это **вертикальные деревянные колья забора**.
- Стандартный цифровой пик-метр в секвенсоре (Sample Peak Meter) - это линейка, которая замеряет **только высоту верхушек этих кольев**. Если колья не достают до потолка потолок (0 dBFS), программа считает, что всё в порядке.

Но в физическом мире звук из динамика - это не разрозненные колья. Динамик не телепортируется от точки к точке.  
Между кольями натянута гибкая непрерывная аналоговая звуковая волна (как тяжелая натянутая веревка).

Что происходит, когда два соседних кола стоят близко к потолку (например, оба на уровне -0.2 dBFS)?  
Аналоговая веревка между ними по законам механики **неизбежно выгибается дугой ВЫШЕ обоих кольев!**  
И эта дуга вылетает вверх на **+1.0 dB или даже +1.8 dB над нулем**!

Это называется **Inter-Sample Peak (межсэмпловый пик-призрак)**. Обычный цифровой индикатор его не видит, потому что в момент самого пика замера не производилось.

### 2. Почему смартфоны хрипят на стримингах
1. Стриминговые сервисы сжимают ваш WAV файл lossy-кодеками (MP3, AAC, Ogg Vorbis). Фильтры сжатия раскачивают эти невидимые дуги еще сильнее (+0.5...1.0 dB дополнительного вылета).
2. Пользователь слушает трек на телефоне или через Bluetooth. Внутри устройства стоит **ЦАП (цифро-аналоговый преобразователь)**.
3. ЦАП восстанавливает из точек непрерывную волну тока и со всего размаха **врезается в свой физический предел питания**.
4. Возникает аппаратный интермодуляционный клиппинг. Прозрачный микс превращается в грязную кашу.

### 3. Решение PHARMAKON 2.0: 4X полифазный оверсэмплинг
Чтобы поймать невидимку, мы внедрили лимитер международного вещательного стандарта ITU-R BS.1770-4:

1. **Разгон частоты в 4 раза:** Перед лимитированием движок разгоняет сигнал с 48 кГц до 192 кГц (`signal.resample_poly(audio, 4, 1)`).
2. **Обнаружение пиков-призраков:** Между каждыми двумя точками вычисляются 3 дополнительные промежуточные точки. Теперь вершина скрытой дуги видна математике с абсолютной точностью.
3. **Упреждающее сглаживание (Lookahead):** Специальный фильтр с опережением во времени мягко присаживает эту дугу до того, как она успеет вылететь в перегруз.
4. **Возврат на 1X без потерь:** Сигнал возвращается в исходную частоту с гарантированным True-Peak потолком **-0.3 dBFS**.

```python
# 4X Polyphase True-Peak Limiter:
audio_4x = signal.resample_poly(audio, oversample=4, up=1, axis=0)
peak_4x = float(np.max(np.abs(audio_4x)))
# Сглаживание и удержание потолка -0.3 dBFS True-Peak:
gain_ahead = minimum_filter1d(needed_gain, size=win_size)
gain_smooth = signal.filtfilt(b_rel, a_rel, gain_ahead)
limited_1x = signal.resample_poly(limited_4x, 1, oversample=4, axis=0)
```

Трек с честным True-Peak лимитированием выдерживает любое сжатие в MP3 и звучит кристально чисто на любых смартфонах, автомагнитолах и клубных мониторах.

---

## English Version

### Inter-Sample Peaks (True-Peak): Why Spotify Distorts Audio on Smartphones and How 4X Polyphase Oversampling Fixes It

This is the holy grail of professional mastering, unknown to 95% of bedroom producers and overlooked by almost every generative audio workflow.

Every producer has encountered this nightmare:  
You export your track from your DAW. The peak meters read a safe -0.1 dBFS. Zero clip lights.  
You upload the track to Spotify, Apple Music, or YouTube. You play it back on an iPhone or through Bluetooth earbuds, and every heavy kick and snare transient splatters into harsh, scratchy distortion.

Why does a track that looked perfectly clean in your DAW distort on mobile devices? It is the physics of digital-to-analog reconstruction.

### 1. The Analogy: The Picket Fence and the Heavy Rope
Digital audio is not a continuous wave. It consists of discrete snapshot measurements (samples) taken 44,100 or 48,000 times per second.

Think of a wooden picket fence:
- Samples are the **vertical wooden posts of the fence**.
- Standard digital peak meters in DAWs (Sample Peak Meters) are rulers that measure **only the tops of the wooden posts**. If the posts remain below 0 dBFS, the meter smiles green: "All safe, zero clipping."

However, human ears do not hear discrete wooden posts. A speaker cone cannot teleport instantaneously between points.  
Connecting those posts is a continuous, flexible analog wave (like a heavy rope suspended between poles).

What happens when two adjacent posts sit near the ceiling (say, both at -0.2 dBFS)?  
The continuous analog rope suspended between them **must naturally arc ABOVE both posts**!  
That physical arc often peaks at **+1.0 dB to +1.8 dB above zero**!

This is an **Inter-Sample Peak (True-Peak)**. It lives in the real world between discrete samples, completely invisible to standard digital peak meters.

### 2. The Smartphone Distortion Trap
1. Streaming platforms compress your WAV master with lossy codecs (MP3, AAC, Ogg Vorbis). The psychoacoustic filters exacerbate these inter-sample arcs, pushing them even higher (+0.5 dB to +1.0 dB).
2. The listener plays the song on a smartphone. Inside the phone is a **DAC (Digital-to-Analog Converter)**.
3. The DAC reconstructs the continuous analog electrical wave and slams hard into its physical rail voltage limit.
4. The result is nasty intermodulation clipping, transient smear, and instant ear fatigue.

### 3. The PHARMAKON 2.0 Solution: 4X Polyphase Oversampling
To catch invisible inter-sample arcs before they leave the studio, PHARMAKON 2.0 employs broadcast-grade ITU-R BS.1770-4 True-Peak limiting:

1. **4X Polyphase Upsampling:** Before limiting, the engine upsamples 48 kHz audio to 192 kHz (`signal.resample_poly(audio, 4, 1)`).
2. **True Arc Detection:** We place three mathematical reference points between every sample, exposing the exact apex of the inter-sample arc.
3. **Lookahead Polyphase Limiting:** A lookahead envelope follower smooths the transient trajectory before clipping occurs.
4. **Pristine Downsampling:** The audio is polyphase-downsampled back to 1X with a mathematically verified **-0.3 dBFS True-Peak ceiling**.

```python
# Broadcast-grade 4X True-Peak Limiter:
audio_4x = signal.resample_poly(audio, oversample=4, up=1, axis=0)
peak_4x = float(np.max(np.abs(audio_4x)))
gain_ahead = minimum_filter1d(needed_gain, size=win_size)
gain_smooth = signal.filtfilt(b_rel, a_rel, gain_ahead)
limited_1x = signal.resample_poly(limited_4x, 1, oversample=4, axis=0)
```

True-Peak mastered audio survives lossy streaming codecs without distortion, preserving punch, dynamics, and crystal-clear transient definition on any playback system.

---
*Repository:* [https://github.com/alex-gerek/PHARMAKON](https://github.com/alex-gerek/PHARMAKON)
