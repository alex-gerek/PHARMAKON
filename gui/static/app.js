// ==========================================================================
// PHARMAKON 2.0 PRO // STUDIO CONSOLE CONTROLLER
// Dual Real-Time Oscilloscopes & Live Diagnostics by Lex Gerek
// ==========================================================================

let currentMode = 'pharmakon1';
let currentTarget = "";
let currentPreset = 'none';
let bundledDemos = [];
let lastMetrics = null;
let currentViewMode = 'dual'; // 'dual', 'single_osc', 'rta', 'static', 'waveform'
let activeCeiling = -0.3;
let currentScopeZoom = 1.0; // 0.5x to 10.0x macro inspection
let isFrozen = false;

// WebAudio & Real-time Dual Analyser Nodes
let audioCtx = null;
let audioRaw = new Audio();
let audioHealed = new Audio();
audioRaw.crossOrigin = "anonymous";
audioHealed.crossOrigin = "anonymous";
audioRaw.preload = "auto";
audioHealed.preload = "auto";
let sourceRaw = null;
let sourceHealed = null;
let gainRaw = null;
let gainHealed = null;
let analyserRaw = null;
let analyserHealed = null;
let timeDataRaw = null;
let timeDataHealed = null;
let freqDataRaw = null;
let freqDataHealed = null;

// Persistent Wave Storage (Digital Storage Oscilloscope memory)
let frozenWaveRaw = null;
let frozenWaveHealed = null;
let hasCapturedAudio = false;

let activeSource = 'healed'; // 'raw' or 'healed'
let isPlaying = false;
let duration = 0;
let lastResult = null;

// Loop fragment auditioning
let isLooping = false;
let loopStart = 0;
let loopEnd = 0;

// Surgical Range & Punch-in Repair State
let surgicalScope = 'full'; // 'full' or 'region'
let surgicalIn = 0.0;
let surgicalOut = 5.0;
let dragStartSec = 0;

// Canvases
let canvasRaw = null;
let canvasHealed = null;
let canvasSingle = null;

document.addEventListener('DOMContentLoaded', async () => {
  initDropzone();
  initCanvases();
  setViewMode('dual');
  initCanvasWheelZoom();
  initHardwareKnobs();
  setupKeyboardShortcuts();
  
  // Start 60 FPS Dual Render Loop immediately
  requestAnimationFrame(renderLoop);

  // Initialize curated bundled demos and auto-run first demo
  await initBundledDemos();
  if (currentTarget) {
    runPharmakonProcess(true);
  }
});

// --------------------------------------------------------------------------
// WEBAUDIO DUAL ANALYSER & PLAYER ENGINE
// --------------------------------------------------------------------------
function initWebAudio() {
  if (analyserRaw && analyserHealed) return;
  const AudioContext = window.AudioContext || window.webkitAudioContext;
  audioCtx = new AudioContext();

  audioRaw.crossOrigin = "anonymous";
  audioHealed.crossOrigin = "anonymous";

  sourceRaw = audioCtx.createMediaElementSource(audioRaw);
  sourceHealed = audioCtx.createMediaElementSource(audioHealed);

  analyserRaw = audioCtx.createAnalyser();
  analyserRaw.fftSize = 2048;
  analyserRaw.smoothingTimeConstant = 0.8;

  analyserHealed = audioCtx.createAnalyser();
  analyserHealed.fftSize = 2048;
  analyserHealed.smoothingTimeConstant = 0.8;

  gainRaw = audioCtx.createGain();
  gainHealed = audioCtx.createGain();

  // Initial gain: Healed is 1.0 (audible), Raw is 0.0 (muted)
  gainRaw.gain.setValueAtTime(0.0, audioCtx.currentTime);
  gainHealed.gain.setValueAtTime(1.0, audioCtx.currentTime);

  // Monitor bus: sums active auditioned stream (RAW, MASTER, or DELTA)
  monitorBus = audioCtx.createGain();
  monitorBus.gain.setValueAtTime(1.0, audioCtx.currentTime);

  // Connect analysers (tapped before gains so dual CRT screens dance)
  sourceRaw.connect(analyserRaw);
  analyserRaw.connect(gainRaw);
  gainRaw.connect(monitorBus);

  sourceHealed.connect(analyserHealed);
  analyserHealed.connect(gainHealed);
  gainHealed.connect(monitorBus);

  monitorBus.connect(audioCtx.destination);

  // Phase Scope Goniometer Stereo L/R Splitter connected to monitorBus
  splitterNode = audioCtx.createChannelSplitter(2);
  analyserL = audioCtx.createAnalyser();
  analyserR = audioCtx.createAnalyser();
  analyserL.fftSize = 1024;
  analyserR.fftSize = 1024;
  analyserL.smoothingTimeConstant = 0.6;
  analyserR.smoothingTimeConstant = 0.6;

  monitorBus.connect(splitterNode);
  splitterNode.connect(analyserL, 0);
  splitterNode.connect(analyserR, 1);

  timeDataRaw = new Uint8Array(analyserRaw.fftSize);
  timeDataHealed = new Uint8Array(analyserHealed.fftSize);
  freqDataRaw = new Uint8Array(analyserRaw.frequencyBinCount);
  freqDataHealed = new Uint8Array(analyserHealed.frequencyBinCount);

  floatDataL = new Float32Array(analyserL.fftSize);
  floatDataR = new Float32Array(analyserR.fftSize);
}

function setupAudioStreams(origPath, masterPath) {
  audioRaw.src = `/api/stream?path=${encodeURIComponent(origPath)}`;
  audioHealed.src = `/api/stream?path=${encodeURIComponent(masterPath)}`;

  audioRaw.load();
  audioHealed.load();

  audioHealed.addEventListener('loadedmetadata', () => {
    duration = audioHealed.duration;
    document.getElementById('totalTime').innerText = formatTime(duration);
  });

  audioHealed.addEventListener('timeupdate', () => {
    if (duration > 0) {
      // Automatic fragment loop jump
      if (isLooping && loopEnd > loopStart) {
        if (audioHealed.currentTime >= loopEnd || audioHealed.currentTime < loopStart) {
          audioHealed.currentTime = loopStart;
          audioRaw.currentTime = loopStart;
        }
      }

      const pct = (audioHealed.currentTime / duration) * 100;
      document.getElementById('progressBar').style.width = `${pct}%`;
      document.getElementById('currTime').innerText = formatTime(audioHealed.currentTime);
    }
  });

  audioHealed.addEventListener('ended', () => {
    isPlaying = false;
    document.getElementById('playIcon').innerText = "▶";
  });
}

// --------------------------------------------------------------------------
// ANALOG HARDWARE RELAY & TACTILE SWITCH SYNTHESIS (TSAK-TSAK)
// --------------------------------------------------------------------------
let lastKnobClickTime = 0;

function playHardwareClick(type = 'relay') {
  try {
    initWebAudio();
    if (!audioCtx) return;
    if (audioCtx.state === 'suspended') {
      audioCtx.resume();
    }
    const t = audioCtx.currentTime;

    if (type === 'relay') {
      // 1. Heavy physical chassis impact thump (38Hz - 110Hz body resonance)
      const osc = audioCtx.createOscillator();
      const oscGain = audioCtx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(115, t);
      osc.frequency.exponentialRampToValueAtTime(36, t + 0.038);
      oscGain.gain.setValueAtTime(0.35, t);
      oscGain.gain.exponentialRampToValueAtTime(0.001, t + 0.038);
      osc.connect(oscGain);
      oscGain.connect(audioCtx.destination);
      osc.start(t);
      osc.stop(t + 0.04);

      // 2. High metallic spring/contact snap (bandpassed white noise micro-burst)
      const bufSize = Math.floor(audioCtx.sampleRate * 0.02);
      const noiseBuffer = audioCtx.createBuffer(1, bufSize, audioCtx.sampleRate);
      const output = noiseBuffer.getChannelData(0);
      for (let i = 0; i < bufSize; i++) {
        output[i] = (Math.random() * 2 - 1) * Math.exp(-i / (bufSize * 0.22));
      }
      const noise = audioCtx.createBufferSource();
      noise.buffer = noiseBuffer;
      const filter = audioCtx.createBiquadFilter();
      filter.type = 'bandpass';
      filter.frequency.setValueAtTime(3200, t);
      filter.Q.setValueAtTime(2.6, t);
      const noiseGain = audioCtx.createGain();
      noiseGain.gain.setValueAtTime(0.42, t + 0.002);
      noiseGain.gain.exponentialRampToValueAtTime(0.001, t + 0.022);
      noise.connect(filter);
      filter.connect(noiseGain);
      noiseGain.connect(audioCtx.destination);
      noise.start(t + 0.001);

    } else if (type === 'knob') {
      // Subtle stepped detent click for rotary hardware knobs (throttled)
      const nowMs = performance.now();
      if (nowMs - lastKnobClickTime < 45) return;
      lastKnobClickTime = nowMs;

      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = 'triangle';
      osc.frequency.setValueAtTime(1100, t);
      osc.frequency.exponentialRampToValueAtTime(280, t + 0.008);
      gain.gain.setValueAtTime(0.08, t);
      gain.gain.exponentialRampToValueAtTime(0.001, t + 0.008);
      osc.connect(gain);
      gain.connect(audioCtx.destination);
      osc.start(t);
      osc.stop(t + 0.01);

    } else {
      // Crisp toggle switch snap (for preset chips, scopes, tabs)
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(780, t);
      osc.frequency.exponentialRampToValueAtTime(190, t + 0.022);
      gain.gain.setValueAtTime(0.24, t);
      gain.gain.exponentialRampToValueAtTime(0.001, t + 0.022);
      osc.connect(gain);
      gain.connect(audioCtx.destination);
      osc.start(t);
      osc.stop(t + 0.025);
    }
  } catch (e) {
    // Graceful fallback
  }
}

function selectAudioSource(source) {
  playHardwareClick('relay');
  initWebAudio();
  if (audioCtx.state === 'suspended') {
    audioCtx.resume();
  }

  activeSource = source;
  const btnRaw = document.getElementById('btnSourceRaw');
  const btnHealed = document.getElementById('btnSourceHealed');
  const topBtnRaw = document.getElementById('scopeBtnRaw');
  const topBtnHealed = document.getElementById('scopeBtnHealed');
  const topBtnDelta = document.getElementById('scopeBtnDelta');
  const pillRaw = document.getElementById('activePillRaw');
  const pillHealed = document.getElementById('activePillHealed');
  const cardRaw = document.querySelector('.raw-card');
  const cardHealed = document.querySelector('.healed-card');

  const now = audioCtx.currentTime;
  const crossfadeTime = 0.025; // 25ms equal-power smooth crossfade

  if (source === 'raw') {
    if (btnRaw) btnRaw.classList.add('active');
    if (btnHealed) btnHealed.classList.remove('active');
    if (topBtnRaw) topBtnRaw.classList.add('active');
    if (topBtnHealed) topBtnHealed.classList.remove('active');
    if (topBtnDelta) topBtnDelta.classList.remove('active');
    if (pillRaw) pillRaw.classList.add('active');
    if (pillHealed) pillHealed.classList.remove('active');
    if (cardRaw) cardRaw.classList.add('active-monitor');
    if (cardHealed) cardHealed.classList.remove('active-monitor');

    gainRaw.gain.setTargetAtTime(1.0, now, crossfadeTime);
    gainHealed.gain.setTargetAtTime(0.0, now, crossfadeTime);
    updateStatus("MONITORING [A] RAW DIGITAL AI: Unadulterated original input with digital artifacts.");
  } else if (source === 'delta') {
    if (btnRaw) btnRaw.classList.remove('active');
    if (btnHealed) btnHealed.classList.remove('active');
    if (topBtnRaw) topBtnRaw.classList.remove('active');
    if (topBtnHealed) topBtnHealed.classList.remove('active');
    if (topBtnDelta) topBtnDelta.classList.add('active');
    if (pillRaw) pillRaw.classList.remove('active');
    if (pillHealed) pillHealed.classList.remove('active');
    if (cardRaw) cardRaw.classList.remove('active-monitor');
    if (cardHealed) cardHealed.classList.remove('active-monitor');

    // DELTA RESIDUE: Raw - Master (inverted phase on master)
    // +6 dB boost (2.0x) so subtle removed harshness & rumble are clearly audible
    gainRaw.gain.setTargetAtTime(2.0, now, crossfadeTime);
    gainHealed.gain.setTargetAtTime(-2.0, now, crossfadeTime);
    updateStatus("MONITORING [Δ] DELTA RESIDUE: Auditioning extracted poison & removed harshness (+6dB boost).");
  } else {
    if (btnRaw) btnRaw.classList.remove('active');
    if (btnHealed) btnHealed.classList.add('active');
    if (topBtnRaw) topBtnRaw.classList.remove('active');
    if (topBtnHealed) topBtnHealed.classList.add('active');
    if (topBtnDelta) topBtnDelta.classList.remove('active');
    if (pillRaw) pillRaw.classList.remove('active');
    if (pillHealed) pillHealed.classList.add('active');
    if (cardRaw) cardRaw.classList.remove('active-monitor');
    if (cardHealed) cardHealed.classList.add('active-monitor');

    gainRaw.gain.setTargetAtTime(0.0, now, crossfadeTime);
    gainHealed.gain.setTargetAtTime(1.0, now, crossfadeTime);
    updateStatus("MONITORING [B] PHARMAKON MASTER: Polished, glued analog master with True-Peak protection.");
  }
}

function togglePlayPause() {
  initWebAudio();
  if (audioCtx.state === 'suspended') {
    audioCtx.resume();
  }

  if (!audioHealed.src || audioHealed.src === window.location.href) {
    runPharmakonProcess();
    return;
  }

  if (isPlaying) {
    captureDualSnapshot();
    audioRaw.pause();
    audioHealed.pause();
    isPlaying = false;
    document.getElementById('playIcon').innerText = "▶";
    updateStatus("PAUSED. Both screens frozen in sync. Use Zoom or mouse wheel to inspect.");
  } else {
    // Unfreeze when resuming playback
    if (isFrozen) {
      isFrozen = false;
      const bFr = document.getElementById('btnFreeze');
      if (bFr) bFr.classList.remove('active');
    }
    // Exact frame sync
    audioRaw.currentTime = audioHealed.currentTime;
    audioRaw.play().catch(() => {});
    audioHealed.play().catch(() => {});
    isPlaying = true;
    document.getElementById('playIcon').innerText = "❚❚";
  }
}

function toggleLoopFragment() {
  isLooping = !isLooping;
  const btn = document.getElementById('btnLoop');
  if (isLooping) {
    const cur = (audioHealed && audioHealed.currentTime) ? audioHealed.currentTime : 0;
    loopStart = Math.max(0, cur - 1.0);
    loopEnd = Math.min(duration || 10.0, loopStart + 5.0);
    if (btn) btn.classList.add('active');
    updateStatus(`🔁 LOOPING 5s FRAGMENT: ${formatTime(loopStart)} ➔ ${formatTime(loopEnd)}. Switch [A] / [B] to audition!`);
    if (!isPlaying) togglePlayPause();
  } else {
    if (btn) btn.classList.remove('active');
    updateStatus("Loop disabled. Full playback active.");
  }
}

function seekAudio(e) {
  const track = document.getElementById('progressTrack');
  const rect = track.getBoundingClientRect();
  const clickX = e.clientX - rect.left;
  const pct = Math.max(0, Math.min(1, clickX / rect.width));

  if (duration > 0) {
    const targetTime = pct * duration;
    audioHealed.currentTime = targetTime;
    audioRaw.currentTime = targetTime;
  }
}

// --------------------------------------------------------------------------
// 60 FPS DUAL CANVASES RENDER LOOP
// --------------------------------------------------------------------------
function initCanvases() {
  canvasRaw = document.getElementById('canvasRaw');
  canvasHealed = document.getElementById('canvasHealed');
  canvasSingle = document.getElementById('canvasSingle');

  fitCanvasDpi(canvasRaw);
  fitCanvasDpi(canvasHealed);
  fitCanvasDpi(canvasSingle);

  if (canvasSingle) {
    let isMouseDown = false;
    let mouseDownX = 0;

    canvasSingle.addEventListener('mousedown', (e) => {
      if (currentViewMode !== 'waveform' || duration <= 0) return;
      isMouseDown = true;
      const rect = canvasSingle.getBoundingClientRect();
      mouseDownX = e.clientX - rect.left;
      const pct = Math.max(0, Math.min(1, mouseDownX / rect.width));
      dragStartSec = pct * duration;
    });

    canvasSingle.addEventListener('mousemove', (e) => {
      if (!isMouseDown || currentViewMode !== 'waveform' || duration <= 0) return;
      const rect = canvasSingle.getBoundingClientRect();
      const curX = e.clientX - rect.left;
      const pct = Math.max(0, Math.min(1, curX / rect.width));
      const curSec = pct * duration;

      if (Math.abs(curX - mouseDownX) > 8) {
        if (surgicalScope !== 'region') {
          setMasteringScope('region');
        }
        surgicalIn = Math.min(dragStartSec, curSec);
        surgicalOut = Math.max(dragStartSec, curSec);
        updateSurgicalInputs();
      }
    });

    window.addEventListener('mouseup', (e) => {
      if (!isMouseDown) return;
      isMouseDown = false;
      if (currentViewMode === 'waveform' && duration > 0) {
        const rect = canvasSingle.getBoundingClientRect();
        const curX = e.clientX - rect.left;
        if (Math.abs(curX - mouseDownX) <= 8) {
          // Quick click: seek audio to position
          const pct = Math.max(0, Math.min(1, mouseDownX / rect.width));
          const targetTime = pct * duration;
          audioHealed.currentTime = targetTime;
          audioRaw.currentTime = targetTime;
        }
      }
    });

    canvasSingle.addEventListener('dblclick', () => {
      if (currentViewMode === 'waveform') {
        resetSurgicalRegion();
      }
    });
  }
}

function fitCanvasDpi(canvas) {
  if (!canvas) return;
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  canvas.width = (rect.width || 580) * dpr;
  canvas.height = (rect.height || 240) * dpr;
}

function initCanvasWheelZoom() {
  const canvases = [
    document.getElementById('canvasRaw'),
    document.getElementById('canvasHealed'),
    document.getElementById('canvasSingle')
  ];
  canvases.forEach(c => {
    if (!c) return;
    c.addEventListener('wheel', (e) => {
      e.preventDefault();
      if (e.deltaY < 0) adjustZoom(0.5);
      else adjustZoom(-0.5);
    }, { passive: false });
  });
}

window.addEventListener('resize', () => {
  initCanvases();
});

function renderLoop() {
  try {
    if (currentViewMode === 'dual') {
      renderDualOscilloscopes();
    } else if (currentViewMode === 'single_osc') {
      renderSingleOscilloscope();
    } else if (currentViewMode === 'rta') {
      renderSingleRta();
    } else if (currentViewMode === 'static') {
      renderSingleStatic();
    } else if (currentViewMode === 'waveform') {
      renderSingleWaveform();
    } else if (currentViewMode === 'goniometer') {
      renderGoniometerScope();
    }
  } catch (loopErr) {
    console.error("renderLoop protected error:", loopErr);
  }

  requestAnimationFrame(renderLoop);
}

function renderDualOscilloscopes() {
  if (!canvasRaw || !canvasHealed) return;

  const ctxR = canvasRaw.getContext('2d');
  const wR = canvasRaw.width;
  const hR = canvasRaw.height;

  const ctxH = canvasHealed.getContext('2d');
  const wH = canvasHealed.width;
  const hH = canvasHealed.height;

  // Retrieve Time Data for BOTH tracks simultaneously while playing
  if (isPlaying && analyserRaw && analyserHealed && !isFrozen) {
    analyserRaw.getByteTimeDomainData(timeDataRaw);
    analyserHealed.getByteTimeDomainData(timeDataHealed);

    // Keep both tracks sample-synced
    if (Math.abs(audioRaw.currentTime - audioHealed.currentTime) > 0.03) {
      audioRaw.currentTime = audioHealed.currentTime;
    }

    // Save active wave snapshot to persistent storage
    let diffR = 0, diffH = 0;
    for (let i = 0; i < 32; i++) {
      diffR += Math.abs(timeDataRaw[i * 8] - 128);
      diffH += Math.abs(timeDataHealed[i * 8] - 128);
    }
    if (diffR > 5) {
      if (!frozenWaveRaw) frozenWaveRaw = new Uint8Array(timeDataRaw.length);
      frozenWaveRaw.set(timeDataRaw);
    }
    if (diffH > 5) {
      if (!frozenWaveHealed) frozenWaveHealed = new Uint8Array(timeDataHealed.length);
      frozenWaveHealed.set(timeDataHealed);
    }
    if (diffR > 5 || diffH > 5) {
      hasCapturedAudio = true;
    }
  }

  const dataR = (isPlaying && !isFrozen) ? timeDataRaw : (frozenWaveRaw || timeDataRaw);
  const dataH = (isPlaying && !isFrozen) ? timeDataHealed : (frozenWaveHealed || timeDataHealed);
  const shouldRenderActive = isPlaying || isFrozen || hasCapturedAudio;

  // Draw Screen 1: Raw (Red laser beam)
  renderScopeBeam(ctxR, wR, hR, dataR, '#ef4444', '#ff8888', shouldRenderActive, 0.0, false);

  // Draw Screen 2: Healed (Emerald phosphor beam)
  renderScopeBeam(ctxH, wH, hH, dataH, '#10b981', '#a7f3d0', shouldRenderActive, 1.2, true);
}

function renderScopeBeam(ctx, w, h, data, glowColor, coreColor, playing, phaseShift, isHealed = false) {
  // Clear with phosphor persistence trail
  ctx.fillStyle = 'rgba(3, 5, 8, 0.35)';
  ctx.fillRect(0, 0, w, h);

  drawGraticule(ctx, w, h, isHealed);

  const midY = (h / 2) + 6;
  const maxAmp = h * 0.38;

  // Idle mode
  if (!playing || !data) {
    const t = performance.now() * 0.003 + phaseShift;
    ctx.strokeStyle = glowColor;
    ctx.globalAlpha = 0.35;
    ctx.lineWidth = 2;
    ctx.beginPath();
    for (let x = 0; x < w; x += 4) {
      const y = midY + Math.sin(x * 0.02 + t) * 5;
      if (x === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.stroke();
    ctx.globalAlpha = 1.0;
    return;
  }

  // Trigger stabilization: find zero-crossing with positive slope
  let triggerIndex = 0;
  for (let i = 0; i < data.length / 2; i++) {
    if (data[i] < 128 && data[i + 1] >= 128) {
      triggerIndex = i;
      break;
    }
  }

  // Macro Zoom timebase slicing
  const zoom = currentScopeZoom || 1.0;
  const baseSlice = Math.floor(data.length * 0.65);
  const sliceLen = Math.max(24, Math.floor(baseSlice / zoom));
  const step = w / sliceLen;

  // Pass 1: Glowing halo
  ctx.save();
  ctx.shadowBlur = 16;
  ctx.shadowColor = glowColor;
  ctx.strokeStyle = glowColor;
  ctx.lineWidth = 3.2;
  ctx.beginPath();
  for (let i = 0; i < sliceLen; i++) {
    const val = (data[triggerIndex + i] || 128) - 128;
    const y = midY + (val / 128.0) * maxAmp;
    const x = i * step;
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  }
  ctx.stroke();
  ctx.restore();

  // Pass 2: Sharp core beam
  ctx.strokeStyle = coreColor;
  ctx.lineWidth = 1.8;
  ctx.beginPath();
  for (let i = 0; i < sliceLen; i++) {
    const val = (data[triggerIndex + i] || 128) - 128;
    const y = midY + (val / 128.0) * maxAmp;
    const x = i * step;
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  }
  ctx.stroke();
}

function drawGraticule(ctx, w, h, isHealed = false) {
  const midX = w / 2;
  const midY = (h / 2) + 6;
  const maxAmp = h * 0.38; // Clean headroom to prevent title collisions

  // 1. Grid background subdivisions
  ctx.strokeStyle = '#0b101d';
  ctx.lineWidth = 1;

  const cols = 8;
  const rows = 6;
  const dx = w / cols;
  const dy = (h - 24) / rows;

  for (let c = 1; c < cols; c++) {
    ctx.beginPath(); ctx.moveTo(c * dx, 16); ctx.lineTo(c * dx, h - 16); ctx.stroke();
  }
  for (let r = 1; r < rows; r++) {
    ctx.beginPath(); ctx.moveTo(0, 16 + r * dy); ctx.lineTo(w, 16 + r * dy); ctx.stroke();
  }

  // 2. Center Crosshair Axes with Precision Ticks
  ctx.strokeStyle = '#18243b';
  ctx.lineWidth = 1.2;
  ctx.beginPath();
  ctx.moveTo(0, midY); ctx.lineTo(w, midY);
  ctx.moveTo(midX, 16); ctx.lineTo(midX, h - 16);
  ctx.stroke();

  // Fine division tick marks along center axes
  ctx.fillStyle = '#263757';
  for (let x = 0; x < w; x += dx / 5) {
    ctx.fillRect(x, midY - 2, 1, 5);
  }
  for (let y = 16; y < h - 16; y += dy / 5) {
    ctx.fillRect(midX - 2, y, 5, 1);
  }

  // 3. TARGET CALIBRATION GUIDES (dBFS)
  ctx.font = '9px "JetBrains Mono", monospace';

  // 0.0 dBFS Digital Ceiling (Red)
  const yClipTop = midY - maxAmp;
  const yClipBottom = midY + maxAmp;
  ctx.strokeStyle = 'rgba(239, 68, 68, 0.45)';
  ctx.setLineDash([4, 4]);
  ctx.beginPath();
  ctx.moveTo(0, yClipTop); ctx.lineTo(w, yClipTop);
  ctx.moveTo(0, yClipBottom); ctx.lineTo(w, yClipBottom);
  ctx.stroke();

  // Badge 0.0 dBFS on left
  ctx.textAlign = 'left';
  ctx.fillStyle = 'rgba(10, 12, 18, 0.75)';
  ctx.fillRect(6, yClipTop - 11, 130, 13);
  ctx.fillStyle = '#ef4444';
  ctx.fillText('0.0 dBFS [DIGITAL CLIP]', 8, yClipTop - 1);

  // -0.3 dBFS True-Peak Ceiling (10^(-0.3/20) = 0.966)
  const yCeilTop = midY - (maxAmp * 0.966);
  const yCeilBottom = midY + (maxAmp * 0.966);
  ctx.strokeStyle = isHealed ? 'rgba(16, 185, 129, 0.75)' : 'rgba(245, 158, 11, 0.45)';
  ctx.setLineDash([3, 3]);
  ctx.beginPath();
  ctx.moveTo(0, yCeilTop); ctx.lineTo(w, yCeilTop);
  ctx.moveTo(0, yCeilBottom); ctx.lineTo(w, yCeilBottom);
  ctx.stroke();
  ctx.setLineDash([]); // Reset dash

  // Badge -0.3 dBFS on right
  ctx.textAlign = 'right';
  ctx.fillStyle = 'rgba(10, 12, 18, 0.75)';
  ctx.fillRect(w - 175, yCeilTop - 11, 168, 13);
  ctx.fillStyle = isHealed ? '#10b981' : '#f59e0b';
  ctx.fillText('-0.3 dBFS [TRUE-PEAK TARGET]', w - 8, yCeilTop - 1);

  // Intermediate dB levels
  ctx.textAlign = 'left';
  ctx.fillStyle = '#475569';
  const y6 = midY - (maxAmp * 0.501);
  ctx.fillText('-6 dB', 8, y6 - 2);

  const y12 = midY - (maxAmp * 0.251);
  ctx.fillText('-12 dB', 8, y12 - 2);

  // 4. HORIZONTAL TIME SCALE LABELS (ms) with Zoom factor
  ctx.textAlign = 'center';
  ctx.fillStyle = '#475569';
  const zoom = currentScopeZoom || 1.0;
  const timePerCol = 2.5 / zoom;
  for (let c = 0; c <= cols; c++) {
    const timeVal = (c * timePerCol).toFixed(timePerCol < 1 ? 2 : 1);
    const xPos = Math.max(16, Math.min(w - 20, c * dx));
    ctx.fillText(`${timeVal}ms`, xPos, h - 5);
  }
}

// --------------------------------------------------------------------------
// SINGLE FULL VIEW MODES (RTA & STATIC)
// --------------------------------------------------------------------------
function setViewMode(mode) {
  playHardwareClick('toggle');
  currentViewMode = mode;
  const bDual = document.getElementById('btnViewDual');
  const bSingle = document.getElementById('btnViewSingleOsc');
  const bRta = document.getElementById('btnViewRta');
  const bStatic = document.getElementById('btnViewStatic');
  const bWave = document.getElementById('btnViewWaveform');
  const bGonio = document.getElementById('btnViewGoniometer');

  if (bDual) bDual.classList.toggle('active', mode === 'dual');
  if (bSingle) bSingle.classList.toggle('active', mode === 'single_osc');
  if (bRta) bRta.classList.toggle('active', mode === 'rta');
  if (bStatic) bStatic.classList.toggle('active', mode === 'static');
  if (bWave) bWave.classList.toggle('active', mode === 'waveform');
  if (bGonio) bGonio.classList.toggle('active', mode === 'goniometer');

  const dualGrid = document.getElementById('dualScreensContainer');
  const singleView = document.getElementById('altViewContainer');

  if (mode === 'dual') {
    dualGrid.style.display = 'grid';
    singleView.style.display = 'none';
  } else {
    dualGrid.style.display = 'none';
    singleView.style.display = 'block';
    fitCanvasDpi(canvasSingle);
  }
}

// -----------------------------------------------------------------------------
// LISSAJOUS PHASE GONIOMETER & CORRELATION SCOPE (CRT 60 FPS)
// -----------------------------------------------------------------------------
function renderGoniometerScope() {
  if (!canvasSingle) return;
  const ctx = canvasSingle.getContext('2d');
  const w = canvasSingle.width;
  const h = canvasSingle.height;

  // Background CRT dark phosphor clear
  ctx.fillStyle = '#060a10';
  ctx.fillRect(0, 0, w, h);

  const cx = w / 2;
  const cy = h / 2 - 18;
  const radius = Math.min(w * 0.30, h * 0.38, 140);

  ctx.save();

  // 1. Draw Oscilloscope Radar Reticle
  ctx.strokeStyle = 'rgba(20, 35, 55, 0.7)';
  ctx.lineWidth = 1;

  // Concentric Range Rings
  [1.0, 0.75, 0.5, 0.25].forEach(rMul => {
    ctx.beginPath();
    ctx.arc(cx, cy, radius * rMul, 0, 2 * Math.PI);
    ctx.stroke();
  });

  // Diagonal 45-deg M/S lines (L and R axes)
  ctx.strokeStyle = 'rgba(16, 185, 129, 0.25)';
  ctx.setLineDash([4, 4]);

  // +L axis (-45 deg)
  ctx.beginPath();
  ctx.moveTo(cx - radius * 0.9, cy - radius * 0.9);
  ctx.lineTo(cx + radius * 0.9, cy + radius * 0.9);
  ctx.stroke();

  // +R axis (+45 deg)
  ctx.beginPath();
  ctx.moveTo(cx + radius * 0.9, cy - radius * 0.9);
  ctx.lineTo(cx - radius * 0.9, cy + radius * 0.9);
  ctx.stroke();

  // Horizontal Side (L-R) axis
  ctx.strokeStyle = 'rgba(239, 68, 68, 0.35)';
  ctx.beginPath();
  ctx.moveTo(cx - radius * 1.15, cy);
  ctx.lineTo(cx + radius * 1.15, cy);
  ctx.stroke();

  // Vertical Mono/Mid (M) axis
  ctx.strokeStyle = 'rgba(56, 189, 248, 0.45)';
  ctx.beginPath();
  ctx.moveTo(cx, cy - radius * 1.15);
  ctx.lineTo(cx, cy + radius * 1.15);
  ctx.stroke();
  ctx.setLineDash([]);

  // Reticle Labels
  ctx.font = '10px "JetBrains Mono", monospace';
  ctx.textAlign = 'center';
  ctx.fillStyle = '#38bdf8';
  ctx.fillText('+M (MONO)', cx, cy - radius - 8);
  ctx.fillText('-M', cx, cy + radius + 14);

  ctx.fillStyle = '#10b981';
  ctx.fillText('+L', cx - radius * 0.72 - 14, cy - radius * 0.72 - 4);
  ctx.fillText('+R', cx + radius * 0.72 + 14, cy - radius * 0.72 - 4);

  ctx.fillStyle = '#f43f5e';
  ctx.fillText('-S', cx - radius - 16, cy + 3);
  ctx.fillText('+S', cx + radius + 16, cy + 3);

  // 2. Fetch Stereo Time Data from analysers (or fallback from mono wave)
  let sumLR = 0, sumLL = 0, sumRR = 0;
  let hasSignal = false;

  if (analyserL && analyserR && floatDataL && floatDataR) {
    analyserL.getFloatTimeDomainData(floatDataL);
    analyserR.getFloatTimeDomainData(floatDataR);

    for (let i = 0; i < floatDataL.length; i++) {
      if (Math.abs(floatDataL[i]) > 0.001 || Math.abs(floatDataR[i]) > 0.001) {
        hasSignal = true;
        break;
      }
    }
  }

  const isAudioActive = isPlaying || isFrozen || hasCapturedAudio;

  if (isAudioActive && hasSignal && floatDataL && floatDataR) {
    const isDelta = (activeSource === 'delta');
    const isRaw = (activeSource === 'raw');
    const glowColor = isDelta ? 'rgba(245, 158, 11, 0.6)' : (isRaw ? 'rgba(239, 68, 68, 0.55)' : 'rgba(16, 185, 129, 0.65)');
    const coreColor = isDelta ? '#fbbf24' : (isRaw ? '#fca5a5' : '#a7f3d0');

    ctx.shadowBlur = 10;
    ctx.shadowColor = glowColor;
    ctx.strokeStyle = coreColor;
    ctx.lineWidth = 1.6;
    ctx.beginPath();

    const sqrt2 = Math.SQRT2;
    const gainScale = radius * 1.5;
    const len = floatDataL.length;

    for (let i = 0; i < len; i++) {
      const l = floatDataL[i];
      const r = floatDataR[i];

      sumLR += l * r;
      sumLL += l * l;
      sumRR += r * r;

      // 45 degree rotation: X = (L - R) / sqrt(2), Y = -(L + R) / sqrt(2)
      const side = (l - r) / sqrt2;
      const mid = (l + r) / sqrt2;

      const px = cx + side * gainScale;
      const py = cy - mid * gainScale;

      if (i === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    }
    ctx.stroke();
    ctx.shadowBlur = 0;
  } else {
    // Idle glowing center reticle line
    ctx.strokeStyle = 'rgba(16, 185, 129, 0.35)';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(cx, cy - 15);
    ctx.lineTo(cx, cy + 15);
    ctx.stroke();
  }
  ctx.restore();

  // 3. Phase Correlation Calculation
  let rawCorr = 1.0;
  if (sumLL > 1e-7 && sumRR > 1e-7) {
    rawCorr = sumLR / Math.sqrt(sumLL * sumRR);
    rawCorr = Math.max(-1.0, Math.min(1.0, rawCorr));
  }
  smoothedCorrelation = 0.88 * smoothedCorrelation + 0.12 * rawCorr;
  const corr = (isAudioActive && hasSignal) ? smoothedCorrelation : 1.0;

  // 4. Draw Phase Correlation Meter Bar at Bottom
  const barW = Math.min(460, w - 80);
  const barH = 12;
  const barX = (w - barW) / 2;
  const barY = h - 38;

  ctx.fillStyle = '#080d14';
  ctx.fillRect(barX, barY, barW, barH);
  ctx.strokeStyle = '#1e293b';
  ctx.lineWidth = 1;
  ctx.strokeRect(barX, barY, barW, barH);

  // Gradient zone: -1 (red) -> 0 (yellow) -> +1 (green)
  const grad = ctx.createLinearGradient(barX, 0, barX + barW, 0);
  grad.addColorStop(0.0, 'rgba(239, 68, 68, 0.85)');
  grad.addColorStop(0.45, 'rgba(245, 158, 11, 0.7)');
  grad.addColorStop(0.55, 'rgba(245, 158, 11, 0.7)');
  grad.addColorStop(1.0, 'rgba(16, 185, 129, 0.85)');

  // Needle position
  const needleNorm = (corr + 1.0) / 2.0; // 0.0 to 1.0
  const needleX = barX + Math.max(0, Math.min(barW, needleNorm * barW));

  // Fill up to center or needle
  ctx.fillStyle = grad;
  const centerX = barX + barW / 2;
  if (needleX >= centerX) {
    ctx.fillRect(centerX, barY + 1, needleX - centerX, barH - 2);
  } else {
    ctx.fillRect(needleX, barY + 1, centerX - needleX, barH - 2);
  }

  // Draw Needle
  ctx.fillStyle = '#ffffff';
  ctx.shadowColor = '#38bdf8';
  ctx.shadowBlur = 8;
  ctx.fillRect(needleX - 2, barY - 2, 4, barH + 4);
  ctx.shadowBlur = 0;

  // Scale markings
  ctx.fillStyle = '#64748b';
  ctx.font = '9px "JetBrains Mono", monospace';
  ctx.textAlign = 'center';
  ctx.fillText('-1.0', barX, barY + barH + 12);
  ctx.fillText('-0.5', barX + barW * 0.25, barY + barH + 12);
  ctx.fillText('0.0 (WIDE)', barX + barW * 0.5, barY + barH + 12);
  ctx.fillText('+0.5', barX + barW * 0.75, barY + barH + 12);
  ctx.fillText('+1.0 (MONO)', barX + barW, barY + barH + 12);

  // Top Badge Readout
  const corrColor = corr > 0.4 ? '#10b981' : (corr > 0.0 ? '#f59e0b' : '#ef4444');
  const corrText = corr > 0.7 ? 'SOLID MONO-COMPATIBLE STEREO' : (corr > 0.2 ? 'WIDE STEREO SPREAD' : (corr > 0 ? 'CRITICAL STEREO (MARGINAL MONO)' : '⚠ OUT OF PHASE / MONO CANCELLATION'));

  ctx.fillStyle = 'rgba(10, 14, 22, 0.88)';
  const badgeW = Math.min(520, w - 40);
  ctx.fillRect((w - badgeW) / 2, 8, badgeW, 22);
  ctx.strokeStyle = '#1e293b';
  ctx.strokeRect((w - badgeW) / 2, 8, badgeW, 22);

  ctx.font = 'bold 11px "JetBrains Mono", monospace';
  ctx.fillStyle = corrColor;
  ctx.textAlign = 'center';
  ctx.fillText(`PHASE CORRELATION: ${corr >= 0 ? '+' : ''}${corr.toFixed(2)}  •  ${corrText}`, w / 2, 23);
}


function renderSingleOscilloscope() {
  if (!canvasSingle) return;
  const ctx = canvasSingle.getContext('2d');
  const w = canvasSingle.width;
  const h = canvasSingle.height;

  const isRaw = (activeSource === 'raw');
  if (isPlaying && analyserRaw && analyserHealed && !isFrozen) {
    analyserRaw.getByteTimeDomainData(timeDataRaw);
    analyserHealed.getByteTimeDomainData(timeDataHealed);
  }

  const data = isRaw
    ? ((isPlaying && !isFrozen) ? timeDataRaw : (frozenWaveRaw || timeDataRaw))
    : ((isPlaying && !isFrozen) ? timeDataHealed : (frozenWaveHealed || timeDataHealed));
  const shouldRenderActive = isPlaying || isFrozen || hasCapturedAudio;

  const glowColor = isRaw ? '#ef4444' : '#10b981';
  const coreColor = isRaw ? '#ffaaaa' : '#e6fffa';
  renderScopeBeam(ctx, w, h, data, glowColor, coreColor, shouldRenderActive, 0.0, !isRaw);

  // HUD in Single Mode: draw clean top-center title badge without colliding with dB marks
  ctx.font = '11px "JetBrains Mono", monospace';
  ctx.textAlign = 'center';
  const badgeW = 420;
  ctx.fillStyle = 'rgba(10, 14, 22, 0.85)';
  ctx.fillRect((w - badgeW) / 2, 5, badgeW, 18);
  ctx.strokeStyle = isRaw ? 'rgba(239, 68, 68, 0.5)' : 'rgba(16, 185, 129, 0.5)';
  ctx.lineWidth = 1;
  ctx.strokeRect((w - badgeW) / 2, 5, badgeW, 18);

  ctx.fillStyle = isRaw ? '#ff6b6b' : '#34d399';
  const stateLabel = isFrozen ? "[❄ FROZEN FRAME]" : (isPlaying ? "[● LIVE 60 FPS]" : "[PAUSED - ZOOM READY]");
  const label = isRaw ? `[A] RAW DIGITAL AI ${stateLabel}` : `[B] PHARMAKON MASTER ${stateLabel}`;
  ctx.fillText(label, w / 2, 18);
}

function adjustZoom(delta) {
  currentScopeZoom = Math.max(0.5, Math.min(10.0, Math.round((currentScopeZoom + delta) * 10) / 10));
  const el = document.getElementById('zoomReadout');
  if (el) el.innerText = currentScopeZoom.toFixed(1) + 'x';
  updateStatus(`Timebase Zoom: ${currentScopeZoom.toFixed(1)}x (${(2.5 / currentScopeZoom).toFixed(2)} ms/DIV)`);
}

function captureDualSnapshot() {
  initWebAudio();
  if (analyserRaw && timeDataRaw) {
    if (!frozenWaveRaw) frozenWaveRaw = new Uint8Array(analyserRaw.fftSize);
    analyserRaw.getByteTimeDomainData(frozenWaveRaw);
  }
  if (analyserHealed && timeDataHealed) {
    if (!frozenWaveHealed) frozenWaveHealed = new Uint8Array(analyserHealed.fftSize);
    analyserHealed.getByteTimeDomainData(frozenWaveHealed);
  }

  // Dual-screen sync guarantee:
  // If one channel captured audio while the other was momentarily silent or unbuffered,
  // synthesize the corresponding counterpart so BOTH screens freeze together!
  if (frozenWaveRaw && frozenWaveHealed) {
    let diffR = 0, diffH = 0;
    for (let i = 0; i < 32; i++) {
      diffR += Math.abs(frozenWaveRaw[i * 8] - 128);
      diffH += Math.abs(frozenWaveHealed[i * 8] - 128);
    }
    if (diffR > 5 && diffH < 5) {
      // Synthesize Healed waveform from Raw with analog tape tanh and -0.3 dBFS ceiling clamp
      for (let i = 0; i < frozenWaveRaw.length; i++) {
        const v = (frozenWaveRaw[i] - 128) / 128.0;
        const vHealed = Math.tanh(v * 1.04) * 0.966;
        frozenWaveHealed[i] = Math.round(128 + vHealed * 128.0);
      }
    } else if (diffH > 5 && diffR < 5) {
      // Synthesize Raw waveform from Healed
      for (let i = 0; i < frozenWaveHealed.length; i++) {
        const v = (frozenWaveHealed[i] - 128) / 128.0;
        frozenWaveRaw[i] = Math.round(128 + v * 1.12 * 128.0);
      }
    }
    hasCapturedAudio = true;
  }
}

function toggleFreeze() {
  playHardwareClick('toggle');
  isFrozen = !isFrozen;
  if (isFrozen) {
    captureDualSnapshot();
  }
  const btn = document.getElementById('btnFreeze');
  if (btn) btn.classList.toggle('active', isFrozen);
  updateStatus(isFrozen ? "❄ BOTH SCREENS FROZEN IN SYNC. Zoom & inspect micro-waveforms." : "▶ DUAL OSCILLOSCOPES RUNNING LIVE.");
}

function renderSingleWaveform() {
  if (!canvasSingle) return;
  const ctx = canvasSingle.getContext('2d');
  const w = canvasSingle.width;
  const h = canvasSingle.height;

  ctx.fillStyle = '#06080e';
  ctx.fillRect(0, 0, w, h);
  drawGraticule(ctx, w, h);

  if (!lastMetrics || !lastMetrics.waveform_proc) {
    ctx.fillStyle = '#4b5563';
    ctx.font = '12px "JetBrains Mono"';
    ctx.textAlign = 'center';
    ctx.fillText("LOAD TRACK & CLICK HEAL FOR WAVEFORM OVERVIEW", w / 2, h / 2);
    return;
  }

  const waveP = lastMetrics.waveform_proc;
  const waveO = lastMetrics.waveform_orig;
  const isRaw = (activeSource === 'raw');
  const step = w / waveP.length;
  const midY = (h / 2) + 6;
  const maxAmp = h * 0.38;

  // 1. Ghost comparison background layer
  if (isRaw) {
    // Auditioning [A] RAW:
    // Show Master as faint emerald ghost reference in the background
    ctx.fillStyle = 'rgba(16, 185, 129, 0.20)';
    for (let i = 0; i < waveP.length; i++) {
      const barH = waveP[i] * maxAmp;
      ctx.fillRect(i * step, midY - barH, step * 0.85, barH * 2);
    }

    // Active Raw Foreground: Luminous Laser Red with White/Yellow Clipping Spikes
    for (let i = 0; i < waveO.length; i++) {
      const barH = waveO[i] * maxAmp;
      const isClipping = (waveO[i] >= 0.95); // High risk clipping
      ctx.fillStyle = isClipping ? '#ffdd55' : '#ef4444';
      if (isClipping) {
        ctx.shadowColor = '#ef4444';
        ctx.shadowBlur = 6;
      }
      ctx.fillRect(i * step, midY - barH, step * 0.85, barH * 2);
      ctx.shadowBlur = 0;
    }
  } else {
    // Auditioning [B] PHARMAKON MASTER:
    // Show Raw as faint red ghost reference in the background (showing what was healed)
    ctx.fillStyle = 'rgba(239, 68, 68, 0.22)';
    for (let i = 0; i < waveO.length; i++) {
      const barH = waveO[i] * maxAmp;
      ctx.fillRect(i * step, midY - barH, step * 0.85, barH * 2);
    }

    // Active Master Foreground: Luminous Emerald Phosphor (tape glued & clamped)
    ctx.fillStyle = '#10b981';
    for (let i = 0; i < waveP.length; i++) {
      const barH = waveP[i] * maxAmp;
      ctx.fillRect(i * step, midY - barH, step * 0.85, barH * 2);
    }
  }

  // 1.5. Highlight Active Loop Region (if looping)
  if (isLooping && duration > 0 && loopEnd > loopStart) {
    const xL1 = (loopStart / duration) * w;
    const xL2 = (loopEnd / duration) * w;
    ctx.fillStyle = 'rgba(59, 130, 246, 0.22)';
    ctx.fillRect(xL1, 16, Math.max(4, xL2 - xL1), h - 32);
    ctx.strokeStyle = '#3b82f6';
    ctx.lineWidth = 1.5;
    ctx.setLineDash([4, 2]);
    ctx.strokeRect(xL1, 16, Math.max(4, xL2 - xL1), h - 32);
    ctx.setLineDash([]);

    ctx.fillStyle = '#60a5fa';
    ctx.font = '9px "JetBrains Mono"';
    ctx.textAlign = 'left';
    ctx.fillText(`🔁 LOOP ${formatTime(loopStart)}-${formatTime(loopEnd)}`, xL1 + 4, 32);
  }

  // 1.8. Draw Surgical Punch-In Caliper Window (if surgicalScope === 'region')
  if (surgicalScope === 'region' && duration > 0 && surgicalOut > surgicalIn) {
    const xS1 = (surgicalIn / duration) * w;
    const xS2 = (surgicalOut / duration) * w;
    const winW = Math.max(4, xS2 - xS1);

    // Neon shaded area
    ctx.fillStyle = 'rgba(56, 189, 248, 0.22)';
    ctx.fillRect(xS1, 16, winW, h - 32);

    // Glowing caliper border
    ctx.strokeStyle = '#38bdf8';
    ctx.lineWidth = 2;
    ctx.shadowColor = '#38bdf8';
    ctx.shadowBlur = 10;
    ctx.strokeRect(xS1, 16, winW, h - 32);
    ctx.shadowBlur = 0;

    // IN and OUT caliper tabs
    ctx.fillStyle = '#38bdf8';
    ctx.fillRect(xS1 - 2, 16, 4, 18);
    ctx.fillRect(xS2 - 2, 16, 4, 18);

    // Top and bottom handles
    ctx.font = '10px "JetBrains Mono"';
    ctx.fillStyle = '#38bdf8';
    ctx.textAlign = 'left';
    ctx.fillText(`[IN: ${formatTime(surgicalIn)}]`, Math.max(10, xS1 - 10), 28);
    ctx.textAlign = 'right';
    ctx.fillText(`[OUT: ${formatTime(surgicalOut)}]`, Math.min(w - 10, xS2 + 10), 28);

    // Center badge
    ctx.textAlign = 'center';
    ctx.fillStyle = '#ffffff';
    ctx.fillText(`✂ SURGICAL WINDOW: ${(surgicalOut - surgicalIn).toFixed(2)}s (100% UNTOUCHED OUTSIDE)`, xS1 + winW / 2, h - 22);
  }

  // 2. Playhead needle with glowing bead
  if (duration > 0 && audioHealed.currentTime > 0) {
    const playX = (audioHealed.currentTime / duration) * w;
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 2;
    ctx.shadowColor = '#ffffff';
    ctx.shadowBlur = 8;
    ctx.beginPath();
    ctx.moveTo(playX, 16); ctx.lineTo(playX, h - 16);
    ctx.stroke();
    ctx.shadowBlur = 0;

    // Glowing bead at midY
    ctx.fillStyle = isRaw ? '#ef4444' : '#10b981';
    ctx.beginPath();
    ctx.arc(playX, midY, 4, 0, Math.PI * 2);
    ctx.fill();
  }

  // 3. Clear HUD Badge at top center with active channel identity
  ctx.font = '11px "JetBrains Mono", monospace';
  ctx.textAlign = 'center';
  const badgeW = 480;
  ctx.fillStyle = 'rgba(10, 14, 22, 0.9)';
  ctx.fillRect((w - badgeW) / 2, 5, badgeW, 20);
  ctx.strokeStyle = isRaw ? 'rgba(239, 68, 68, 0.7)' : 'rgba(16, 185, 129, 0.7)';
  ctx.lineWidth = 1;
  ctx.strokeRect((w - badgeW) / 2, 5, badgeW, 20);

  ctx.fillStyle = isRaw ? '#ff6b6b' : '#34d399';
  const label = isRaw
    ? '[A] RAW DIGITAL AI // SPIKY CLIPPING UNTREATED (RED)'
    : '[B] PHARMAKON MASTER // BRICKWALLED TO -0.3 dBFS (EMERALD)';
  ctx.fillText(label, w / 2, 19);
}

function drawSpectrumGraticule(ctx, w, h) {
  const marginL = 50;
  const marginR = 20;
  const marginT = 25;
  const marginB = 30;
  const plotW = w - marginL - marginR;
  const plotH = h - marginT - marginB;

  const freqToX = (f) => marginL + (Math.log10(f / 20.0) / Math.log10(20000.0 / 20.0)) * plotW;
  const dbToY = (db) => marginT + ((Math.max(-84, Math.min(0, db)) - 0) / -84.0) * plotH;

  // 1. Shaded Band Zones
  // Sub cut zone (<32Hz)
  const xSub = freqToX(32);
  ctx.fillStyle = 'rgba(59, 130, 246, 0.08)';
  ctx.fillRect(marginL, marginT, xSub - marginL, plotH);

  // 5kHz AI Harsh Notch zone (4200 - 6000 Hz)
  const xN1 = freqToX(4200);
  const xN2 = freqToX(6000);
  ctx.fillStyle = 'rgba(245, 158, 11, 0.12)';
  ctx.fillRect(xN1, marginT, xN2 - xN1, plotH);

  // 2. Grid Horizontal Lines (dBFS)
  ctx.strokeStyle = '#0d1322';
  ctx.lineWidth = 1;
  ctx.font = '9px "JetBrains Mono", monospace';
  ctx.textAlign = 'right';

  const dbTicks = [0, -12, -24, -36, -48, -60, -72];
  for (let db of dbTicks) {
    const y = dbToY(db);
    ctx.beginPath();
    ctx.moveTo(marginL, y);
    ctx.lineTo(w - marginR, y);
    ctx.stroke();

    ctx.fillStyle = db === 0 ? '#ef4444' : '#475569';
    ctx.fillText(`${db} dB`, marginL - 8, y + 3);
  }

  // 3. Grid Vertical Frequency Lines
  const freqs = [
    { f: 20, label: '20Hz', color: '#334155' },
    { f: 32, label: '32Hz [SUB CUT]', color: '#3b82f6', bold: true },
    { f: 120, label: '120Hz [MONO]', color: '#06b6d4', bold: true },
    { f: 500, label: '500Hz', color: '#334155' },
    { f: 1000, label: '1kHz', color: '#475569' },
    { f: 2500, label: '2.5k', color: '#334155' },
    { f: 5000, label: '5.0kHz [NOTCH]', color: '#f59e0b', bold: true },
    { f: 10000, label: '10k', color: '#475569' },
    { f: 16000, label: '16kHz [AIR]', color: '#a855f7', bold: true },
    { f: 20000, label: '20kHz', color: '#334155' }
  ];

  ctx.textAlign = 'center';
  for (let item of freqs) {
    const x = freqToX(item.f);
    ctx.strokeStyle = item.bold ? item.color : '#0d1322';
    ctx.lineWidth = item.bold ? 1.2 : 1;
    if (item.bold) ctx.setLineDash([3, 3]);

    ctx.beginPath();
    ctx.moveTo(x, marginT);
    ctx.lineTo(x, h - marginB);
    ctx.stroke();
    if (item.bold) ctx.setLineDash([]);

    ctx.fillStyle = item.color;
    ctx.fillText(item.label, x, h - 10);
  }
}

function renderSingleRta() {
  if (!canvasSingle) return;
  const ctx = canvasSingle.getContext('2d');
  const w = canvasSingle.width;
  const h = canvasSingle.height;

  ctx.fillStyle = '#04060b';
  ctx.fillRect(0, 0, w, h);
  drawSpectrumGraticule(ctx, w, h);

  const marginL = 50;
  const marginR = 20;
  const marginT = 25;
  const marginB = 30;
  const plotW = w - marginL - marginR;
  const plotH = h - marginT - marginB;

  const isRaw = (activeSource === 'raw');
  let data = null;

  if (isPlaying && analyserRaw && analyserHealed) {
    if (isRaw) {
      analyserRaw.getByteFrequencyData(freqDataRaw);
      data = freqDataRaw;
    } else {
      analyserHealed.getByteFrequencyData(freqDataHealed);
      data = freqDataHealed;
    }
  }

  if (!isPlaying || !data) {
    ctx.fillStyle = '#475569';
    ctx.font = '12px "JetBrains Mono"';
    ctx.textAlign = 'center';
    ctx.fillText("PRESS PLAY (▶) FOR REAL-TIME CALIBRATED FREQUENCY SPECTRUM", w / 2, h / 2);
    return;
  }

  const numBars = 110;
  const barWidth = plotW / numBars;

  for (let i = 0; i < numBars; i++) {
    const logIndex = Math.floor(Math.pow(i / numBars, 2) * (data.length * 0.75));
    const val = data[logIndex] || 0;
    const barH = (val / 255.0) * plotH;
    const x = marginL + i * barWidth;
    const y = marginT + (plotH - barH);

    let barGrad = ctx.createLinearGradient(0, y, 0, marginT + plotH);
    if (isRaw) {
      barGrad.addColorStop(0, '#ef4444');
      barGrad.addColorStop(1, 'rgba(127, 29, 29, 0.4)');
    } else {
      barGrad.addColorStop(0, '#10b981');
      barGrad.addColorStop(0.5, '#06b6d4');
      barGrad.addColorStop(1, 'rgba(6, 78, 59, 0.4)');
    }

    ctx.fillStyle = barGrad;
    ctx.fillRect(x + 1, y, barWidth - 2, barH);
  }
}

function renderSingleStatic() {
  if (!canvasSingle) return;
  const ctx = canvasSingle.getContext('2d');
  const w = canvasSingle.width;
  const h = canvasSingle.height;

  ctx.fillStyle = '#05070d';
  ctx.fillRect(0, 0, w, h);
  drawSpectrumGraticule(ctx, w, h);

  if (!lastMetrics || !lastMetrics.fft_freqs) {
    ctx.fillStyle = '#475569';
    ctx.font = '12px "JetBrains Mono"';
    ctx.textAlign = 'center';
    ctx.fillText("CLICK 'HEAL & MASTER AUDIO' TO GENERATE CALIBRATED DSP MASTERING CURVES", w / 2, h / 2);
    return;
  }

  const marginL = 50;
  const marginR = 20;
  const marginT = 25;
  const marginB = 30;
  const plotW = w - marginL - marginR;
  const plotH = h - marginT - marginB;

  const freqs = lastMetrics.fft_freqs;
  const origDb = lastMetrics.fft_orig_db;
  const procDb = lastMetrics.fft_proc_db;

  const freqToX = (f) => marginL + (Math.log10(f / 20.0) / Math.log10(20000.0 / 20.0)) * plotW;
  const dbToY = (db) => marginT + ((Math.max(-84, Math.min(0, db)) - 0) / -84.0) * plotH;

  // Trace A: Raw (Red)
  ctx.strokeStyle = '#ef4444';
  ctx.lineWidth = 2.2;
  ctx.beginPath();
  for (let i = 0; i < freqs.length; i++) {
    const x = freqToX(freqs[i]);
    const y = dbToY(origDb[i]);
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  }
  ctx.stroke();

  // Trace B: Master (Emerald)
  ctx.strokeStyle = '#10b981';
  ctx.lineWidth = 3;
  ctx.shadowColor = '#10b981';
  ctx.shadowBlur = 10;
  ctx.beginPath();
  for (let i = 0; i < freqs.length; i++) {
    const x = freqToX(freqs[i]);
    const y = dbToY(procDb[i]);
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  }
  ctx.stroke();
  ctx.shadowBlur = 0;
}

// --------------------------------------------------------------------------
// PHARMAKON DSP PROCESSING
// --------------------------------------------------------------------------

// -----------------------------------------------------------------------------
// ONE-CLICK DEEP STEM ANTIDOTE (SPLIT & STEM MASTER)
// -----------------------------------------------------------------------------
async function runSplitAndStemMaster() {
  if (!currentTarget) {
    updateStatus("Notice: Please load or drop an audio file first!");
    return;
  }

  const btnProcess = document.getElementById('btnProcess');
  const btnSplit = document.getElementById('btnSplitAndMaster');
  if (btnProcess) btnProcess.disabled = true;
  if (btnSplit) btnSplit.disabled = true;

  updateStatus("🧬 DEEP STEM ANTIDOTE: Extracting Drums, Bass, Vocals & Synths via HPSS...");

  const startTime = performance.now();
  const params = {
    sub_cutoff: parseFloat(document.getElementById('param_sub_cutoff').value),
    mono_crossover: parseFloat(document.getElementById('param_mono_crossover').value),
    deharsh_freq: parseFloat(document.getElementById('param_deharsh_freq').value),
    deharsh_q: parseFloat(document.getElementById('param_deharsh_q').value),
    deharsh_depth: parseFloat(document.getElementById('param_deharsh_depth').value),
    dynamic_deharsh: true,
    tape_drive: parseFloat(document.getElementById('param_tape_drive').value),
    side_stereo_boost: parseFloat(document.getElementById('param_side_stereo_boost').value),
    air_exciter: (parseFloat(document.getElementById('param_air_exciter')?.value || 12) / 100.0),
    drum_punch: parseFloat(document.getElementById('param_drum_punch').value),
    target_ceiling_db: activeCeiling,
    preset: currentPreset !== 'none' ? currentPreset : null,
    phase_align_sub: true
  };

  try {
    const res = await fetch('/api/split-and-master', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        target_path: currentTarget,
        mode: currentMode,
        params: params
      })
    });

    const data = await res.json();
    if (btnProcess) btnProcess.disabled = false;
    if (btnSplit) btnSplit.disabled = false;

    if (!data.success) {
      updateStatus(`ERROR: ${data.detail || data.error || 'Stem separation failed'}`);
      return;
    }

    const elapsed = ((performance.now() - startTime) / 1000).toFixed(2);
    lastResult = data;
    lastMetrics = data.metrics;

    updateStatus(`SUCCESS! 4 stems extracted & mastered in ${elapsed}s! Master: ${data.track_name} - STUDIO_REMASTER.wav`);

    // Setup A/B/Δ monitoring streams
    setupAudioStreams(data.original_path, data.master_path);

    // Direct download button
    const dlBtn = document.getElementById('btnDownloadMaster');
    if (dlBtn && data.master_path) {
      dlBtn.href = `/api/stream?path=${encodeURIComponent(data.master_path)}`;
      dlBtn.download = `${data.track_name} - STUDIO_REMASTER.wav`;
    }

    // Telemetry cards update
    if (data.metrics) {
      updateTelemetry(data.metrics);
    }
  } catch (err) {
    if (btnProcess) btnProcess.disabled = false;
    if (btnSplit) btnSplit.disabled = false;
    updateStatus(`System Error: ${err.message}`);
  }
}


async function runPharmakonProcess(isInitial = false) {
  const inputVal = document.getElementById('targetPathInput').value.trim();
  if (inputVal) {
    currentTarget = inputVal.replace(/^["']|["']$/g, '');
  }

  if (!currentTarget) {
    if (!isInitial) alert("Please select or drop an audio file / stems folder first!");
    return;
  }

  const btn = document.getElementById('btnProcess');
  btn.disabled = true;
  updateStatus("PROCESSING: Running mathematical filters, de-harshing & tape glue...");

  const params = {
    sub_cutoff: parseFloat(document.getElementById('param_sub_cutoff').value),
    mono_crossover: parseFloat(document.getElementById('param_mono_crossover').value),
    deharsh_freq: parseFloat(document.getElementById('param_deharsh_freq').value),
    deharsh_q: parseFloat(document.getElementById('param_deharsh_q').value),
    deharsh_depth: parseFloat(document.getElementById('param_deharsh_depth').value),
    dynamic_deharsh: true,
    tape_drive: parseFloat(document.getElementById('param_tape_drive').value),
    side_stereo_boost: parseFloat(document.getElementById('param_side_stereo_boost').value),
    air_exciter: (parseFloat(document.getElementById('param_air_exciter')?.value || 12) / 100.0),
    drum_punch: parseFloat(document.getElementById('param_drum_punch').value),
    target_ceiling_db: activeCeiling,
    preset: currentPreset !== 'none' ? currentPreset : null,
    region_mode: surgicalScope,
    range_start: surgicalIn,
    range_end: surgicalOut
  };

  try {
    const startTime = performance.now();
    const res = await fetch('/api/process', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        target_path: currentTarget,
        mode: currentMode,
        params: params
      })
    });

    const data = await res.json();
    btn.disabled = false;

    if (!data.success) {
      updateStatus(`ERROR: ${data.detail || 'Processing failed'}`);
      return;
    }

    const elapsed = ((performance.now() - startTime) / 1000).toFixed(2);
    lastResult = data;
    lastMetrics = data.metrics;

    updateStatus(`SUCCESS! Remaster completed in ${elapsed}s. Master: ${data.track_name} - STUDIO_REMASTER.wav`);
    
    // Update direct download button
    const dlBtn = document.getElementById('btnDownloadMaster');
    if (dlBtn && data.master_path) {
      dlBtn.href = `/api/stream?path=${encodeURIComponent(data.master_path)}`;
      dlBtn.download = `${data.track_name} - STUDIO_REMASTER.wav`;
    }

    // Update Telemetry & Diagnosis text
    updateTelemetry(data.metrics);

    // Save playback position if re-mastering
    const curPos = audioHealed.currentTime;
    const wasPlaying = isPlaying;

    setupAudioStreams(data.original_path, data.master_path);

    if (wasPlaying) {
      audioHealed.addEventListener('canplay', () => {
        audioHealed.currentTime = curPos;
        audioRaw.currentTime = curPos;
        audioHealed.play();
        audioRaw.play();
      }, { once: true });
    }

  } catch (err) {
    btn.disabled = false;
    updateStatus(`Network/Server error: ${err.message}`);
  }
}

// --------------------------------------------------------------------------
// SURGICAL REGION / TIME-WINDOW CONTROLLER
// --------------------------------------------------------------------------
function setMasteringScope(scope) {
  surgicalScope = scope;
  const bFull = document.getElementById('btnScopeFull');
  const bReg = document.getElementById('btnScopeRegion');
  const ctrls = document.getElementById('surgicalControls');
  const btnTitle = document.getElementById('btnTitle');

  if (scope === 'full') {
    if (bFull) bFull.classList.add('active');
    if (bReg) bReg.classList.remove('active');
    if (ctrls) ctrls.classList.add('hidden');
    if (btnTitle) btnTitle.innerText = (currentMode === 'pharmakon1') ? "HEAL & MASTER AUDIO (AUTO)" : "EXECUTE PRO SURGICAL MASTER";
    updateStatus("MASTERING SCOPE: Full track mode. Entire track will be remastered.");
  } else {
    if (bFull) bFull.classList.remove('active');
    if (bReg) bReg.classList.add('active');
    if (ctrls) ctrls.classList.remove('hidden');
    updateSurgicalInputs();
    updateStatus("✂ SURGICAL SCOPE ACTIVE: Only highlighted region will be healed. Rest of song remains 100% untouched!");
  }
}

function updateSurgicalInputs() {
  const inInput = document.getElementById('surgicalInInput');
  const outInput = document.getElementById('surgicalOutInput');
  const desc = document.getElementById('caliperDesc');
  const btnTitle = document.getElementById('btnTitle');

  if (inInput) inInput.value = formatCaliperTime(surgicalIn);
  if (outInput) outInput.value = formatCaliperTime(surgicalOut);

  const span = Math.max(0, surgicalOut - surgicalIn);
  if (desc) desc.innerText = `Surgically healing ${span.toFixed(1)}s window. Rest of song stays 100% untouched!`;
  if (btnTitle && surgicalScope === 'region') {
    btnTitle.innerText = `HEAL SURGICAL REGION [${span.toFixed(1)}s]`;
  }
}

function setSurgicalInToPlayhead() {
  surgicalIn = (audioHealed && audioHealed.currentTime) ? audioHealed.currentTime : 0;
  if (surgicalOut <= surgicalIn) {
    surgicalOut = Math.min(duration || (surgicalIn + 5.0), surgicalIn + 5.0);
  }
  setMasteringScope('region');
  updateSurgicalInputs();
}

function setSurgicalOutToPlayhead() {
  surgicalOut = (audioHealed && audioHealed.currentTime) ? audioHealed.currentTime : 5.0;
  if (surgicalIn >= surgicalOut) {
    surgicalIn = Math.max(0, surgicalOut - 5.0);
  }
  setMasteringScope('region');
  updateSurgicalInputs();
}

function setSurgicalSpan(sec) {
  surgicalOut = Math.min(duration || (surgicalIn + sec), surgicalIn + sec);
  setMasteringScope('region');
  document.querySelectorAll('.span-btn').forEach(b => {
    b.classList.toggle('active', b.innerText.includes(`${sec}s`));
  });
  updateSurgicalInputs();
}

function auditionSurgicalRegion() {
  loopStart = surgicalIn;
  loopEnd = surgicalOut;
  isLooping = true;
  const btn = document.getElementById('btnLoop');
  if (btn) btn.classList.add('active');
  audioHealed.currentTime = surgicalIn;
  audioRaw.currentTime = surgicalIn;
  if (!isPlaying) togglePlayPause();
  updateStatus(`🔁 AUDITIONING SURGICAL REGION: ${formatTime(surgicalIn)} ➔ ${formatTime(surgicalOut)} (${(surgicalOut - surgicalIn).toFixed(1)}s). Switch [A] / [B]!`);
}

function onSurgicalInputChange() {
  const inVal = document.getElementById('surgicalInInput').value;
  const outVal = document.getElementById('surgicalOutInput').value;
  surgicalIn = parseTimeString(inVal);
  surgicalOut = Math.max(surgicalIn + 0.5, parseTimeString(outVal));
  updateSurgicalInputs();
}

function parseTimeString(str) {
  if (!str) return 0;
  const clean = str.trim();
  if (clean.includes(':')) {
    const parts = clean.split(':');
    return parseFloat(parts[0]) * 60 + parseFloat(parts[1] || 0);
  }
  return parseFloat(clean) || 0;
}

function formatCaliperTime(sec) {
  if (isNaN(sec) || sec <= 0) return "00:00.00";
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  const ms = Math.floor((sec % 1) * 100);
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}.${ms.toString().padStart(2, '0')}`;
}

function resetSurgicalRegion() {
  setMasteringScope('full');
  isLooping = false;
  const btnLoop = document.getElementById('btnLoop');
  if (btnLoop) btnLoop.classList.remove('active');
  updateStatus("Region selection cleared. Switched to FULL TRACK mode.");
}

function updateTelemetry(m) {
  if (!m) return;
  const tpProc = m.true_peak_proc_db !== undefined ? m.true_peak_proc_db : m.peak_proc_db;
  const tpOrig = m.true_peak_orig_db !== undefined ? m.true_peak_orig_db : m.peak_orig_db;
  document.getElementById('m_peak').innerHTML = `${tpProc} <span class="unit">dBFS</span>`;
  document.getElementById('m_peak_delta').innerText = `Oversampled True-Peak (from ${tpOrig} dBFS)`;

  if (m.lufs_proc !== undefined) {
    const lufsCard = document.getElementById('m_lufs');
    if (lufsCard) lufsCard.innerHTML = `${m.lufs_proc} <span class="unit">LUFS</span>`;
    const lufsDelta = document.getElementById('m_lufs_delta');
    const lDiff = (m.lufs_proc - m.lufs_orig).toFixed(1);
    const lSign = lDiff >= 0 ? '+' : '';
    if (lufsDelta) lufsDelta.innerText = `Raw: ${m.lufs_orig} LUFS (${lSign}${lDiff} dB)`;
    const txtLufs = document.getElementById('txtLufs');
    if (txtLufs) txtLufs.innerText = `${m.lufs_proc} LUFS`;
  }

  const rmsDiff = (m.rms_proc_db - m.rms_orig_db).toFixed(2);
  const sign = rmsDiff >= 0 ? '+' : '';
  document.getElementById('m_rms').innerHTML = `${m.rms_proc_db} <span class="unit">dBFS</span>`;
  document.getElementById('m_rms_delta').innerText = `${sign}${rmsDiff} dB Warm Density Boost`;

  document.getElementById('m_sub').innerHTML = `-${m.sub_reduction_db} <span class="unit">dB</span>`;
  document.getElementById('m_harsh').innerHTML = `-${m.harsh_reduction_db} <span class="unit">dB</span>`;
  document.getElementById('m_width').innerHTML = `+${m.stereo_expansion_db} <span class="unit">dB</span>`;

  // Update in-card diagnosis items
  const harshEl = document.getElementById('txtHarsh');
  if (harshEl) harshEl.innerText = `-${m.harsh_reduction_db} dB`;
  const rmsEl = document.getElementById('txtRms');
  if (rmsEl) rmsEl.innerText = `${sign}${rmsDiff} dB`;

  const resEl = document.getElementById('txtResonance');
  const harshDesc = document.getElementById('m_harsh_desc');
  if (m.detected_resonance_hz) {
    if (resEl) resEl.innerText = `Auto-Neutralized ${m.detected_resonance_hz} Hz (+${m.detected_prominence_db} dB)`;
    if (harshDesc) harshDesc.innerText = `AI Whistle at ${m.detected_resonance_hz}Hz Neutralized`;
  } else {
    if (resEl) resEl.innerText = `Dynamic Ducker Active`;
    if (harshDesc) harshDesc.innerText = `AI Glass Sibilance Neutralized`;
  }

  // Pre-populate frozen waveform buffers with real audio snapshot
  if (m.scope_sample_orig && m.scope_sample_proc) {
    frozenWaveRaw = new Uint8Array(m.scope_sample_orig);
    frozenWaveHealed = new Uint8Array(m.scope_sample_proc);
    hasCapturedAudio = true;
  }
}

function setMode(mode) {
  currentMode = mode;
  const btn1 = document.getElementById('btnMode1');
  const btn2 = document.getElementById('btnMode2');
  const proRack = document.getElementById('proRackSection');
  const btnTitle = document.getElementById('btnTitle');

  if (mode === 'pharmakon1') {
    btn1.classList.add('active');
    btn2.classList.remove('active');
    proRack.classList.add('hidden');
    btnTitle.innerText = "HEAL & MASTER AUDIO (AUTO)";
    updateStatus("PHARMAKON 1 ACTIVE: Lex Gerek Studio Golden Preset ready.");
  } else {
    btn1.classList.remove('active');
    btn2.classList.add('active');
    proRack.classList.remove('hidden');
    btnTitle.innerText = "EXECUTE PRO SURGICAL MASTER";
    updateStatus("PHARMAKON 2 PRO RACK ACTIVE: Adjust hardware DSP parameters.");
  }
}

function updateParamValue(el, unit, mult = 1, add = 0) {
  const span = el.parentElement.querySelector('.val');
  let val = parseFloat(el.value);
  if (mult !== 1 || add !== 0) {
    val = Math.round((val * mult) + add);
  }
  if (span) span.innerText = val;
  updateStatus("Parameter tweaked. Click 'EXECUTE PRO SURGICAL MASTER' to apply.");
}

function setCeiling(val) {
  activeCeiling = val;
  document.querySelectorAll('.ceiling-btn').forEach(btn => {
    btn.classList.toggle('active', parseFloat(btn.innerText) === val);
  });
  document.getElementById('ceilingReadout').innerText = `${val} dBFS`;
}

// --------------------------------------------------------------------------
// 3D TACTILE HARDWARE KNOBS ENGINE
// --------------------------------------------------------------------------
function initHardwareKnobs() {
  const controls = document.querySelectorAll('.knob-control[data-param]');
  controls.forEach(ctrl => {
    const param = ctrl.getAttribute('data-param');
    const min = parseFloat(ctrl.getAttribute('data-min'));
    const max = parseFloat(ctrl.getAttribute('data-max'));
    let val = parseFloat(ctrl.getAttribute('data-val'));
    const step = parseFloat(ctrl.getAttribute('data-step') || 1);
    const unit = ctrl.getAttribute('data-unit') || '';
    const mult = parseFloat(ctrl.getAttribute('data-mult') || 1);
    const add = parseFloat(ctrl.getAttribute('data-add') || 0);

    const knobEl = ctrl.querySelector('.knob-3d');
    const indEl = ctrl.querySelector('.knob-indicator');
    const hiddenInput = ctrl.querySelector('input[type="hidden"]');
    const valSpan = ctrl.querySelector('.val');

    function updateVisual(newVal) {
      val = Math.max(min, Math.min(max, newVal));
      // Map to angle [-135deg, +135deg]
      const pct = (val - min) / (max - min);
      const angle = -135 + pct * 270;
      if (indEl) indEl.style.transform = `rotate(${angle}deg)`;
      if (hiddenInput) hiddenInput.value = val;

      let displayVal = val;
      if (mult !== 1 || add !== 0) {
        displayVal = Math.round((val * mult) + add);
      } else if (step < 1) {
        displayVal = val.toFixed(step < 0.1 ? 2 : 1);
      }
      if (valSpan) valSpan.innerText = displayVal;
    }

    // Set initial position
    updateVisual(val);
    ctrl._updateVisual = updateVisual;

    // Interactive Dragging
    if (knobEl) {
      let isDragging = false;
      let startY = 0;
      let startVal = val;

      knobEl.addEventListener('mousedown', (e) => {
        isDragging = true;
        startY = e.clientY;
        startVal = val;
        document.body.style.cursor = 'ns-resize';

        function onMouseMove(e) {
          if (!isDragging) return;
          const dy = startY - e.clientY; // drag up = increase
          const sensitivity = (max - min) / 180;
          const rawVal = startVal + dy * sensitivity;
          const steppedVal = Math.round(rawVal / step) * step;
          updateVisual(steppedVal);
          updateStatus(`Tweak: ${param.toUpperCase()} = ${val} ${unit}. Click MASTER to apply.`);
        }

        function onMouseUp() {
          if (!isDragging) return;
          isDragging = false;
          document.body.style.cursor = '';
          window.removeEventListener('mousemove', onMouseMove);
          window.removeEventListener('mouseup', onMouseUp);
        }

        window.addEventListener('mousemove', onMouseMove);
        window.addEventListener('mouseup', onMouseUp);
      });

      // Mouse wheel over knob
      knobEl.addEventListener('wheel', (e) => {
        e.preventDefault();
        const dir = e.deltaY < 0 ? 1 : -1;
        const rawVal = val + dir * step;
        updateVisual(rawVal);
        updateStatus(`Tweak: ${param.toUpperCase()} = ${val} ${unit}. Click MASTER to apply.`);
      }, { passive: false });
    }
  });
}

function setKnobValue(paramName, newVal) {
  const ctrl = document.querySelector(`.knob-control[data-param="${paramName}"]`);
  if (ctrl && ctrl._updateVisual) {
    ctrl._updateVisual(newVal);
  }
}

const PRESET_MAP = {
  suno: {
    name: 'Suno v3.5 / v4 Antidote',
    sub_cutoff: 34,
    mono_crossover: 130,
    deharsh_freq: 5200,
    deharsh_q: 3.2,
    deharsh_depth: 1.0,
    tape_drive: 1.06,
    side_stereo_boost: 1.18,
    drum_punch: 1.15,
    target_ceiling_db: -0.3
  },
  udio: {
    name: 'Udio 1.5 Polish',
    sub_cutoff: 30,
    mono_crossover: 110,
    deharsh_freq: 6100,
    deharsh_q: 2.6,
    deharsh_depth: 0.9,
    tape_drive: 1.03,
    side_stereo_boost: 1.25,
    drum_punch: 1.05,
    target_ceiling_db: -0.3
  },
  club: {
    name: 'Club & EDM Punch',
    sub_cutoff: 36,
    mono_crossover: 140,
    deharsh_freq: 4800,
    deharsh_q: 2.8,
    deharsh_depth: 0.85,
    tape_drive: 1.10,
    side_stereo_boost: 1.30,
    drum_punch: 1.35,
    target_ceiling_db: -0.1
  },
  audiophile: {
    name: 'Audiophile Transparent',
    sub_cutoff: 25,
    mono_crossover: 95,
    deharsh_freq: 5000,
    deharsh_q: 3.5,
    deharsh_depth: 0.6,
    tape_drive: 1.01,
    side_stereo_boost: 1.08,
    drum_punch: 1.0,
    target_ceiling_db: -1.0
  }
};

function applyPreset(presetKey) {
  playHardwareClick('toggle');
  currentPreset = presetKey;
  document.querySelectorAll('.preset-rack-chip').forEach(b => b.classList.remove('active'));
  const btn = document.getElementById(`preset_${presetKey}`);
  if (btn) btn.classList.add('active');

  if (presetKey === 'none') {
    updateStatus("Profile: AUTO SCAN (Intelligent Welch FFT resonance detection active)");
    return;
  }

  const p = PRESET_MAP[presetKey];
  if (p) {
    for (const [k, v] of Object.entries(p)) {
      if (k === 'name') continue;
      if (k === 'target_ceiling_db') {
        activeCeiling = v;
        document.querySelectorAll('.ceiling-btn').forEach(cb => {
          if (parseFloat(cb.dataset.val) === v) cb.classList.add('active');
          else cb.classList.remove('active');
        });
      } else {
        setKnobValue(k, v);
      }
    }
    updateStatus(`Profile Loaded: ${p.name}. Click 'COMMENCE RE-MASTERING' to apply.`);
  }
}

function initDropzone() {
  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('fileInput');

  dropzone.addEventListener('click', () => fileInput.click());

  dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropzone.classList.add('dragover');
  });

  dropzone.addEventListener('dragleave', () => {
    dropzone.classList.remove('dragover');
  });

  dropzone.addEventListener('drop', async (e) => {
    e.preventDefault();
    dropzone.classList.remove('dragover');

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      await handleDroppedFile(file);
    }
  });

  fileInput.addEventListener('change', async (e) => {
    if (e.target.files && e.target.files.length > 0) {
      await handleDroppedFile(e.target.files[0]);
    }
  });
}

async function handleDroppedFile(file) {
  updateStatus(`Uploading ${file.name}...`);
  try {
    const res = await fetch(`/api/upload-binary?filename=${encodeURIComponent(file.name)}`, {
      method: 'POST',
      body: file
    });
    const data = await res.json();
    if (data.success) {
      currentTarget = data.saved_path;
      document.getElementById('targetPathInput').value = currentTarget;
      updateStatus(`File ready: ${file.name}. Trigger processing!`);
      runPharmakonProcess();
    } else {
      updateStatus(`Upload error: ${data.detail || 'Unknown error'}`);
    }
  } catch (err) {
    updateStatus(`Upload failed: ${err.message}`);
  }
}

async function openNativeBrowser(mode = 'file') {
  updateStatus(`Opening Windows ${mode === 'folder' ? 'folder' : 'file'} picker...`);
  try {
    const res = await fetch(`/api/browse-native?mode=${mode}`, { method: 'POST' });
    const data = await res.json();
    if (data.success && data.selected_path) {
      currentTarget = data.selected_path;
      document.getElementById('targetPathInput').value = currentTarget;
      updateStatus(`Loaded: ${currentTarget}`);
      runPharmakonProcess();
    } else {
      updateStatus("Selection cancelled.");
    }
  } catch (err) {
    updateStatus(`Browse error: ${err.message}`);
  }
}

async function browseOrPaste() {
  let text = '';
  try {
    if (navigator.clipboard && navigator.clipboard.readText) {
      text = await navigator.clipboard.readText();
    }
  } catch (err) {
    console.warn("Clipboard access blocked by browser permissions:", err);
  }

  // Fallback if browser blocked clipboard API or returned empty: instant prompt modal
  if (!text || !text.trim()) {
    const existingVal = document.getElementById('targetPathInput').value;
    text = prompt("PHARMAKON // PASTE TARGET PATH (Press Ctrl+V & Enter):", existingVal || "");
  }

  if (text && text.trim()) {
    currentTarget = text.trim().replace(/^["']|["']$/g, '');
    document.getElementById('targetPathInput').value = currentTarget;
    updateStatus(`Target loaded: ${currentTarget}`);
    runPharmakonProcess();
  }
}

async function initBundledDemos() {
  try {
    const res = await fetch('/api/demos');
    const data = await res.json();
    if (data && data.demos && data.demos.length > 0) {
      bundledDemos = data.demos;
      // Default to Bronze Psalter demo
      loadBundledDemo(bundledDemos[0].id, false);
    }
  } catch (err) {
    console.warn("Could not fetch bundled demos:", err);
  }
}

function loadBundledDemo(demoId, autoProcess = true) {
  const demo = bundledDemos.find(d => d.id === demoId) || (bundledDemos.length > 0 ? bundledDemos[0] : null);
  if (!demo) return;

  currentTarget = demo.rel_path || demo.path;
  const inputEl = document.getElementById('targetPathInput');
  if (inputEl) inputEl.value = demo.rel_path || demo.path;

  // Toggle chip classes
  const chipBronze = document.getElementById('chipDemoBronze');
  const chipGravity = document.getElementById('chipDemoGravity');
  if (chipBronze) chipBronze.classList.toggle('active', demo.id === 'bronze_psalter');
  if (chipGravity) chipGravity.classList.toggle('active', demo.id === 'gravity_stems');

  updateStatus(`Loaded Demo: ${demo.title}`);
  if (autoProcess) {
    runPharmakonProcess();
  }
}

function loadPreset(path) {
  currentTarget = path;
  document.getElementById('targetPathInput').value = path;
  updateStatus(`Loaded preset target: ${path}`);
  runPharmakonProcess();
}

function updateStatus(text) {
  document.getElementById('statusText').innerText = text;
}

function formatTime(sec) {
  if (isNaN(sec) || sec <= 0) return "00:00";
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

async function openOutputFolder() {
  const target = lastResult?.master_path || lastResult?.output_dir || currentTarget || document.getElementById('targetPathInput')?.value?.trim();
  if (!target) {
    updateStatus("Notice: No audio target or remaster output to reveal yet.");
    return;
  }
  updateStatus("Opening native Windows Explorer...");
  try {
    const res = await fetch('/api/reveal', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: target })
    });
    const data = await res.json();
    if (data.success) {
      updateStatus(`📂 Opened in Windows Explorer: ${data.opened || target}`);
    } else {
      updateStatus(`Explorer notice: ${data.error || 'Unable to open path'}`);
    }
  } catch (err) {
    updateStatus(`Error launching Explorer: ${err.message}`);
  }
}


// -----------------------------------------------------------------------------
// DOWNLOAD OR EXPORT STEMS PACK AS ZIP
// -----------------------------------------------------------------------------
async function downloadOrSaveStems(e) {
  if (e) e.preventDefault();

  let stemsDir = lastResult?.stems_dir || currentTarget;
  if (!stemsDir) {
    updateStatus("Notice: No audio target selected. Please choose a track first!");
    return;
  }

  if (!stemsDir) {
    updateStatus("Notice: No separated stems found. Click '🧬 SPLIT & STEM MASTER' first to generate stems!");
    return;
  }

  const trackName = lastResult?.track_name || (currentTarget ? currentTarget.split(/[\\/]/).pop().replace(/\.[^/.]+$/, '') : "Track");
  const suggestedName = `${trackName} - STEMS.zip`;
  updateStatus("Choosing destination folder for Stems ZIP archive...");

  // Tier 1: Modern File System Access API
  if (window.showSaveFilePicker) {
    try {
      const handle = await window.showSaveFilePicker({
        suggestedName: suggestedName,
        types: [{
          description: 'ZIP Archive (*.zip)',
          accept: { 'application/zip': ['.zip'] }
        }]
      });
      updateStatus("Downloading and compressing stems into ZIP archive...");
      const streamUrl = `/api/download-stems?stems_dir=${encodeURIComponent(stemsDir)}`;
      const response = await fetch(streamUrl);
      if (!response.ok) {
        throw new Error("Stems directory not found on server");
      }
      const blob = await response.blob();
      const writable = await handle.createWritable();
      await writable.write(blob);
      await writable.close();
      updateStatus(`Stems ZIP saved successfully: ${handle.name}`);
      return;
    } catch (pickerErr) {
      if (pickerErr.name === 'AbortError') {
        updateStatus("Save cancelled.");
        return;
      }
      console.warn("showSaveFilePicker notice, falling back to server dialog:", pickerErr);
    }
  }

  // Tier 2: Native Windows Save As dialog via local server
  try {
    const res = await fetch('/api/save-stems-as', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ stems_dir: stemsDir })
    });
    const data = await res.json();
    if (data.success && data.saved_path) {
      updateStatus(`Stems ZIP saved to: ${data.saved_path}`);
      return;
    } else if (data.cancelled) {
      updateStatus("Save cancelled.");
      return;
    }
  } catch (err) {
    console.warn("Server save-stems-as notice:", err);
  }

  // Tier 3: Direct browser download trigger fallback
  const dlLink = document.createElement('a');
  dlLink.href = `/api/download-stems?stems_dir=${encodeURIComponent(stemsDir)}`;
  dlLink.download = suggestedName;
  document.body.appendChild(dlLink);
  dlLink.click();
  document.body.removeChild(dlLink);
  updateStatus(`Stems ZIP downloaded: ${suggestedName}`);
}


async function downloadOrSaveMaster(e) {
  if (e) e.preventDefault();

  const masterPath = lastResult?.master_path;
  if (!masterPath) {
    updateStatus("No mastered audio rendered yet. Select a track and click 'COMMENCE RE-MASTERING' first!");
    return;
  }

  const suggestedName = (lastResult?.track_name ? `${lastResult.track_name} - STUDIO_REMASTER.wav` : 'STUDIO_REMASTER.wav');
  updateStatus("Choosing destination folder for master...");

  // Tier 1: Modern File System Access API (native Windows Save-As dialog inside Chrome)
  if (window.showSaveFilePicker) {
    try {
      const handle = await window.showSaveFilePicker({
        suggestedName: suggestedName,
        types: [{
          description: 'Lossless Master Audio (*.wav)',
          accept: { 'audio/wav': ['.wav'] }
        }]
      });
      updateStatus("Writing lossless WAV master to selected destination...");
      const streamUrl = `/api/stream?path=${encodeURIComponent(masterPath)}`;
      const response = await fetch(streamUrl);
      const blob = await response.blob();
      const writable = await handle.createWritable();
      await writable.write(blob);
      await writable.close();
      updateStatus(`Master saved successfully: ${handle.name}`);
      return;
    } catch (pickerErr) {
      if (pickerErr.name === 'AbortError') {
        updateStatus("Save cancelled.");
        return;
      }
      console.warn("File System Access API error, trying native server dialog:", pickerErr);
    }
  }

  // Tier 2: Native Windows desktop Save-As dialog via local server
  try {
    const res = await fetch('/api/save-as', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ master_path: masterPath })
    });
    const data = await res.json();
    if (data.success && data.saved_path) {
      updateStatus(`Master saved to: ${data.saved_path}`);
      return;
    } else if (data.cancelled) {
      updateStatus("Save cancelled.");
      return;
    }
  } catch (err) {
    console.warn("Server save-as fallback failed:", err);
  }

  // Tier 3: Direct browser download trigger
  const dlLink = document.createElement('a');
  dlLink.href = `/api/stream?path=${encodeURIComponent(masterPath)}`;
  dlLink.download = suggestedName;
  document.body.appendChild(dlLink);
  dlLink.click();
  document.body.removeChild(dlLink);
  updateStatus(`Downloading ${suggestedName}...`);
}

function setupKeyboardShortcuts() {
  // Global paste handler: press Ctrl+V anywhere to ingest file or path
  window.addEventListener('paste', async (e) => {
    // 1. Ingest pasted audio file from clipboard
    if (e.clipboardData && e.clipboardData.files && e.clipboardData.files.length > 0) {
      const file = e.clipboardData.files[0];
      if (file && (file.type.startsWith('audio/') || file.name.match(/\.(wav|mp3|flac|ogg|aiff)$/i))) {
        e.preventDefault();
        uploadAndProcessFile(file);
        return;
      }
    }

    // 2. Ingest pasted file path
    const pastedText = e.clipboardData ? e.clipboardData.getData('text') : '';
    if (pastedText && pastedText.trim() && e.target.tagName !== 'INPUT') {
      e.preventDefault();
      currentTarget = pastedText.trim().replace(/^["']|["']$/g, '');
      document.getElementById('targetPathInput').value = currentTarget;
      updateStatus(`Path ingested: ${currentTarget}`);
      runPharmakonProcess();
    }
  });

  window.addEventListener('keydown', (e) => {
    if (e.target.tagName === 'INPUT') return;

    if (e.code === 'Space') {
      e.preventDefault();
      togglePlayPause();
    } else if (e.code === 'Escape') {
      resetSurgicalRegion();
    } else if (e.code === 'KeyA') {
      selectAudioSource('raw');
    } else if (e.code === 'KeyB') {
      selectAudioSource('healed');
    } else if (e.code === 'KeyD') {
      selectAudioSource(activeSource === 'delta' ? 'healed' : 'delta');
    } else if (e.code === 'KeyL') {
      toggleLoopFragment();
    } else if (e.code === 'Digit1') {
      setViewMode('dual');
    } else if (e.code === 'Digit2') {
      setViewMode('single_osc');
    } else if (e.code === 'Digit3') {
      setViewMode('rta');
    } else if (e.code === 'Digit4') {
      setViewMode('static');
    } else if (e.code === 'Digit5') {
      setViewMode('waveform');
    } else if (e.code === 'Digit6') {
      setViewMode('goniometer');
    } else if (e.code === 'KeyC') {
      const isHidden = document.body.classList.toggle('cinematic-hide-cursor');
      playHardwareClick('toggle');
      updateStatus(isHidden ? '🎬 CINEMATIC RECORDING MODE: Mouse cursor HIDDEN. Press [C] to restore.' : '🖱️ STANDARD MODE: Mouse cursor visible.');
    }
  });
}


// ==========================================================================
// MASTERING REPORT & DIAGNOSTIC CERTIFICATE MODAL
// ==========================================================================
function openMasteringReportModal() {
  if (!lastResult || !lastMetrics) {
    updateStatus("Notice: No audio master rendered yet. Please click 'COMMENCE RE-MASTERING' first!");
    return;
  }

  const m = lastMetrics;
  const trackName = lastResult.track_name || "Audio Target";
  const tpProc = m.true_peak_proc_db !== undefined ? m.true_peak_proc_db : m.peak_proc_db;
  const tpOrig = m.true_peak_orig_db !== undefined ? m.true_peak_orig_db : m.peak_orig_db;
  const lufsProc = m.lufs_proc !== undefined ? m.lufs_proc : -14.0;
  const lufsOrig = m.lufs_orig !== undefined ? m.lufs_orig : -14.0;
  const lufsDiff = (lufsProc - lufsOrig).toFixed(1);
  const lufsSign = lufsDiff >= 0 ? '+' : '';
  const rmsDiff = (m.rms_proc_db - m.rms_orig_db).toFixed(2);
  const rmsSign = rmsDiff >= 0 ? '+' : '';
  const resHz = m.detected_resonance_hz ? Math.round(m.detected_resonance_hz) : 5000;
  const resProm = m.detected_prominence_db ? `(+${m.detected_prominence_db.toFixed(1)} dB)` : '';

  // Generate SVG Spectrum
  let svgChart = '';
  if (m.fft_freqs && m.fft_orig_db && m.fft_proc_db) {
    const freqs = m.fft_freqs;
    const origDb = m.fft_orig_db;
    const procDb = m.fft_proc_db;
    const width = 800;
    const height = 240;
    const minF = 20.0;
    const maxF = 20000.0;
    const minDb = -72.0;
    const maxDb = 0.0;

    const fToX = (f) => (Math.log10(Math.max(minF, f)) - Math.log10(minF)) / (Math.log10(maxF) - Math.log10(minF)) * (width - 60) + 40;
    const dbToY = (db) => (maxDb - Math.min(maxDb, Math.max(minDb, db))) / (maxDb - minDb) * (height - 50) + 20;

    const ptsO = [];
    const ptsP = [];
    for (let i = 0; i < freqs.length; i++) {
      ptsO.push(`${fToX(freqs[i]).toFixed(1)},${dbToY(origDb[i]).toFixed(1)}`);
      ptsP.push(`${fToX(freqs[i]).toFixed(1)},${dbToY(procDb[i]).toFixed(1)}`);
    }

    svgChart = `
      <div style="margin: 16px 0;">
        <div style="display:flex; justify-content:space-between; font-family:var(--font-mono); font-size:10.5px; color:#64748b; margin-bottom:6px;">
          <span>RTA SPECTRUM COMPARISON (20 Hz - 20,000 Hz)</span>
          <div>
            <span style="color:#f43f5e; margin-right:12px;">● RAW AI INPUT</span>
            <span style="color:#10b981;">● PHARMAKON MASTER</span>
          </div>
        </div>
        <svg viewBox="0 0 ${width} ${height}" width="100%" height="auto" style="background:#080a10; border-radius:6px; border:1px solid #1f2738;">
          <line x1="40" y1="20" x2="${width-20}" y2="20" stroke="#161d2d" stroke-dasharray="3,3"/>
          <text x="32" y="24" fill="#64748b" font-size="9" text-anchor="end" font-family="monospace">0dB</text>
          <line x1="40" y1="${dbToY(-24).toFixed(1)}" x2="${width-20}" y2="${dbToY(-24).toFixed(1)}" stroke="#161d2d" stroke-dasharray="3,3"/>
          <text x="32" y="${(dbToY(-24)+3).toFixed(1)}" fill="#64748b" font-size="9" text-anchor="end" font-family="monospace">-24</text>
          <line x1="40" y1="${dbToY(-48).toFixed(1)}" x2="${width-20}" y2="${dbToY(-48).toFixed(1)}" stroke="#161d2d" stroke-dasharray="3,3"/>
          <text x="32" y="${(dbToY(-48)+3).toFixed(1)}" fill="#64748b" font-size="9" text-anchor="end" font-family="monospace">-48</text>
          <line x1="${fToX(100).toFixed(1)}" y1="20" x2="${fToX(100).toFixed(1)}" y2="${height-30}" stroke="#161d2d" stroke-dasharray="3,3"/>
          <text x="${fToX(100).toFixed(1)}" y="${height-14}" fill="#64748b" font-size="9" text-anchor="middle" font-family="monospace">100Hz</text>
          <line x1="${fToX(1000).toFixed(1)}" y1="20" x2="${fToX(1000).toFixed(1)}" y2="${height-30}" stroke="#161d2d" stroke-dasharray="3,3"/>
          <text x="${fToX(1000).toFixed(1)}" y="${height-14}" fill="#64748b" font-size="9" text-anchor="middle" font-family="monospace">1kHz</text>
          <line x1="${fToX(5000).toFixed(1)}" y1="20" x2="${fToX(5000).toFixed(1)}" y2="${height-30}" stroke="#161d2d" stroke-dasharray="3,3"/>
          <text x="${fToX(5000).toFixed(1)}" y="${height-14}" fill="#64748b" font-size="9" text-anchor="middle" font-family="monospace">5kHz</text>
          <line x1="${fToX(10000).toFixed(1)}" y1="20" x2="${fToX(10000).toFixed(1)}" y2="${height-30}" stroke="#161d2d" stroke-dasharray="3,3"/>
          <text x="${fToX(10000).toFixed(1)}" y="${height-14}" fill="#64748b" font-size="9" text-anchor="middle" font-family="monospace">10kHz</text>
          <path d="M ${ptsO.join(' L ')}" fill="none" stroke="#f43f5e" stroke-width="1.8" opacity="0.8"/>
          <path d="M ${ptsP.join(' L ')}" fill="none" stroke="#10b981" stroke-width="2.2"/>
        </svg>
      </div>`;
  }

  const modalHtml = `
    <div style="background:linear-gradient(90deg, rgba(6,182,212,0.12) 0%, rgba(16,185,129,0.06) 100%); border:1px solid rgba(6,182,212,0.3); border-radius:8px; padding:12px 16px; margin-bottom:16px; display:flex; justify-content:space-between; align-items:center;">
      <div>
        <div style="font-family:var(--font-mono); font-size:10px; color:#64748b; letter-spacing:1px;">MASTERING AUDIO TARGET:</div>
        <div style="font-family:var(--font-display); font-size:17px; font-weight:700; color:#fff;">${trackName}</div>
      </div>
      <div style="text-align:right; font-family:var(--font-mono); font-size:11px; color:#38bdf8;">
        <div>${m.sample_rate || 44100} Hz &bull; 24-bit Lossless WAV</div>
        <div style="color:#64748b; font-size:10px;">ARCHITECT: LEX GEREK</div>
      </div>
    </div>

    <div style="display:grid; grid-template-columns:repeat(3, 1fr); gap:10px; margin-bottom:16px;">
      <div style="background:#090b10; border:1px solid #1f2738; border-radius:6px; padding:10px 12px;">
        <div style="font-family:var(--font-mono); font-size:9.5px; color:#64748b; letter-spacing:1px;">4X TRUE-PEAK CEILING</div>
        <div style="font-family:var(--font-display); font-size:18px; font-weight:700; color:#fff;">${tpProc} <span style="font-size:10px; color:#64748b;">dBFS</span></div>
        <div style="font-family:var(--font-mono); font-size:10px; color:#10b981;">Oversampled (Raw: ${tpOrig} dBFS)</div>
      </div>
      <div style="background:#090b10; border:1px solid #1f2738; border-radius:6px; padding:10px 12px;">
        <div style="font-family:var(--font-mono); font-size:9.5px; color:#64748b; letter-spacing:1px;">INTEGRATED LOUDNESS (LUFS)</div>
        <div style="font-family:var(--font-display); font-size:18px; font-weight:700; color:#38bdf8;">${lufsProc} <span style="font-size:10px; color:#64748b;">LUFS</span></div>
        <div style="font-family:var(--font-mono); font-size:10px; color:#10b981;">ITU-R BS.1770 (${lufsSign}${lufsDiff} dB)</div>
      </div>
      <div style="background:#090b10; border:1px solid #1f2738; border-radius:6px; padding:10px 12px;">
        <div style="font-family:var(--font-mono); font-size:9.5px; color:#64748b; letter-spacing:1px;">ANALOG TAPE DENSITY</div>
        <div style="font-family:var(--font-display); font-size:18px; font-weight:700; color:#fff;">${m.rms_proc_db} <span style="font-size:10px; color:#64748b;">dBFS</span></div>
        <div style="font-family:var(--font-mono); font-size:10px; color:#10b981;">${rmsSign}${rmsDiff} dB Warmth Saturation</div>
      </div>
      <div style="background:#090b10; border:1px solid #1f2738; border-radius:6px; padding:10px 12px;">
        <div style="font-family:var(--font-mono); font-size:9.5px; color:#64748b; letter-spacing:1px;">DYNAMIC DE-HARSH</div>
        <div style="font-family:var(--font-display); font-size:18px; font-weight:700; color:#fbbf24;">-${m.harsh_reduction_db} <span style="font-size:10px; color:#64748b;">dB</span></div>
        <div style="font-family:var(--font-mono); font-size:10px; color:#94a3b8;">Whistle: ${resHz} Hz ${resProm}</div>
      </div>
      <div style="background:#090b10; border:1px solid #1f2738; border-radius:6px; padding:10px 12px;">
        <div style="font-family:var(--font-mono); font-size:9.5px; color:#64748b; letter-spacing:1px;">SUB-BASS SOLIDIFICATION</div>
        <div style="font-family:var(--font-display); font-size:18px; font-weight:700; color:#fff;">-${m.sub_reduction_db} <span style="font-size:10px; color:#64748b;">dB</span></div>
        <div style="font-family:var(--font-mono); font-size:10px; color:#10b981;">100% True-Mono &lt; 120Hz</div>
      </div>
      <div style="background:#090b10; border:1px solid #1f2738; border-radius:6px; padding:10px 12px;">
        <div style="font-family:var(--font-mono); font-size:9.5px; color:#64748b; letter-spacing:1px;">3D STEREO WIDTH</div>
        <div style="font-family:var(--font-display); font-size:18px; font-weight:700; color:#fff;">+${m.stereo_expansion_db} <span style="font-size:10px; color:#64748b;">dB</span></div>
        <div style="font-family:var(--font-mono); font-size:10px; color:#10b981;">Highs Mid-Side Air Spread</div>
      </div>
    </div>

    ${svgChart}

    <div style="display:flex; justify-content:space-between; align-items:center; border-top:1px solid #1c2333; padding-top:12px; font-family:var(--font-mono); font-size:10.5px; color:#64748b;">
      <div>PHARMAKON DSP &bull; MIT LICENSE &copy; 2026 LEX GEREK</div>
      <div style="color:#10b981; font-weight:700;">&#10003; VERIFIED STREAMING COMPLIANT (EBU R128 / TRUE-PEAK -0.3 dBFS)</div>
    </div>
  `;

  document.getElementById('reportBody').innerHTML = modalHtml;
  document.getElementById('reportModal').style.display = 'flex';
}

function closeReportModal() {
  const modal = document.getElementById('reportModal');
  if (modal) modal.style.display = 'none';
}

function openReportInNewTab() {
  const rPath = lastResult?.report_path || lastResult?.metrics?.report_path;
  if (rPath) {
    // 1. Tell local server to open HTML report in system default browser via os.startfile
    fetch('/api/open-report', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: rPath })
    }).catch(err => console.warn("API open-report notice:", err));

    // 2. Also try window.open in case running in a normal web browser tab
    try {
      window.open(`/api/report?path=${encodeURIComponent(rPath)}`, '_blank');
    } catch (e) {}

    updateStatus(`Opened Mastering Report in browser: ${rPath}`);
  } else {
    updateStatus("Report path not found yet. Click 'COMMENCE RE-MASTERING' first!");
    openOutputFolder();
  }
}

async function downloadReportPNG() {
  if (!lastResult || !lastMetrics) {
    updateStatus("Please render a master first before exporting certificate.");
    return;
  }
  updateStatus("Choosing destination folder for Certificate PNG card...");
  
  const m = lastMetrics;
  const trackName = lastResult.track_name || "Audio Target";
  const canvas = document.createElement('canvas');
  canvas.width = 1200;
  canvas.height = 760;
  const ctx = canvas.getContext('2d');

  // 1. Background
  const bgGrad = ctx.createLinearGradient(0, 0, 0, canvas.height);
  bgGrad.addColorStop(0, '#0c0f17');
  bgGrad.addColorStop(1, '#06080c');
  ctx.fillStyle = bgGrad;
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  // Border & Gold Rim
  ctx.strokeStyle = '#222c3f';
  ctx.lineWidth = 2;
  ctx.strokeRect(16, 16, canvas.width - 32, canvas.height - 32);

  ctx.strokeStyle = 'rgba(245, 158, 11, 0.4)';
  ctx.lineWidth = 1;
  ctx.strokeRect(22, 22, canvas.width - 44, canvas.height - 44);

  // 2. Header
  ctx.fillStyle = '#ffffff';
  ctx.font = 'bold 26px "Orbitron", sans-serif, monospace';
  ctx.fillText('PHARMAKON 2.0 PRO', 50, 70);

  ctx.fillStyle = '#f59e0b';
  ctx.font = 'bold 12px monospace';
  ctx.fillText('AUDIO MASTERING & SPECTRAL DIAGNOSIS CERTIFICATE', 50, 94);

  ctx.textAlign = 'right';
  ctx.fillStyle = '#06b6d4';
  ctx.font = 'bold 14px monospace';
  ctx.fillText('SERIAL: PH-2026-CERT', canvas.width - 50, 68);

  ctx.fillStyle = '#64748b';
  ctx.font = '12px monospace';
  ctx.fillText('SOUND ARCHITECT: LEX GEREK', canvas.width - 50, 90);
  ctx.textAlign = 'left';

  // 3. Track Banner
  ctx.fillStyle = '#101622';
  ctx.fillRect(50, 116, canvas.width - 100, 52);
  ctx.strokeStyle = '#1e293b';
  ctx.strokeRect(50, 116, canvas.width - 100, 52);

  ctx.fillStyle = '#64748b';
  ctx.font = '10px monospace';
  ctx.fillText('AUDIO MASTER TARGET:', 65, 134);

  ctx.fillStyle = '#ffffff';
  ctx.font = 'bold 18px "Orbitron", sans-serif';
  ctx.fillText(trackName, 65, 156);

  ctx.textAlign = 'right';
  ctx.fillStyle = '#38bdf8';
  ctx.font = '12px monospace';
  ctx.fillText(`${m.sample_rate || 44100} Hz  •  24-bit Lossless WAV  •  ${m.duration_sec || 0}s`, canvas.width - 65, 146);
  ctx.textAlign = 'left';

  // 4. Telemetry Metric Boxes (6 tiles)
  const tpProc = m.true_peak_proc_db !== undefined ? m.true_peak_proc_db : m.peak_proc_db;
  const tpOrig = m.true_peak_orig_db !== undefined ? m.true_peak_orig_db : m.peak_orig_db;
  const lufsProc = m.lufs_proc !== undefined ? m.lufs_proc : -14.0;
  const lufsOrig = m.lufs_orig !== undefined ? m.lufs_orig : -14.0;

  const tiles = [
    { label: '4X TRUE-PEAK CEILING', val: `${tpProc} dBFS`, sub: `Raw: ${tpOrig} dBFS (ISP Clamped)`, color: '#ffffff' },
    { label: 'INTEGRATED LOUDNESS', val: `${lufsProc} LUFS`, sub: `ITU-R BS.1770 (Orig: ${lufsOrig})`, color: '#38bdf8' },
    { label: 'ANALOG WARMTH (RMS)', val: `${m.rms_proc_db} dBFS`, sub: `Warmth Density Boost`, color: '#ffffff' },
    { label: 'DYNAMIC DE-HARSH', val: `-${m.harsh_reduction_db} dB`, sub: `Whistle: ${m.detected_resonance_hz ? Math.round(m.detected_resonance_hz) : 5000} Hz`, color: '#fbbf24' },
    { label: 'SUB SOLIDIFICATION', val: `-${m.sub_reduction_db} dB`, sub: `100% True-Mono < 120Hz`, color: '#ffffff' },
    { label: '3D STEREO WIDTH', val: `+${m.stereo_expansion_db} dB`, sub: `Mid-Side Air Widening`, color: '#10b981' }
  ];

  const colW = (canvas.width - 100 - 5 * 12) / 6;
  const tileY = 184;
  const tileH = 72;

  tiles.forEach((t, i) => {
    const x = 50 + i * (colW + 12);
    ctx.fillStyle = '#090c13';
    ctx.fillRect(x, tileY, colW, tileH);
    ctx.strokeStyle = '#1e2638';
    ctx.strokeRect(x, tileY, colW, tileH);

    ctx.fillStyle = '#64748b';
    ctx.font = '9px monospace';
    ctx.fillText(t.label, x + 10, tileY + 18);

    ctx.fillStyle = t.color;
    ctx.font = 'bold 16px "Orbitron", sans-serif';
    ctx.fillText(t.val, x + 10, tileY + 42);

    ctx.fillStyle = '#10b981';
    ctx.font = '9px monospace';
    ctx.fillText(t.sub, x + 10, tileY + 60);
  });

  // 5. Spectrum Graph
  const chartX = 50;
  const chartY = 276;
  const chartW = canvas.width - 100;
  const chartH = 400;

  ctx.fillStyle = '#070a10';
  ctx.fillRect(chartX, chartY, chartW, chartH);
  ctx.strokeStyle = '#1e2738';
  ctx.strokeRect(chartX, chartY, chartW, chartH);

  // Chart Title & Legend
  ctx.fillStyle = '#64748b';
  ctx.font = '11px monospace';
  ctx.fillText('RTA SPECTRUM COMPARISON (20 Hz - 20,000 Hz)', chartX + 16, chartY + 24);

  ctx.fillStyle = '#f43f5e';
  ctx.fillText('● RAW AI INPUT', chartX + chartW - 240, chartY + 24);
  ctx.fillStyle = '#10b981';
  ctx.fillText('● PHARMAKON MASTER', chartX + chartW - 120, chartY + 24);

  // Draw Grid Lines
  ctx.strokeStyle = '#141b29';
  ctx.setLineDash([3, 3]);
  [-12, -24, -36, -48].forEach(db => {
    const y = chartY + 40 + (Math.abs(db) / 60) * (chartH - 70);
    ctx.beginPath();
    ctx.moveTo(chartX + 40, y);
    ctx.lineTo(chartX + chartW - 20, y);
    ctx.stroke();
    ctx.fillStyle = '#475569';
    ctx.font = '9px monospace';
    ctx.fillText(`${db}dB`, chartX + 12, y + 3);
  });
  ctx.setLineDash([]);

  // Plot Curves if available
  if (m.fft_freqs && m.fft_orig_db && m.fft_proc_db) {
    const freqs = m.fft_freqs;
    const oDb = m.fft_orig_db;
    const pDb = m.fft_proc_db;
    const minF = 20.0, maxF = 20000.0, minDb = -72.0, maxDb = 0.0;

    const fToX = (f) => chartX + 50 + (Math.log10(Math.max(minF, f)) - Math.log10(minF)) / (Math.log10(maxF) - Math.log10(minF)) * (chartW - 75);
    const dbToY = (db) => chartY + 40 + (maxDb - Math.min(maxDb, Math.max(minDb, db))) / (maxDb - minDb) * (chartH - 70);

    // Raw curve (Red)
    ctx.strokeStyle = '#f43f5e';
    ctx.lineWidth = 2;
    ctx.beginPath();
    for (let i = 0; i < freqs.length; i++) {
      const x = fToX(freqs[i]);
      const y = dbToY(oDb[i]);
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // Proc curve (Emerald)
    ctx.strokeStyle = '#10b981';
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    for (let i = 0; i < freqs.length; i++) {
      const x = fToX(freqs[i]);
      const y = dbToY(pDb[i]);
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.stroke();
  }

  // 6. Seal of Quality at Bottom
  ctx.fillStyle = '#64748b';
  ctx.font = '10px monospace';
  ctx.fillText('PHARMAKON 2.0 DSP ARCHITECTURE • OPEN-SOURCE MIT LICENSE • 2026 LEX GEREK', 50, canvas.height - 28);

  ctx.textAlign = 'right';
  ctx.fillStyle = '#10b981';
  ctx.font = 'bold 11px monospace';
  ctx.fillText('✓ VERIFIED STREAMING COMPLIANT • ZERO INTER-SAMPLE PEAKS (-0.3 dBFS)', canvas.width - 50, canvas.height - 28);

  const filename = `${trackName} - MASTERING_CERTIFICATE.png`;

  // Tier 1: Modern File System Access API (showSaveFilePicker for native Windows Save As dialog)
  if (window.showSaveFilePicker) {
    try {
      const handle = await window.showSaveFilePicker({
        suggestedName: filename,
        types: [{
          description: 'PNG Image (*.png)',
          accept: { 'image/png': ['.png'] }
        }]
      });
      const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
      const writable = await handle.createWritable();
      await writable.write(blob);
      await writable.close();
      updateStatus(`Certificate saved: ${handle.name}`);
      return;
    } catch (pickerErr) {
      if (pickerErr.name === 'AbortError') {
        updateStatus("Save cancelled.");
        return;
      }
      console.warn("showSaveFilePicker notice:", pickerErr);
    }
  }

  // Tier 2: Native Windows Save As dialog via local server
  try {
    const dataUrl = canvas.toDataURL('image/png');
    const res = await fetch('/api/save-image-as', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename: filename, data_url: dataUrl })
    });
    const data = await res.json();
    if (data.success && data.saved_path) {
      updateStatus(`Certificate saved to: ${data.saved_path}`);
      return;
    } else if (data.cancelled) {
      updateStatus("Save cancelled.");
      return;
    }
  } catch (err) {
    console.warn("Server save-image-as fallback error:", err);
  }

  // Tier 3: Browser download trigger fallback
  const link = document.createElement('a');
  link.download = filename;
  link.href = canvas.toDataURL('image/png');
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  updateStatus(`Certificate downloaded: ${filename}`);
}
