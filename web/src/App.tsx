import { useEffect, useRef, useState, useCallback } from 'react';
import * as PIXI from 'pixi.js';
import { Live2DModel } from 'pixi-live2d-display';
import './index.css';

// Register PIXI on window and register Ticker for pixi-live2d-display
(window as any).PIXI = PIXI;
Live2DModel.registerTicker(PIXI.Ticker);

import {
  JIAN_CHARACTER,
  CHARACTERS,
  type CharacterProfile,
  type AssistantEmotion,
  getJianCharacter,
} from './characters';

export { JIAN_CHARACTER, CHARACTERS, getJianCharacter, type CharacterProfile, type AssistantEmotion };

type AppState = 'loading' | 'ready' | 'error';
type ListenState = 'idle' | 'listening' | 'processing' | 'speaking';

// Streaming TTS audio chunk queue player
export class AudioChunkPlayer {
  private ctx: AudioContext;
  private queue: ArrayBuffer[] = [];
  private playing = false;
  private nextTime = 0;
  onEnded?: () => void;
  onChunk?: (rms: number) => void;

  constructor(ctx: AudioContext) {
    this.ctx = ctx;
  }

  async enqueue(chunk: ArrayBuffer) {
    this.queue.push(chunk);
    if (!this.playing) this._pump();
  }

  private async _pump() {
    if (this.queue.length === 0) {
      this.playing = false;
      setTimeout(() => { if (this.queue.length === 0) this.onEnded?.(); }, 80);
      return;
    }
    this.playing = true;
    const chunk = this.queue.shift()!;
    try {
      const buf = await this.ctx.decodeAudioData(chunk.slice(0));
      const src = this.ctx.createBufferSource();
      src.buffer = buf;
      // Analyser for lip sync on streamed chunks
      const analyser = this.ctx.createAnalyser();
      analyser.fftSize = 256;
      src.connect(analyser);
      analyser.connect(this.ctx.destination);
      const td = new Uint8Array(analyser.fftSize);
      const rmsLoop = () => {
        analyser.getByteTimeDomainData(td);
        let s = 0; for (const v of td) s += ((v - 128) / 128) ** 2;
        this.onChunk?.(Math.sqrt(s / td.length));
        if (this.playing) requestAnimationFrame(rmsLoop);
      };
      requestAnimationFrame(rmsLoop);
      const when = Math.max(this.ctx.currentTime, this.nextTime);
      src.start(when);
      this.nextTime = when + buf.duration;
      src.onended = () => this._pump();
    } catch {
      this._pump();
    }
  }

  stop() {
    this.playing = false;
    this.queue = [];
    this.nextTime = 0;
  }
}

// Window Dimensions (un-cropped generous framing)
export const WIN_W = 440;
export const WIN_H = 540;

// Wake Word & Intent Regex Patterns
const WAKE_WORD_PATTERN = /^(?:(?:hey|hi|hello|ok|okay|yo|listen)\s+)?(?:sylphya|friday)\b[,:\s]*/i;
const ANY_WAKE_WORD_PATTERN = /\b(?:sylphya|friday)\b/i;
const WAKE_WORD_CLEAN_PATTERN = /\b(?:sylphya|friday)\b/gi;
const GREETING_REGEX = /^(hi|hello|hey)(\s+(sylphya|friday|there))?$/i;
const WAKE_COMMAND_REGEX = /^(?:(?:hey|hi)?\s*(?:sylphya|friday)[,:\s]*)?(?:wake\s*up|wake)\b/i;
const SLEEP_COMMAND_REGEX = /^(?:(?:hey|hi|hello|ok)?\s*(?:sylphya|friday)[,:\s]*)?(?:(?:go\s+to\s+)?sleep|take\s+a\s+(?:nap|rest)|stop\s+listening|mute\s+yourself|good\s*night)\b/i;

// Safe Electron IPC accessor
function getElectronIpc() {
  if (typeof window === 'undefined') return null;
  const w = window as any;
  if (w.ipcRenderer) return w.ipcRenderer;
  if (typeof w.require === 'function') {
    try {
      const electron = w.require('electron');
      return electron?.ipcRenderer || electron;
    } catch {}
  }
  return null;
}

// Global AudioContext for Lip Sync
let globalAudioCtx: AudioContext | null = null;
const getAudioContext = () => {
  if (!globalAudioCtx) {
    globalAudioCtx = new (window.AudioContext || (window as any).webkitAudioContext)();
  }
  return globalAudioCtx;
};

// Pure in-memory base64 decoder
function base64ToArrayBuffer(base64: string): ArrayBuffer {
  const binaryString = window.atob(base64);
  const len = binaryString.length;
  const bytes = new Uint8Array(len);
  for (let i = 0; i < len; i++) {
    bytes[i] = binaryString.charCodeAt(i);
  }
  return bytes.buffer;
}

// Main App Component
function App() {
  const canvasRef = useRef<HTMLDivElement>(null);
  const appRef = useRef<PIXI.Application | null>(null);
  const modelRef = useRef<any>(null);

  const [state, setState] = useState<AppState>('loading');
  const [errorMsg, setErrorMsg] = useState('');
  const [listenState, setListenState] = useState<ListenState>('idle');
  const [subtitle, setSubtitle] = useState<string | null>(null);

  // Always-On / Hands-Free Wake Word Mode
  const [isAlwaysOn, setIsAlwaysOn] = useState<boolean>(() => {
    try {
      return (
        localStorage.getItem('sylphya_always_on') === 'true' ||
        localStorage.getItem('friday_always_on') === 'true'
      );
    } catch {
      return false;
    }
  });
  const [isInActiveWindow, setIsInActiveWindow] = useState(false);
  const [isSleeping, setIsSleeping] = useState(false);

  const alwaysOnRef = useRef(isAlwaysOn);
  const isSleepingRef = useRef(false);
  const activeConversationUntilRef = useRef<number>(0);
  const restartTimeoutRef = useRef<any>(null);
  const activeWindowTimerRef = useRef<any>(null);
  const startListeningRef = useRef<(() => void) | null>(null);

  const listenStateRef = useRef<ListenState>('idle');
  const emotionRef = useRef<AssistantEmotion>('neutral');
  const emotionIntensityRef = useRef<number>(1.0);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const isRecordingRef = useRef(false);
  const dragRef = useRef({ isDragging: false, startX: 0, startY: 0, winStartX: 0, winStartY: 0, hasMoved: false });

  // WebSocket streaming voice pipeline refs (reserved for real-time streaming)
  // const voiceWsRef = useRef<WebSocket | null>(null);
  // const audioChunkPlayerRef = useRef<AudioChunkPlayer | null>(null);
  // const streamingTranscriptRef = useRef<string>('');

  // Feedback state
  const [lastReplyText, setLastReplyText] = useState<string | null>(null);
  const [showFeedback, setShowFeedback] = useState(false);

  // Speech gesture state: micro-nod accumulator
  const nodPhaseRef = useRef(0);
  const nodTargetRef = useRef(0);
  const nodActiveRef = useRef(false);
  
  // Mathematical Tracking State (Origin: WIN_W / 2, 180)
  const cursorPosRef = useRef({
    x: Math.round(WIN_W / 2),
    y: 180,
    smoothEyeX: 0,
    smoothEyeY: 0,
    smoothAngleX: 0,
    smoothAngleY: 0,
    smoothAngleZ: 0,
    smoothBodyX: 0,
  });

  const emotionTimeoutRef = useRef<any>(null);
  const lipSyncFrameRef = useRef<number | null>(null);
  const lipSyncSourceRef = useRef<AudioBufferSourceNode | null>(null);
  const lipSyncAnalyserRef = useRef<AnalyserNode | null>(null);
  const mouthOpenRef = useRef(0);
  const animTimeRef = useRef(0);
  const lastFrameTimeRef = useRef(0);
  const currentAudioFilenameRef = useRef<string | null>(null);
  const sendToBackendRef = useRef<((msg: string) => Promise<void> | void) | undefined>(undefined);

  const updateEmotion = useCallback((newEmotion: AssistantEmotion, durationMs = 12000) => {
    emotionRef.current = newEmotion;
    if (emotionTimeoutRef.current) {
      clearTimeout(emotionTimeoutRef.current);
      emotionTimeoutRef.current = null;
    }
    if (newEmotion !== 'neutral' && durationMs > 0) {
      emotionTimeoutRef.current = setTimeout(() => {
        emotionRef.current = isSleepingRef.current ? 'sleeping' : 'neutral';
      }, durationMs);
    }
  }, []);

  const subtitleTimeoutRef = useRef<any>(null);

  const showSubtitle = useCallback((text: string | null, autoDismissMs = 5000) => {
    if (subtitleTimeoutRef.current) {
      clearTimeout(subtitleTimeoutRef.current);
      subtitleTimeoutRef.current = null;
    }
    setSubtitle(text);
    if (text && autoDismissMs > 0) {
      subtitleTimeoutRef.current = setTimeout(() => {
        setSubtitle(null);
        subtitleTimeoutRef.current = null;
      }, autoDismissMs);
    }
  }, []);

  // Sync Always-On state with ref and localStorage
  useEffect(() => {
    alwaysOnRef.current = isAlwaysOn;
    try {
      localStorage.setItem('sylphya_always_on', String(isAlwaysOn));
    } catch {}
  }, [isAlwaysOn]);

  // Refreshes the 25-second active conversational follow-up window
  const refreshActiveConversationWindow = useCallback((durationMs = 25000) => {
    activeConversationUntilRef.current = Date.now() + durationMs;
    setIsInActiveWindow(true);
    if (activeWindowTimerRef.current) clearTimeout(activeWindowTimerRef.current);
    activeWindowTimerRef.current = setTimeout(() => {
      setIsInActiveWindow(false);
    }, durationMs);
  }, []);

  // Safely schedules next listening turn if Always-On mode is engaged
  const scheduleRestartListening = useCallback((delay = 400) => {
    if (!alwaysOnRef.current) return;
    if (restartTimeoutRef.current) clearTimeout(restartTimeoutRef.current);
    restartTimeoutRef.current = setTimeout(() => {
      if (
        alwaysOnRef.current &&
        listenStateRef.current === 'idle' &&
        !isRecordingRef.current
      ) {
        startListeningRef.current?.();
      }
    }, delay);
  }, []);

  // Delete spoken audio file from backend after played or cancelled
  const deleteSpokenAudioFile = useCallback((explicitFilename?: string | null) => {
    const filename = explicitFilename || currentAudioFilenameRef.current;
    if (filename) {
      if (currentAudioFilenameRef.current === filename) {
        currentAudioFilenameRef.current = null;
      }
      fetch(`http://localhost:8000/api/audio/${filename}`, { method: 'DELETE' }).catch(() => {});
    }
  }, []);

  // Unified speech tear-down for lip sync, audio sources and mouth positions
  const stopCurrentSpeech = useCallback(() => {
    if (lipSyncFrameRef.current !== null) {
      cancelAnimationFrame(lipSyncFrameRef.current);
      lipSyncFrameRef.current = null;
    }
    if (lipSyncSourceRef.current) {
      try { lipSyncSourceRef.current.stop(); } catch {}
      try { lipSyncSourceRef.current.disconnect(); } catch {}
      lipSyncSourceRef.current = null;
    }
    if (lipSyncAnalyserRef.current) {
      try { lipSyncAnalyserRef.current.disconnect(); } catch {}
      lipSyncAnalyserRef.current = null;
    }
    mouthOpenRef.current = 0;
    if (modelRef.current?.internalModel?.coreModel) {
      try {
        modelRef.current.internalModel.coreModel.setParameterValueById('ParamMouthOpenY', 0);
      } catch {}
    }
    deleteSpokenAudioFile();
  }, [deleteSpokenAudioFile]);

  // Unified helper to reset listening state, emotion and restart Always-On
  const setIdleState = useCallback((emotion: AssistantEmotion = 'neutral', restartDelayMs?: number) => {
    listenStateRef.current = 'idle';
    setListenState('idle');
    updateEmotion(isSleepingRef.current ? 'sleeping' : emotion);
    if (restartDelayMs !== undefined && alwaysOnRef.current) {
      scheduleRestartListening(restartDelayMs);
    }
  }, [scheduleRestartListening, updateEmotion]);

  // Unified wake-up transition from sleep mode
  const wakeUpFromSleep = useCallback(async (customSubtitle?: string, promptToSend?: string) => {
    isSleepingRef.current = false;
    setIsSleeping(false);
    updateEmotion('happy', 15000);
    if (customSubtitle) {
      showSubtitle(customSubtitle, 4000);
    }
    if (promptToSend) {
      await sendToBackendRef.current?.(promptToSend);
    } else if (alwaysOnRef.current && listenStateRef.current === 'idle' && !isRecordingRef.current) {
      scheduleRestartListening(300);
    }
  }, [scheduleRestartListening, showSubtitle, updateEmotion]);

  // Unified sleep transition
  const enterSleepMode = useCallback(async (promptMsg?: string) => {
    console.log('[Sleep Mode] Entering sleep mode');
    isSleepingRef.current = true;
    setIsSleeping(true);
    activeConversationUntilRef.current = 0;
    setIsInActiveWindow(false);
    updateEmotion('sleeping', 0);
    showSubtitle('💤 Sleeping: Say "Hey Sylphya" or tap to wake me', 6000);
    if (promptMsg) {
      await sendToBackendRef.current?.(promptMsg);
    }
  }, [showSubtitle, updateEmotion]);

  // --- Pixel-Perfect Alpha Hit Testing & Seamless Click-Through ---
  const isIgnoringRef = useRef(false);
  const hitPixelBuffer = useRef(new Uint8Array(4));

  const checkHit = useCallback((x: number, y: number): boolean => {
    if (x < 0 || x >= WIN_W || y < 0 || y >= WIN_H) {
      return false;
    }

    try {
      const elem = document.elementFromPoint(x, y);
      if (elem) {
        if (
          elem.tagName === 'BUTTON' ||
          elem.closest('button') ||
          elem.closest('.interactive') ||
          elem.closest('.error-container')
        ) {
          return true;
        }
      }
    } catch {}

    const app = appRef.current;
    if (!app || !app.view) return false;

    const gl = (app.renderer as any)?.gl || (app.view as HTMLCanvasElement)?.getContext('webgl2') || (app.view as HTMLCanvasElement)?.getContext('webgl');
    if (!gl) return false;

    try {
      const bufW = gl.drawingBufferWidth || WIN_W;
      const bufH = gl.drawingBufferHeight || WIN_H;
      const scaleX = bufW / WIN_W;
      const scaleY = bufH / WIN_H;

      const glX = Math.floor(x * scaleX);
      const glY = Math.floor((WIN_H - 1 - y) * scaleY);

      if (glX < 0 || glX >= bufW || glY < 0 || glY >= bufH) {
        return false;
      }

      gl.readPixels(glX, glY, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, hitPixelBuffer.current);
      return hitPixelBuffer.current[3] > 20;
    } catch {
      return false;
    }
  }, []);

  const updateHitTest = useCallback((x: number, y: number) => {
    if (dragRef.current.isDragging) {
      if (isIgnoringRef.current) {
        isIgnoringRef.current = false;
        const ipc = getElectronIpc();
        ipc?.send('set-ignore-mouse-events', false);
      }
      return;
    }

    const isHit = checkHit(x, y);
    const shouldIgnore = !isHit;

    if (canvasRef.current) {
      canvasRef.current.style.cursor = isHit ? 'grab' : 'default';
    }

    if (shouldIgnore !== isIgnoringRef.current) {
      isIgnoringRef.current = shouldIgnore;
      const ipc = getElectronIpc();
      if (ipc) {
        if (shouldIgnore) {
          ipc.send('set-ignore-mouse-events', true, { forward: true });
        } else {
          ipc.send('set-ignore-mouse-events', false);
        }
      }
    }
  }, [checkHit]);

  // --- Live2D Setup & Procedural Animation Loop ---
  const initLive2D = useCallback(async () => {
    if (!canvasRef.current) return;
    const char = JIAN_CHARACTER;

    setState('loading');
    setErrorMsg('');

    try {
      if (appRef.current) {
        appRef.current.destroy(true, { children: true });
        appRef.current = null;
      }

      const app = new PIXI.Application({
        width: WIN_W,
        height: WIN_H,
        backgroundAlpha: 0,
        antialias: true,
        resolution: 1,
        autoDensity: false,
        preserveDrawingBuffer: true,
        sharedTicker: true,
      });

      PIXI.Ticker.shared.start();

      canvasRef.current.innerHTML = '';
      canvasRef.current.appendChild(app.view as unknown as HTMLElement);
      appRef.current = app;

      const model = await Live2DModel.from(char.modelPath, { 
        autoInteract: false, 
        autoUpdate: true,
      } as any);

      if (!appRef.current || app !== appRef.current || !app.screen) {
        model.destroy();
        return;
      }

      modelRef.current = model;

      app.ticker.add(() => {
        if (modelRef.current && modelRef.current.deltaTime === 0) {
          modelRef.current.update(app.ticker.deltaMS);
        }
      });

      const baseWidth = (model as any).internalModel.width || model.width;
      const baseHeight = (model as any).internalModel.height || model.height;
      const scale = Math.min(WIN_W / baseWidth, WIN_H / baseHeight) * char.scaleMultiplier;
      
      model.scale.set(scale);
      model.anchor.set(0.5, 0.5);
      model.x = WIN_W / 2 + char.offsetX;
      model.y = WIN_H / 2 + char.offsetY;
      model.interactive = true;
      app.stage.addChild(model);

      model.on('hit', (hitAreas: string[]) => {
        if (hitAreas.includes('Body') || hitAreas.includes('HitArea') || hitAreas.includes('Head')) {
          if (listenStateRef.current === 'idle') {
            sendToBackendRef.current?.(char.pokeMessage);
          }
        }
      });

      setState('ready');

      // Animation State Caches
      const currentParams: Record<string, number> = {};
      const proceduralState: Record<string, number> = {};

      const updateFace = () => {
        if (!modelRef.current?.internalModel?.coreModel) return;

        const now = performance.now();
        const dt = Math.min((now - (lastFrameTimeRef.current || now)) / 1000, 0.05);
        lastFrameTimeRef.current = now;
        animTimeRef.current += dt;
        const t = animTimeRef.current;

        const activeEmotion = emotionRef.current || 'neutral';
        const baseParams = char.emotionMap[activeEmotion] || char.emotionMap['neutral'];
        const targetParams: Record<string, number> = { ...baseParams };

        // Origin at (WIN_W / 2, 180)
        const dx = cursorPosRef.current.x - (WIN_W / 2);
        const dy = cursorPosRef.current.y - 180;

        const targetEyeX = Math.tanh(dx / 120);
        const targetEyeY = Math.tanh(-dy / 120);
        const targetAngleX = Math.tanh(dx / 220) * 28;
        const targetAngleY = Math.tanh(-dy / 220) * 20;
        const targetAngleZ = Math.tanh(-dx / 280) * 8;
        const targetBodyX = Math.tanh(dx / 320) * 6;

        const kEye = 1 - Math.exp(-14 * dt);
        const kHead = 1 - Math.exp(-8 * dt);
        const c = cursorPosRef.current;
        c.smoothEyeX += (targetEyeX - c.smoothEyeX) * kEye;
        c.smoothEyeY += (targetEyeY - c.smoothEyeY) * kEye;
        c.smoothAngleX += (targetAngleX - c.smoothAngleX) * kHead;
        c.smoothAngleY += (targetAngleY - c.smoothAngleY) * kHead;
        c.smoothAngleZ += (targetAngleZ - c.smoothAngleZ) * kHead;
        c.smoothBodyX += (targetBodyX - c.smoothBodyX) * kHead;

        if (activeEmotion === 'sleeping' || isSleepingRef.current) {
          targetParams.ParamEyeLOpen = 0;
          targetParams.ParamEyeROpen = 0;
          targetParams.ParamEyeBallX = 0;
          targetParams.ParamEyeBallY = 0;
        } else {
          if (targetParams.ParamEyeBallX === undefined) targetParams.ParamEyeBallX = c.smoothEyeX;
          if (targetParams.ParamEyeBallY === undefined) targetParams.ParamEyeBallY = c.smoothEyeY;
        }

        const currState = listenStateRef.current;

        if (currState === 'idle' && activeEmotion !== 'sleeping' && !isSleepingRef.current) {
          const cheerfulBreath = Math.sin(t * 1.5) * 0.05;
          targetParams.ParamMouthForm = Math.min(1, Math.max(0.6, (targetParams.ParamMouthForm ?? 0.85) + cheerfulBreath));
          targetParams.ParamEyeLSmile = Math.min(1, Math.max(0.4, (targetParams.ParamEyeLSmile ?? 0.65) + cheerfulBreath * 0.4));
          targetParams.ParamEyeRSmile = Math.min(1, Math.max(0.4, (targetParams.ParamEyeRSmile ?? 0.65) + cheerfulBreath * 0.4));
          targetParams.ParamSwitch2 = Math.min(1, Math.max(0.2, (targetParams.ParamSwitch2 ?? 0.35) + Math.sin(t * 0.9) * 0.05));
          targetParams.Ear_smile = Math.min(1, Math.max(0.1, (targetParams.Ear_smile ?? 0.25) + Math.sin(t * 0.7) * 0.1));
        }

        if (char.switchIds) {
          for (const sw of char.switchIds) {
            if (targetParams[sw] === undefined) targetParams[sw] = 0;
          }
        }

        const coreModel = modelRef.current.internalModel.coreModel;

        // 1. Emotion & Parameter Blending with intensity scaling and smooth lerp
        const intensity = emotionIntensityRef.current ?? 1.0;
        // Lerp speed: faster for high-intensity emotions, slower for subtle ones
        const lerpSpeed = 0.06 + intensity * 0.12;
        for (const [param, rawTarget] of Object.entries(targetParams)) {
          // Scale emotion params toward neutral at lower intensity (but keep procedural motion params)
          const isEmotionParam = param.startsWith('Param') && !param.startsWith('ParamAngle') && !param.startsWith('ParamBody') && !param.startsWith('ParamChest') && !param.startsWith('ParamHip') && !param.startsWith('ParamShoulder') && !param.startsWith('ParamBreath') && !param.startsWith('ParamMouthOpenY');
          const neutralVal = char.emotionMap['neutral'][param] ?? 0;
          const scaledTarget = isEmotionParam ? neutralVal + (rawTarget - neutralVal) * intensity : rawTarget;
          if (currentParams[param] === undefined) currentParams[param] = scaledTarget;
          currentParams[param] += (scaledTarget - currentParams[param]) * lerpSpeed;
          coreModel.setParameterValueById(param, currentParams[param]);
        }

        if (currState !== 'speaking') {
          mouthOpenRef.current = 0;
          coreModel.setParameterValueById('ParamMouthOpenY', 0);
        }

        // 2. Continuous Breathing
        const isSleep = activeEmotion === 'sleeping' || isSleepingRef.current;
        const breathSpeed = isSleep ? 1.0 : currState === 'speaking' ? 3.5 : currState === 'listening' ? 2.5 : 2.0;
        const breathAmp = isSleep ? 0.25 : currState === 'speaking' ? 0.6 : 0.4;
        const breath = Math.sin(t * breathSpeed) * breathAmp + breathAmp * 0.5;
        coreModel.setParameterValueById('ParamBreath', Math.max(0, breath));

        // 3. State-Specific Procedural Motions
        const applySmoothed = (id: string, target: number, speed = 0.08) => {
          if (proceduralState[id] === undefined) proceduralState[id] = 0;
          proceduralState[id] += (target - proceduralState[id]) * speed;
          coreModel.setParameterValueById(id, proceduralState[id]);
        };

        const mouthEnergy = mouthOpenRef.current;
        let pBodyAngleX = 0;
        let pBodyAngleZ = 0;
        let pAngleX = 0;
        let pAngleY = 0;
        let pAngleZ = 0;
        let pShoulder = 0;

        if (isSleep) {
          pAngleX = 2 + Math.sin(t * 0.8) * 1.5;
          pAngleY = -5;
          pAngleZ = -3 + Math.sin(t * 0.5) * 1.0;
          pBodyAngleX = 1.0;
          pBodyAngleZ = -2.0;
          pShoulder = -0.15;
          coreModel.setParameterValueById('ParamEyeLOpen', 0);
          coreModel.setParameterValueById('ParamEyeROpen', 0);
        } else if (currState === 'speaking') {
          // Micro-nod gesture: brief head dip on sentence boundaries
          const nodOffset = nodActiveRef.current ? nodTargetRef.current * Math.sin(nodPhaseRef.current * Math.PI) : 0;
          nodPhaseRef.current = Math.min(1, nodPhaseRef.current + dt * 4);
          if (!nodActiveRef.current) nodPhaseRef.current = 0;

          // Excitement scales the speaking motion amplitude
          const intensityScale = 0.7 + (emotionIntensityRef.current ?? 1.0) * 0.5;
          pBodyAngleX = (Math.sin(t * 0.8) * 3.5 + Math.sin(t * 1.3) * 1.8 + c.smoothBodyX * 0.5) * intensityScale;
          pBodyAngleZ = Math.sin(t * 0.6 + 1) * 2.5 * intensityScale;
          pAngleX = (Math.sin(t * 1.2) * 3.5 + c.smoothAngleX * 0.6) * intensityScale + nodOffset;
          pAngleY = (Math.sin(t * 1.5) * 4.5 + mouthEnergy * -3.5 + c.smoothAngleY * 0.6) * intensityScale;
          pAngleZ = (Math.sin(t * 0.9 + 0.5) * 3.5 + c.smoothAngleZ * 0.6) * intensityScale;
          pShoulder = mouthEnergy * 0.45 + Math.sin(t * 2) * 0.18;
        } else if (currState === 'listening') {
          pAngleX = 12 + Math.sin(t * 0.5) * 3 + c.smoothAngleX * 0.6;
          pAngleY = -8 + Math.sin(t * 0.7) * 2 + c.smoothAngleY * 0.6;
          pAngleZ = Math.sin(t * 0.4) * 5 + c.smoothAngleZ * 0.6;
          pBodyAngleX = c.smoothBodyX * 0.7;
          pBodyAngleZ = 6 + Math.sin(t * 0.6) * 2;
          pShoulder = 0.25 + Math.sin(t * 0.6) * 0.1;
          coreModel.setParameterValueById('ParamEyeLOpen', 1.2);
          coreModel.setParameterValueById('ParamEyeROpen', 1.2);
        } else {
          pBodyAngleX = Math.sin(t * 0.3) * 2.0 + Math.sin(t * 0.17) * 1.0 + c.smoothBodyX;
          pBodyAngleZ = Math.sin(t * 0.25 + 1) * 1.5 + Math.tanh(-dx / 280) * 3;
          pAngleX = Math.sin(t * 0.2) * 1.5 + c.smoothAngleX;
          pAngleY = Math.sin(t * 0.15) * 1.5 + c.smoothAngleY;
          pAngleZ = Math.sin(t * 0.2) * 2.0 + c.smoothAngleZ;
          pShoulder = Math.sin(t * 2) * 0.1;
        }

        // 4. Apply Procedural Rig Parameters
        applySmoothed('ParamAngleX', pAngleX);
        applySmoothed('ParamAngleY', pAngleY);
        applySmoothed('ParamAngleZ', pAngleZ);
        applySmoothed('ParamChestAngleX', pBodyAngleX * 0.8);
        applySmoothed('ParamChestAngleY', (pAngleY * 0.3) + Math.sin(t * 2) * 0.2);
        applySmoothed('ParamBodyAngleX0', pBodyAngleX * 1.2);
        applySmoothed('ParamBodyAngleY0', pAngleY * 0.4);
        applySmoothed('ParamBodyAngleZ0', pBodyAngleZ * 1.1);
        applySmoothed('ParamHipAngleX0', pBodyAngleX * 0.6);
        applySmoothed('ParamHipAngleZ0', pBodyAngleZ * 0.5);
        applySmoothed('ParamBodyAngleRX', pBodyAngleX * 1.5);
        applySmoothed('ParamBodyAngleRY', pShoulder * 2.0);
        applySmoothed('ParamShoulderAngleX', pBodyAngleX * 0.4);
        applySmoothed('ParamShoulderAngleY', pShoulder * 0.8);

        // Cat Tail & Ears Physics
        const tailBase = currState === 'speaking' ? Math.sin(t * 2.2) * 0.6 + mouthEnergy * 0.4
                       : currState === 'listening' ? Math.sin(t * 1.3) * 0.35
                       : Math.sin(t * 0.8) * 0.25 + (pBodyAngleX * 0.05);
        applySmoothed('Param_Angle_Rotation_1_ArtMesh220', tailBase);

        const earTwitchL = Math.sin(t * 2.5) * 0.15 * (currState === 'speaking' ? (0.5 + mouthEnergy) : 0.4);
        const earTwitchR = Math.sin(t * 2.5 + 1.5) * 0.15 * (currState === 'speaking' ? (0.5 + mouthEnergy) : 0.4);
        applySmoothed('Ear_SR1', earTwitchR);
        applySmoothed('Ear_SL1', earTwitchL);
        if (currState === 'listening') applySmoothed('Ear_smile', 0.7);

        if (modelRef.current) {
          try { modelRef.current.focus(cursorPosRef.current.x, cursorPosRef.current.y); } catch {}
        }
      };

      (model as any).internalModel.on('beforeModelUpdate', updateFace);
      setState('ready');
    } catch (err: any) {
      console.error('Failed to initialize Live2D:', err);
      setErrorMsg(err?.message || 'Unknown error loading the Live2D model.');
      setState('error');
    }
  }, []);

  useEffect(() => {
    initLive2D();
    return () => {
      if (subtitleTimeoutRef.current) {
        clearTimeout(subtitleTimeoutRef.current);
        subtitleTimeoutRef.current = null;
      }
      stopCurrentSpeech();
      if (appRef.current) {
        try { appRef.current.destroy(true, { children: true, texture: true, baseTexture: true }); } catch {}
        appRef.current = null;
        modelRef.current = null;
      }
    };
  }, [initLive2D, stopCurrentSpeech]);

  // --- Feedback submission ---
  const submitFeedback = useCallback(async (positive: boolean) => {
    setShowFeedback(false);
    try {
      await fetch('http://localhost:8000/api/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: lastReplyText, positive }),
      });
    } catch {}
  }, [lastReplyText]);

  // --- Backend Chat, Edge-TTS Audio & Real-Time Lip Sync ---
  const sendToBackend = async (message: string) => {
    if (!message.trim()) return;

    stopCurrentSpeech();
    setShowFeedback(false);

    const cleanMsg = message.trim().toLowerCase().replace(/[^\w\s]/g, '');
    const isGreeting = GREETING_REGEX.test(cleanMsg);

    listenStateRef.current = 'processing';
    setListenState('processing');

    if (isGreeting) {
      showSubtitle('Hello!', 5000);
      updateEmotion('happy', 15000);
    } else {
      updateEmotion('thinking', 0);
    }

    let data: any = null;
    try {
      const response = await fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message }),
      });

      if (!response.ok) throw new Error(`Backend error: ${response.status}`);
      data = await response.json();

      const emotion = (data.emotion || 'happy') as AssistantEmotion;
      const intensity = typeof data.intensity === 'number' ? Math.max(0.1, Math.min(1.0, data.intensity)) : 1.0;
      emotionIntensityRef.current = intensity;
      updateEmotion(emotion, 15000);
      showSubtitle(data.text || (isGreeting ? 'Hello!' : null), 0);
      setLastReplyText(data.text || null);

      if ((!data.audio_base64 && !data.audio_url) || !modelRef.current) {
        setIdleState('happy', 600);
        showSubtitle(data.text || (isGreeting ? 'Hello!' : null), 5000);
        if (alwaysOnRef.current) {
          refreshActiveConversationWindow(25000);
        }
        setShowFeedback(true);
        return;
      }

      // Track filename to ensure it is deleted after being spoken or on interruption
      const audioFilename = data.filename || (data.audio_url ? data.audio_url.split('/').pop()?.split('?')[0] : null);
      currentAudioFilenameRef.current = audioFilename || null;

      const arrayBuffer = data.audio_base64
        ? base64ToArrayBuffer(data.audio_base64)
        : await (await fetch(data.audio_url)).arrayBuffer();

      const audioCtx = getAudioContext();
      if (audioCtx.state === 'suspended') await audioCtx.resume();
      const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);

      const source = audioCtx.createBufferSource();
      source.buffer = audioBuffer;
      lipSyncSourceRef.current = source;

      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 512;
      analyser.smoothingTimeConstant = 0.25;
      source.connect(analyser);
      analyser.connect(audioCtx.destination);
      lipSyncAnalyserRef.current = analyser;

      const timeData = new Uint8Array(analyser.fftSize);
      let running = true;
      let previousMouth = 0;
      let lastTime = performance.now();
      // Speech gesture: schedule micro-nods tied to sentences (every 2.5-4.5s)
      let nextNodAt = audioCtx.currentTime + 1.5 + Math.random() * 2;

      const updateLipSync = (now: number) => {
        if (!running || !modelRef.current) return;
        const coreModel = modelRef.current?.internalModel?.coreModel;
        if (!coreModel) return;

        const deltaTime = Math.min((now - lastTime) / 1000, 0.05);
        lastTime = now;

        analyser.getByteTimeDomainData(timeData);
        let sum = 0;
        for (let i = 0; i < timeData.length; i++) {
          const s = (timeData[i] - 128) / 128;
          sum += s * s;
        }
        const rms = Math.sqrt(sum / timeData.length);
        const normalized = Math.min(1, Math.max(0, rms - 0.01) / 0.12);
        let targetMouth = Math.pow(normalized, 0.75);
        if (targetMouth < 0.06) targetMouth = 0;

        const speed = targetMouth > previousMouth ? 24 : 12;
        const smoothing = 1 - Math.exp(-speed * deltaTime);
        const mouth = previousMouth + (targetMouth - previousMouth) * smoothing;
        previousMouth = mouth;
        mouthOpenRef.current = mouth;

        // Schedule micro-nod gestures during speech
        if (audioCtx.currentTime >= nextNodAt) {
          nodActiveRef.current = true;
          nodTargetRef.current = (Math.random() > 0.5 ? 1 : -1) * (6 + Math.random() * 6);
          nextNodAt = audioCtx.currentTime + 2.0 + Math.random() * 2.5;
          setTimeout(() => { nodActiveRef.current = false; nodTargetRef.current = 0; }, 500);
        }

        coreModel.setParameterValueById('ParamMouthOpenY', mouth);
        lipSyncFrameRef.current = requestAnimationFrame(updateLipSync);
      };

      source.onended = () => {
        running = false;
        nodActiveRef.current = false;
        nodTargetRef.current = 0;
        const smoothlyCloseMouth = () => {
          if (!modelRef.current?.internalModel?.coreModel) return;
          mouthOpenRef.current *= 0.65;
          modelRef.current.internalModel.coreModel.setParameterValueById('ParamMouthOpenY', mouthOpenRef.current);
          if (mouthOpenRef.current > 0.01) {
            requestAnimationFrame(smoothlyCloseMouth);
          } else {
            stopCurrentSpeech();
          }
        };
        smoothlyCloseMouth();

        setIdleState('neutral', 600);
        showSubtitle(data.text || (isGreeting ? 'Hello!' : null), 5000);
        setShowFeedback(true);

        // Delete audio file after being spoken
        const targetFilename = data.filename || (data.audio_url ? data.audio_url.split('/').pop()?.split('?')[0] : null);
        deleteSpokenAudioFile(targetFilename);

        if (alwaysOnRef.current) {
          refreshActiveConversationWindow(25000);
        }
      };

      listenStateRef.current = 'speaking';
      setListenState('speaking');
      source.start(0);
      lipSyncFrameRef.current = requestAnimationFrame(updateLipSync);

    } catch (err) {
      console.error('[Chat/LipSync] Error:', err);
      const targetFilename = data?.filename || (data?.audio_url ? data.audio_url.split('/').pop()?.split('?')[0] : null);
      deleteSpokenAudioFile(targetFilename);
      stopCurrentSpeech();
      setIdleState(isGreeting ? 'happy' : 'concerned', 1000);
      showSubtitle(isGreeting ? 'Hello!' : null, 4000);
    }
  };

  sendToBackendRef.current = sendToBackend;

  // --- Microphone Recording with Voice Activity Detection (VAD) & Wake Words ---
  const startListening = async () => {
    if (isRecordingRef.current || listenStateRef.current === 'speaking') return;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      isRecordingRef.current = true;
      listenStateRef.current = 'listening';
      setListenState('listening');

      const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      mediaRecorderRef.current = mediaRecorder;
      const audioChunks: Blob[] = [];

      const audioContext = new AudioContext();
      const analyser = audioContext.createAnalyser();
      const source = audioContext.createMediaStreamSource(stream);
      source.connect(analyser);
      analyser.fftSize = 512;
      const dataArray = new Uint8Array(analyser.frequencyBinCount);

      let silentFrames = 0;
      let hasSpoken = false;
      const SILENCE_THRESHOLD = 15;
      const SILENCE_FRAMES_TO_STOP = 7;

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunks.push(e.data);
      };

      mediaRecorder.onstop = async () => {
        stream.getTracks().forEach(t => t.stop());
        try { audioContext.close(); } catch {}
        isRecordingRef.current = false;

        if (audioChunks.length === 0 || !hasSpoken) {
          setIdleState('neutral', 200);
          return;
        }

        listenStateRef.current = 'processing';
        setListenState('processing');

        const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });

        try {
          const formData = new FormData();
          formData.append('audio', audioBlob, 'recording.webm');

          const res = await fetch('http://localhost:8000/api/transcribe', {
            method: 'POST',
            body: formData,
          });

          if (!res.ok) throw new Error('Transcription failed');
          const data = await res.json();
          const text = data.text?.trim();

          if (text && text.length > 0) {
            const now = Date.now();
            const hasWakeWord = ANY_WAKE_WORD_PATTERN.test(text);
            const isWakeCommand = WAKE_COMMAND_REGEX.test(text);

            // 1. SLEEPING STATE
            if (isSleepingRef.current) {
              if (hasWakeWord || isWakeCommand) {
                console.log('[Sleep Mode] Woken up by speech:', text);
                const cleanedText = text
                  .replace(WAKE_WORD_PATTERN, '')
                  .replace(WAKE_WORD_CLEAN_PATTERN, '')
                  .replace(WAKE_COMMAND_REGEX, '')
                  .trim();

                if (!cleanedText) {
                  await wakeUpFromSleep(
                    "I'm awake, Sir! What can I do for you?",
                    "The user just woke you up. Give a short, cheerful, wakeful greeting."
                  );
                } else {
                  await wakeUpFromSleep();
                  refreshActiveConversationWindow(25000);
                  await sendToBackend(cleanedText);
                }
              } else {
                console.log('[Sleep Mode] Ignored speech while sleeping:', text);
                setIdleState('sleeping', 300);
              }
              return;
            }

            // 2. AWAKE STATE - Check for Sleep Command
            if (SLEEP_COMMAND_REGEX.test(text)) {
              await enterSleepMode("The user told you to go to sleep or take a rest. Reply softly, charmingly, and say goodnight (1 short sentence).");
              return;
            }

            const inActiveWindow = activeConversationUntilRef.current > now;

            if (!alwaysOnRef.current || inActiveWindow || hasWakeWord) {
              let cleanedText = text;
              if (hasWakeWord) {
                cleanedText = text.replace(WAKE_WORD_PATTERN, '').replace(WAKE_WORD_CLEAN_PATTERN, '').trim();
                if (!cleanedText) cleanedText = 'Hey Sylphya';
              }
              refreshActiveConversationWindow(25000);
              await sendToBackend(cleanedText);
            } else {
              console.log('[Always-On] Background speech ignored (no wake word):', text);
              setIdleState('neutral', 300);
            }
          } else {
            setIdleState('neutral', 300);
          }
        } catch (err) {
          console.error('Transcription error:', err);
          setIdleState('neutral', 500);
        }
      };

      mediaRecorder.start(250);

      const vadInterval = setInterval(() => {
        analyser.getByteFrequencyData(dataArray);
        const volume = dataArray.reduce((a, b) => a + b, 0) / dataArray.length;

        if (volume > SILENCE_THRESHOLD) {
          hasSpoken = true;
          silentFrames = 0;
        } else if (hasSpoken) {
          silentFrames++;
          if (silentFrames >= SILENCE_FRAMES_TO_STOP) {
            clearInterval(vadInterval);
            if (mediaRecorder.state === 'recording') mediaRecorder.stop();
          }
        }
      }, 100);

      setTimeout(() => {
        clearInterval(vadInterval);
        if (mediaRecorder.state === 'recording') mediaRecorder.stop();
      }, 15000);

    } catch (err) {
      console.error('Microphone error:', err);
      isRecordingRef.current = false;
      setIdleState('neutral', 1000);
    }
  };

  startListeningRef.current = startListening;

  const stopListening = useCallback(() => {
    if (restartTimeoutRef.current) clearTimeout(restartTimeoutRef.current);
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.stop();
    }
  }, []);

  const toggleAlwaysOn = useCallback(() => {
    if (isSleepingRef.current) {
      wakeUpFromSleep("I'm awake, Sir! Say 'Hey Sylphya' anytime.");
      return;
    }

    setIsAlwaysOn(prev => {
      const nextVal = !prev;
      alwaysOnRef.current = nextVal;
      try {
        localStorage.setItem('sylphya_always_on', String(nextVal));
      } catch {}

      if (nextVal) {
        showSubtitle('Always-On active: Say "Hey Sylphya" anytime!', 4000);
        if (listenStateRef.current === 'idle' && !isRecordingRef.current) {
          scheduleRestartListening(300);
        }
      } else {
        showSubtitle('Push-to-Talk active (Ctrl+Space to talk)', 3000);
        if (restartTimeoutRef.current) clearTimeout(restartTimeoutRef.current);
        if (listenStateRef.current === 'listening') {
          stopListening();
        }
      }
      return nextVal;
    });
  }, [scheduleRestartListening, showSubtitle, stopListening, wakeUpFromSleep]);

  // Auto-engage Always-On listener once Live2D is initialized
  useEffect(() => {
    if (state === 'ready' && alwaysOnRef.current && listenStateRef.current === 'idle') {
      scheduleRestartListening(1200);
    }
  }, [state, scheduleRestartListening]);

  // --- Desktop Cursor Tracking ---
  useEffect(() => {
    let cleanupIpc: (() => void) | undefined;
    const ipc = getElectronIpc();

    if (ipc && typeof ipc.on === 'function') {
      const onGlobalCursor = (_event: any, relX: number, relY: number) => {
        cursorPosRef.current.x = relX;
        cursorPosRef.current.y = relY;
        updateHitTest(relX, relY);
      };
      ipc.on('cursor-pos', onGlobalCursor);
      cleanupIpc = () => {
        try { ipc.removeListener('cursor-pos', onGlobalCursor); } catch {}
      };
    }

    const onMouseMove = (e: MouseEvent) => {
      cursorPosRef.current.x = e.clientX;
      cursorPosRef.current.y = e.clientY;
      updateHitTest(e.clientX, e.clientY);
    };
    window.addEventListener('mousemove', onMouseMove, { passive: true });

    return () => {
      window.removeEventListener('mousemove', onMouseMove);
      cleanupIpc?.();
      const ipc = getElectronIpc();
      ipc?.send('set-ignore-mouse-events', false);
    };
  }, [updateHitTest]);

  // --- Keyboard Shortcuts (Ctrl+Space to Talk, Ctrl+Shift+A for Always-On) ---
  useEffect(() => {
    const ipc = getElectronIpc();
    let cleanupIpc: (() => void) | undefined;

    if (ipc && typeof ipc.on === 'function') {
      const handleHotkey = () => {
        if (state === 'ready') {
          if (listenStateRef.current === 'idle') {
            startListening();
          } else if (listenStateRef.current === 'listening') {
            stopListening();
          }
        }
      };
      const handleHotkeyToggleAlwaysOn = () => {
        toggleAlwaysOn();
      };

      ipc.on('hotkey-listen', handleHotkey);
      ipc.on('hotkey-toggle-always-on', handleHotkeyToggleAlwaysOn);

      cleanupIpc = () => {
        try {
          ipc.removeListener('hotkey-listen', handleHotkey);
          ipc.removeListener('hotkey-toggle-always-on', handleHotkeyToggleAlwaysOn);
        } catch {}
      };
    }

    return () => {
      cleanupIpc?.();
    };
  }, [state, toggleAlwaysOn]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && (e.key === 'A' || e.key === 'a')) {
        e.preventDefault();
        toggleAlwaysOn();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [toggleAlwaysOn]);

  // Status & Mode Styling Config
  const toggleTheme = isSleeping
    ? {
        bg: 'rgba(99, 102, 241, 0.25)',
        border: 'rgba(129, 140, 248, 0.6)',
        color: '#a5b4fc',
        dot: '#818cf8',
        glow: 'rgba(99, 102, 241, 0.35)',
        label: '💤 Sleeping',
      }
    : isAlwaysOn
      ? isInActiveWindow
        ? {
            bg: 'rgba(59, 130, 246, 0.25)',
            border: 'rgba(96, 165, 250, 0.6)',
            color: '#93c5fd',
            dot: '#60a5fa',
            glow: 'rgba(59, 130, 246, 0.35)',
            label: 'Active Chat 💬',
          }
        : {
            bg: 'rgba(34, 197, 94, 0.22)',
            border: 'rgba(74, 222, 128, 0.6)',
            color: '#4ade80',
            dot: '#22c55e',
            glow: 'rgba(34, 197, 94, 0.35)',
            label: 'Hey Sylphya 👂',
          }
      : {
          bg: 'rgba(20, 20, 32, 0.75)',
          border: 'rgba(255, 255, 255, 0.14)',
          color: '#9ca3af',
          dot: '#6b7280',
          glow: 'rgba(0, 0, 0, 0.4)',
          label: 'Push to Talk 🎙️',
        };

  return (
    <>
      <div className={`loading-container ${state !== 'loading' ? 'hidden' : ''}`}>
        <div className="loading-spinner" />
      </div>

      {state === 'error' && (
        <div className="error-container" style={{ WebkitAppRegion: 'no-drag' } as any}>
          <div className="error-icon">⚠️</div>
          <div className="error-title">Failed to load model</div>
          <div className="error-message">{errorMsg}</div>
          <button className="error-retry" onClick={() => initLive2D()}>Retry</button>
        </div>
      )}

      {/* Always-On / Wake Word Mode Toggle (Top-Left) */}
      <div
        className="interactive always-on-toggle"
        onClick={(e) => {
          e.stopPropagation();
          toggleAlwaysOn();
        }}
        title="Toggle Always-On / Wake Word Mode (Ctrl+Shift+A)"
        style={{
          position: 'absolute',
          top: 14,
          left: 14,
          display: 'flex',
          alignItems: 'center',
          gap: '7px',
          padding: '5px 12px',
          borderRadius: '16px',
          background: toggleTheme.bg,
          border: `1px solid ${toggleTheme.border}`,
          backdropFilter: 'blur(16px)',
          WebkitBackdropFilter: 'blur(16px)',
          color: toggleTheme.color,
          fontSize: '11px',
          fontWeight: 600,
          letterSpacing: '0.3px',
          cursor: 'pointer',
          userSelect: 'none',
          zIndex: 80,
          transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
          boxShadow: isAlwaysOn || isSleeping ? `0 0 14px ${toggleTheme.glow}` : `0 2px 8px ${toggleTheme.glow}`,
        }}
      >
        <span
          style={{
            width: '8px',
            height: '8px',
            borderRadius: '50%',
            backgroundColor: toggleTheme.dot,
            boxShadow: isAlwaysOn || isSleeping ? `0 0 8px ${toggleTheme.dot}` : 'none',
            animation: !isSleeping && isAlwaysOn && listenState === 'listening' ? 'pulse 1.2s infinite' : 'none',
          }}
        />
        {toggleTheme.label}
      </div>

      {/* Discreet Audio Status Indicators (Top-Right) */}
      {listenState === 'listening' && (
        <div style={{ position: 'absolute', top: 16, right: 16, color: '#ff4757', animation: 'pulse 1s infinite', fontSize: '20px', pointerEvents: 'none', zIndex: 50 }}>
          🎤
        </div>
      )}
      {listenState === 'processing' && (
        <div style={{ position: 'absolute', top: 16, right: 16, color: '#ffa502', fontSize: '20px', pointerEvents: 'none', zIndex: 50 }}>
          ⏳
        </div>
      )}

      {/* Main Transparent Canvas: Tap-to-Talk, Drag Window & Pixel-Accurate Click-Through */}
      <div 
        className="canvas-wrapper" 
        ref={canvasRef} 
        onPointerDown={(e) => {
          try {
            (e.target as HTMLElement).setPointerCapture(e.pointerId);
          } catch {}
          let winPos = [0, 0];
          try {
            const ipc = getElectronIpc();
            if (ipc?.sendSync) {
              winPos = ipc.sendSync('get-window-pos') || [0, 0];
            }
          } catch {}

          dragRef.current = {
            isDragging: true,
            startX: e.screenX,
            startY: e.screenY,
            winStartX: winPos[0],
            winStartY: winPos[1],
            hasMoved: false
          };

          if (canvasRef.current) {
            canvasRef.current.style.cursor = 'grabbing';
          }
        }}
        onPointerMove={(e) => {
          cursorPosRef.current.x = e.clientX;
          cursorPosRef.current.y = e.clientY;

          if (dragRef.current.isDragging) {
            const dx = e.screenX - dragRef.current.startX;
            const dy = e.screenY - dragRef.current.startY;
            
            if (Math.abs(dx) > 3 || Math.abs(dy) > 3) {
              dragRef.current.hasMoved = true;
            }

            if (dragRef.current.hasMoved) {
              try {
                const ipc = getElectronIpc();
                const newX = Math.round(Number(dragRef.current.winStartX || 0) + Number(dx || 0));
                const newY = Math.round(Number(dragRef.current.winStartY || 0) + Number(dy || 0));
                if (!isNaN(newX) && !isNaN(newY)) {
                  ipc?.send('set-window-pos', newX, newY);
                }
              } catch {}
            }
          } else {
            updateHitTest(e.clientX, e.clientY);
          }
        }}
        onPointerUp={(e) => {
          try {
            (e.target as HTMLElement).releasePointerCapture(e.pointerId);
          } catch {}
          dragRef.current.isDragging = false;
          
          if (!dragRef.current.hasMoved && state === 'ready') {
            try {
              modelRef.current?.tap(e.clientX, e.clientY);
            } catch {}

            if (isSleepingRef.current) {
              wakeUpFromSleep(
                "I'm awake, Sir! What can I do for you?",
                "The user tapped you to wake you up from sleep. Greet him with a short cheerful greeting."
              );
              return;
            }

            if (listenState === 'idle') {
              startListening();
            } else if (listenState === 'listening') {
              stopListening();
            }
          }

          updateHitTest(e.clientX, e.clientY);
        }}
      />

      {/* Subtitle Bubble (Bottom) */}
      {subtitle && (
        <div
          style={{
            position: 'absolute',
            bottom: showFeedback ? 68 : 24,
            left: '50%',
            transform: 'translateX(-50%)',
            maxWidth: '90%',
            background: 'rgba(15, 15, 25, 0.85)',
            backdropFilter: 'blur(20px)',
            WebkitBackdropFilter: 'blur(20px)',
            border: '1px solid rgba(255, 255, 255, 0.22)',
            borderRadius: '16px',
            padding: '8px 16px',
            color: '#fff',
            fontSize: '12px',
            lineHeight: 1.4,
            textAlign: 'center',
            boxShadow: '0 8px 32px rgba(0, 0, 0, 0.5)',
            pointerEvents: 'none',
            zIndex: 60,
            animation: 'fadeIn 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
            transition: 'bottom 0.3s ease',
          }}
        >
          {subtitle}
        </div>
      )}

      {/* Feedback Buttons (show after Sylphya speaks) */}
      {showFeedback && listenState === 'idle' && (
        <div
          className="interactive"
          style={{
            position: 'absolute',
            bottom: 18,
            left: '50%',
            transform: 'translateX(-50%)',
            display: 'flex',
            gap: '10px',
            alignItems: 'center',
            background: 'rgba(15, 15, 25, 0.82)',
            backdropFilter: 'blur(16px)',
            WebkitBackdropFilter: 'blur(16px)',
            border: '1px solid rgba(255,255,255,0.15)',
            borderRadius: '20px',
            padding: '5px 14px',
            zIndex: 61,
            animation: 'fadeIn 0.3s ease',
          }}
        >
          <span style={{ color: 'rgba(255,255,255,0.45)', fontSize: '10px', letterSpacing: '0.3px' }}>Helpful?</span>
          <button
            onClick={() => submitFeedback(true)}
            style={{
              background: 'rgba(34,197,94,0.18)', border: '1px solid rgba(34,197,94,0.4)',
              color: '#4ade80', borderRadius: '12px', padding: '3px 10px',
              cursor: 'pointer', fontSize: '13px', transition: 'all 0.2s',
            }}
            title="Good response"
          >👍</button>
          <button
            onClick={() => submitFeedback(false)}
            style={{
              background: 'rgba(239,68,68,0.18)', border: '1px solid rgba(239,68,68,0.4)',
              color: '#f87171', borderRadius: '12px', padding: '3px 10px',
              cursor: 'pointer', fontSize: '13px', transition: 'all 0.2s',
            }}
            title="Poor response"
          >👎</button>
          <button
            onClick={() => setShowFeedback(false)}
            style={{
              background: 'transparent', border: 'none',
              color: 'rgba(255,255,255,0.3)', cursor: 'pointer', fontSize: '11px', padding: '2px 4px',
            }}
          >✕</button>
        </div>
      )}
    </>
  );
}

export default App;
