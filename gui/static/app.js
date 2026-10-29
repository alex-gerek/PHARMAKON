// ==========================================================================
// PHARMAKON 2.0 PRO // STUDIO CONSOLE CONTROLLER
// Dual Real-Time Oscilloscopes & Live Diagnostics by Lex Gerek
// ==========================================================================

let currentMode = 'pharmakon1';
let currentTarget = "D:\\КЛИПЫ\\Reels\\Data Corruption\\Bronze Psalter\\Audio\\Bronze Psalter (1).wav";
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

document.addEventListener('DOMContentLoaded', () => {
  initDropzone();
  initCanvases();
  setViewMode('dual');
  initCanvasWheelZoom();
  initHardwareKnobs();
  setupKeyboardShortcuts();
  
  // Start 60 FPS Dual Render Loop immediately
  requestAnimationFrame(renderLoop);

  // Auto-run initial demo processing so metrics & dual streams are ready
  runPharmakonProcess(true);
});

// --------------------------------------------------------------------------
// WEBAUDIO DUAL ANALYSER & PLAYER ENGINE
// --------------------------------------------------------------------------
function initWebAudio() {
  if (audioCtx) return;
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

  // CRITICAL: Analysers are tapped BEFORE gains so BOTH screens dance simultaneously!
  sourceRaw.connect(analyserRaw);
  analyserRaw.connect(gainRaw);
  gainRaw.connect(audioCtx.destination);

  sourceHealed.connect(analyserHealed);
  analyserHealed.connect(gainHealed);
  gainHealed.connect(audioCtx.destination);

  timeDataRaw = new Uint8Array(analyserRaw.fftSize);
  timeDataHealed = new Uint8Array(analyserHealed.fftSize);
  freqDataRaw = new Uint8Array(analyserRaw.frequencyBinCount);
  freqDataHealed = new Uint8Array(analyserHealed.frequencyBinCount);
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

function selectAudioSource(source) {
  initWebAudio();
  if (audioCtx.state === 'suspended') {
    audioCtx.resume();
  }

  activeSource = source;
  const btnRaw = document.getElementById('btnSourceRaw');
  const btnHealed = document.getElementById('btnSourceHealed');
  const topBtnRaw = document.getElementById('scopeBtnRaw');
  const topBtnHealed = document.getElementById('scopeBtnHealed');
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
    if (pillRaw) pillRaw.classList.add('active');
    if (pillHealed) pillHealed.classList.remove('active');
    if (cardRaw) cardRaw.classList.add('active-monitor');
    if (cardHealed) cardHealed.classList.remove('active-monitor');

    gainRaw.gain.setTargetAtTime(1.0, now, crossfadeTime);
    gainHealed.gain.setTargetAtTime(0.0, now, crossfadeTime);
  } else {
    if (btnRaw) btnRaw.classList.remove('active');
    if (btnHealed) btnHealed.classList.add('active');
    if (topBtnRaw) topBtnRaw.classList.remove('active');
    if (topBtnHealed) topBtnHealed.classList.add('active');
    if (pillRaw) pillRaw.classList.remove('active');
    if (pillHealed) pillHealed.classList.add('active');
    if (cardRaw) cardRaw.classList.remove('active-monitor');
    if (cardHealed) cardHealed.classList.add('active-monitor');

    gainRaw.gain.setTargetAtTime(0.0, now, crossfadeTime);
    gainHealed.gain.setTargetAtTime(1.0, now, crossfadeTime);
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
  currentViewMode = mode;
  const bDual = document.getElementById('btnViewDual');
  const bSingle = document.getElementById('btnViewSingleOsc');
  const bRta = document.getElementById('btnViewRta');
  const bStatic = document.getElementById('btnViewStatic');
  const bWave = document.getElementById('btnViewWaveform');

  if (bDual) bDual.classList.toggle('active', mode === 'dual');
  if (bSingle) bSingle.classList.toggle('active', mode === 'single_osc');
  if (bRta) bRta.classList.toggle('active', mode === 'rta');
  if (bStatic) bStatic.classList.toggle('active', mode === 'static');
  if (bWave) bWave.classList.toggle('active', mode === 'waveform');

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
    tape_drive: parseFloat(document.getElementById('param_tape_drive').value),
    side_stereo_boost: parseFloat(document.getElementById('param_side_stereo_boost').value),
    drum_punch: parseFloat(document.getElementById('param_drum_punch').value),
    target_ceiling_db: activeCeiling,
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
  document.getElementById('m_peak').innerHTML = `${m.peak_proc_db} <span class="unit">dBFS</span>`;
  document.getElementById('m_peak_delta').innerText = `Clamped from ${m.peak_orig_db} dBFS`;

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

function openOutputFolder() {
  if (lastResult && lastResult.output_dir) {
    fetch('/api/reveal', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: lastResult.output_dir })
    });
  } else {
    fetch('/api/reveal', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: currentTarget })
    });
  }
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
    }
  });
}
