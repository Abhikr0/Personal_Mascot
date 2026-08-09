import { useEffect, useRef, useState, useCallback } from 'react';
import * as PIXI from 'pixi.js';
import { Live2DModel } from 'pixi-live2d-display';
import './index.css';

// Register PIXI on window for pixi-live2d-display
(window as any).PIXI = PIXI;

type AppState = 'loading' | 'ready' | 'error';
type ListenState = 'idle' | 'listening' | 'processing' | 'speaking';
type AssistantEmotion = 'neutral' | 'happy' | 'thinking' | 'concerned' | 'surprised';

const MODEL_PATH = '/runtime/hiyori_pro_t11.model3.json';

// --- Global AudioContext for Lip Sync ---
let globalAudioCtx: AudioContext | null = null;
const getAudioContext = () => {
  if (!globalAudioCtx) {
    globalAudioCtx = new (window.AudioContext || (window as any).webkitAudioContext)();
  }
  return globalAudioCtx;
};

// --- App Component ---
function App() {
  const canvasRef = useRef<HTMLDivElement>(null);
  const appRef = useRef<PIXI.Application | null>(null);
  const modelRef = useRef<any>(null);

  const [state, setState] = useState<AppState>('loading');
  const [errorMsg, setErrorMsg] = useState('');
  const [listenState, setListenState] = useState<ListenState>('idle');

  const listenStateRef = useRef<ListenState>('idle');
  const emotionRef = useRef<AssistantEmotion>('neutral');
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const isRecordingRef = useRef(false);
  const faceLoopRef = useRef<number | null>(null);
  const originalSizeRef = useRef({ width: 0, height: 0 });
  const dragRef = useRef({ isDragging: false, startX: 0, startY: 0, winStartX: 0, winStartY: 0, hasMoved: false });
  const cursorPosRef = useRef({ x: 0, y: 0 });
  const lipSyncFrameRef = useRef<number | null>(null);
  const lipSyncSourceRef = useRef<AudioBufferSourceNode | null>(null);
  const lipSyncAnalyserRef = useRef<AnalyserNode | null>(null);
  const mouthOpenRef = useRef(0);
  const animTimeRef = useRef(0);
  const lastFrameTimeRef = useRef(0);
  const idleFidgetTimerRef = useRef(0);
  const idleFidgetTargetRef = useRef({ armL: 0, armR: 0, handL: 0, handR: 0 });
  const sendToBackendRef = useRef<(msg: string) => void>();

  const updateEmotion = (newEmotion: AssistantEmotion) => {
    emotionRef.current = newEmotion;
  };

  useEffect(() => {
    const handleInteract = async () => {
      // Initialize and resume AudioContext on first click to satisfy browser security
      const ctx = getAudioContext();
      if (ctx.state === 'suspended') {
        await ctx.resume();
      }
      window.removeEventListener('click', handleInteract);
      window.removeEventListener('keydown', handleInteract);
    };
    window.addEventListener('click', handleInteract);
    window.addEventListener('keydown', handleInteract);
    
    // Listen for the global cursor stream from the Electron main process
    try {
      const { ipcRenderer } = (window as any).require('electron');
      ipcRenderer.on('cursor-pos', (_event: any, x: number, y: number) => {
        cursorPosRef.current = { x, y };
      });
    } catch(e) {}

    return () => {
      window.removeEventListener('click', handleInteract);
      window.removeEventListener('keydown', handleInteract);
    };
  }, []);

  // --- Emotion Mappings ---
  // We strictly avoid ParamEyeLOpen/ROpen here to allow the engine to handle blinking naturally!
  // Now includes: Cheek (blush), Shoulder, BodyAngleX/Y, BrowForm for richer expressions.
  const EMOTION_MAP: Record<AssistantEmotion, Record<string, number>> = {
    neutral: {
      ParamEyeLSmile: 0, ParamEyeRSmile: 0, ParamMouthForm: 0,
      ParamBrowLAngle: 0, ParamBrowRAngle: 0, ParamBrowLY: 0, ParamBrowRY: 0,
      ParamBrowLForm: 0, ParamBrowRForm: 0,
      ParamCheek: 0, ParamShoulder: 0,
      ParamBodyAngleX: 0, ParamBodyAngleY: 0,
      ParamArmLA: 0, ParamArmRA: 0, ParamArmLB: 0, ParamArmRB: 0,
      ParamHandL: 0, ParamHandR: 0, ParamLeg: 0,
    },
    happy: {
      ParamEyeLSmile: 1, ParamEyeRSmile: 1, ParamMouthForm: 1,
      ParamBrowLAngle: 0, ParamBrowRAngle: 0, ParamBrowLY: 0.2, ParamBrowRY: 0.2,
      ParamBrowLForm: 0.5, ParamBrowRForm: 0.5,
      ParamCheek: 1, ParamShoulder: 0.3,
      ParamBodyAngleX: 0, ParamBodyAngleY: 0,
      ParamArmLA: 1, ParamArmRA: 1, ParamArmLB: 0, ParamArmRB: 0,
      ParamHandL: 1, ParamHandR: 1, ParamLeg: 1,
    },
    thinking: {
      ParamEyeLSmile: 0, ParamEyeRSmile: 0, ParamMouthForm: 0,
      ParamBrowLAngle: -0.5, ParamBrowRAngle: -0.5, ParamBrowLY: -0.5, ParamBrowRY: -0.5,
      ParamBrowLForm: -0.3, ParamBrowRForm: -0.3,
      ParamCheek: 0, ParamShoulder: -0.2,
      ParamBodyAngleX: -8, ParamBodyAngleY: 5,
      ParamArmLA: 0, ParamArmRA: 0, ParamArmLB: 1, ParamArmRB: 0,
      ParamHandL: -1, ParamHandR: 0, ParamLeg: 0,
    },
    concerned: {
      ParamEyeLSmile: 0, ParamEyeRSmile: 0, ParamMouthForm: -0.5,
      ParamBrowLAngle: 0.8, ParamBrowRAngle: 0.8, ParamBrowLY: -0.3, ParamBrowRY: -0.3,
      ParamBrowLForm: 0.5, ParamBrowRForm: 0.5,
      ParamCheek: 0, ParamShoulder: -0.4,
      ParamBodyAngleX: 0, ParamBodyAngleY: -3,
      ParamArmLA: -1, ParamArmRA: -1, ParamArmLB: 0, ParamArmRB: 0,
      ParamHandL: -1, ParamHandR: -1, ParamLeg: -1,
    },
    surprised: {
      ParamEyeLSmile: 0, ParamEyeRSmile: 0, ParamMouthForm: -0.2,
      ParamBrowLAngle: 0, ParamBrowRAngle: 0, ParamBrowLY: 0.8, ParamBrowRY: 0.8,
      ParamBrowLForm: -0.5, ParamBrowRForm: -0.5,
      ParamCheek: 0.5, ParamShoulder: 0.8,
      ParamBodyAngleX: 0, ParamBodyAngleY: -5,
      ParamArmLA: 0, ParamArmRA: 0, ParamArmLB: -1, ParamArmRB: -1,
      ParamHandL: 1, ParamHandR: 1, ParamLeg: 0,
    },
  };

  // --- Live2D Setup ---
  const initLive2D = useCallback(async () => {
    if (!canvasRef.current) return;
    setState('loading');
    setErrorMsg('');

    try {
      if (appRef.current) {
        appRef.current.destroy(true, { children: true });
        appRef.current = null;
      }

      const WIN_W = 350;
      const WIN_H = 500;

      const app = new PIXI.Application({
        width: WIN_W,
        height: WIN_H,
        backgroundAlpha: 0,
        antialias: true,
        resolution: 1, // Locked to 1 to prevent multi-monitor DPI scaling bugs
        autoDensity: false, // Disabled to prevent Pixi from reacting to monitor dragging
      });

      canvasRef.current.innerHTML = '';
      canvasRef.current.appendChild(app.view as unknown as HTMLElement);
      appRef.current = app;

      const model = await Live2DModel.from(MODEL_PATH, { 
        autoInteract: false, 
        autoUpdate: true,
        idleMotionGroup: 'none' // Disable built-in idle motions so they don't overwrite our procedural ones
      });

      if (!appRef.current || app !== appRef.current || !app.screen) {
        model.destroy();
        return;
      }

      modelRef.current = model;

      const baseWidth = model.internalModel.width || model.width;
      const baseHeight = model.internalModel.height || model.height;

      const scaleX = WIN_W / baseWidth;
      const scaleY = WIN_H / baseHeight;
      const scale = Math.min(scaleX, scaleY) * 2.1; // Drastically zoom in to crop out her legs
      
      model.scale.set(scale);
      model.anchor.set(0.5, 0.5);
      model.x = WIN_W / 2;
      model.y = WIN_H / 2 + 200; // Shift heavily down so her head is at the top of the frame
      model.interactive = true;
      app.stage.addChild(model);

      model.on('hit', (hitAreas: string[]) => {
        if (hitAreas.includes('Body') || hitAreas.includes('HitArea')) {
          if (listenStateRef.current === 'idle') {
             // Send an action to the backend so the AI can react to being poked!
             sendToBackendRef.current?.("*pokes your tummy*");
          }
        }
      });

      // Stop any existing motions that might override our procedural animation
      try { model.internalModel.motionManager.stopAllMotions(); } catch {}
      setState('ready');

      // --- Continuous Facial Expression + Procedural Body Animation Loop ---
      const currentParams: Record<string, number> = {};
      // Procedural animation accumulators (smoothed values for body params)
      const proceduralState: Record<string, number> = {};

      const lerp = (current: number, target: number, speed: number) =>
        current + (target - current) * Math.min(1, speed);

      const updateFace = () => {
        if (modelRef.current?.internalModel?.coreModel) {
          const now = performance.now();
          const dt = Math.min((now - (lastFrameTimeRef.current || now)) / 1000, 0.05);
          lastFrameTimeRef.current = now;
          animTimeRef.current += dt;
          const t = animTimeRef.current;

          const targetParams = EMOTION_MAP[emotionRef.current] || EMOTION_MAP['neutral'];
          const coreModel = modelRef.current.internalModel.coreModel;
          const state = listenStateRef.current;

          // ======================================================
          // 1. EMOTION BLENDING (existing, unchanged logic)
          // ======================================================
          for (const [param, target] of Object.entries(targetParams)) {
             if (currentParams[param] === undefined) {
                 currentParams[param] = target;
             }
             currentParams[param] += (target - currentParams[param]) * 0.1;
             coreModel.setParameterValueById(param, currentParams[param]);
          }

          // Force mouth strictly closed when NOT speaking
          if (state !== 'speaking') {
             mouthOpenRef.current = 0;
             coreModel.setParameterValueById('ParamMouthOpenY', 0);
          }

          // ======================================================
          // 2. ALWAYS-ON: BREATHING
          // ======================================================
          // Gentle sine wave for breathing, always active
          const breathSpeed = state === 'speaking' ? 3.5 : state === 'listening' ? 2.5 : 2.0;
          const breathAmp = state === 'speaking' ? 0.6 : 0.4;
          const breath = Math.sin(t * breathSpeed) * breathAmp + breathAmp * 0.5;
          coreModel.setParameterValueById('ParamBreath', Math.max(0, breath));

          // ======================================================
          // 3. STATE-SPECIFIC PROCEDURAL ANIMATIONS
          // ======================================================

          // --- Target values for procedural params ---
          let pBodyAngleX = 0;
          let pBodyAngleZ = 0;
          let pAngleX = 0;
          let pAngleY = 0;
          let pAngleZ = 0;
          let pShoulder = 0;
          let pArmLA = 0;
          let pArmRA = 0;
          let pArmLB = 0;
          let pArmRB = 0;
          let pHandL = 0;
          let pHandR = 0;
          let pHairFront = 0;
          let pHairBack = 0;
          let pRibbon = 0;
          let pSkirt = 0;

          if (state === 'speaking') {
            // ====================================================
            // SPEAKING: Expressive gestures driven by time + audio
            // ====================================================
            const mouthEnergy = mouthOpenRef.current; // 0..1 from lip-sync

            // Body sway — slow, gentle side-to-side lean
            pBodyAngleX = Math.sin(t * 0.8) * 3 + Math.sin(t * 1.3) * 1.5;
            pBodyAngleZ = Math.sin(t * 0.6 + 1) * 2;

            // Head nods — subtle Y movement (like explaining/agreeing)
            pAngleY = Math.sin(t * 1.5) * 4 + mouthEnergy * -3;

            // Head tilts — Z-axis tilt synced loosely to speech
            pAngleZ = Math.sin(t * 0.9 + 0.5) * 3;

            // Shoulder movement — rises with speech energy
            pShoulder = mouthEnergy * 0.4 + Math.sin(t * 2) * 0.15;

            // Hand gestures — periodic "emphasis" gestures
            const gestureWave = Math.sin(t * 0.7);
            const gestureIntensity = 0.3 + mouthEnergy * 0.7;

            if (emotionRef.current === 'happy') {
              // Upward hand movement!
              // Hide the straight arms
              pArmLA = -1.5;
              pArmRA = -1.5;
              // Show the upward/bent arms and animate them
              pArmLB = 1.0 + gestureWave * 0.5 * gestureIntensity;
              pArmRB = 1.0 - gestureWave * 0.5 * gestureIntensity;
              
              pHandL = Math.sin(t * 1.1) * 3.0 + mouthEnergy * 2.0;
              pHandR = Math.sin(t * 1.1 + Math.PI) * 3.0 + mouthEnergy * 2.0;
            } else {
              // Standard speaking gestures
              pArmLA = gestureWave * gestureIntensity * 5.0;
              pArmRA = -gestureWave * gestureIntensity * 5.0;
              pHandL = Math.sin(t * 1.1) * 3.0 + mouthEnergy * 2.0;
              pHandR = Math.sin(t * 1.1 + Math.PI) * 3.0 + mouthEnergy * 2.0;
            }

            // Hair/ribbon sway — driven by body movement
            pHairFront = Math.sin(t * 1.2) * 0.3;
            pHairBack = Math.sin(t * 0.9 + 0.7) * 0.25;
            pRibbon = Math.sin(t * 1.5 + 0.3) * 0.4;
            pSkirt = Math.sin(t * 0.8 + 1.2) * 0.2;

          } else if (state === 'listening') {
            // ====================================================
            // LISTENING: Attentive, curious posture
            // ====================================================

            // Lean forward attentively
            pAngleX = 12 + Math.sin(t * 0.5) * 3;
            pAngleY = -8 + Math.sin(t * 0.7) * 2;

            // Curious head tilts — slow side-to-side
            pAngleZ = Math.sin(t * 0.4) * 5;

            // Body leans in
            pBodyAngleZ = 6 + Math.sin(t * 0.6) * 2;

            // Widened eyes (keep existing behavior)
            coreModel.setParameterValueById('ParamEyeLOpen', 1.2);
            coreModel.setParameterValueById('ParamEyeROpen', 1.2);

            // Hands in attentive pose — gently clasped/moving
            pArmLA = -0.3 + Math.sin(t * 0.5) * 0.15;
            pArmRA = -0.3 + Math.sin(t * 0.5 + Math.PI) * 0.15;
            pHandL = -0.5 + Math.sin(t * 0.8) * 0.2;
            pHandR = -0.5 + Math.sin(t * 0.8 + Math.PI) * 0.2;

            // Shoulder slightly raised (attentive)
            pShoulder = 0.2 + Math.sin(t * 0.6) * 0.1;

            // Subtle hair movement
            pHairFront = Math.sin(t * 0.5) * 0.15;
            pRibbon = Math.sin(t * 0.7) * 0.2;

          } else {
            // ====================================================
            // IDLE: Subtle micro-animations to look alive
            // ====================================================

            // Very slow weight shifting
            pBodyAngleX = Math.sin(t * 0.3) * 1.5 + Math.sin(t * 0.17) * 0.8;
            pBodyAngleZ = Math.sin(t * 0.25 + 1) * 1;

            // Slight head movement — looking around naturally
            pAngleZ = Math.sin(t * 0.2) * 2;
            pAngleY = Math.sin(t * 0.15) * 1.5;

            // Idle hand fidgets — random targets that change every few seconds
            idleFidgetTimerRef.current -= dt;
            if (idleFidgetTimerRef.current <= 0) {
              idleFidgetTimerRef.current = 3 + Math.random() * 5; // 3-8 sec between fidgets
              const fidgetIntensity = Math.random() * 0.5;
              idleFidgetTargetRef.current = {
                armL: (Math.random() - 0.5) * fidgetIntensity,
                armR: (Math.random() - 0.5) * fidgetIntensity,
                handL: (Math.random() - 0.5) * fidgetIntensity * 1.5,
                handR: (Math.random() - 0.5) * fidgetIntensity * 1.5,
              };
            }
            const fidget = idleFidgetTargetRef.current;
            pArmLA = fidget.armL;
            pArmRA = fidget.armR;
            pHandL = fidget.handL;
            pHandR = fidget.handR;

            // Subtle hair sway — breeze effect
            pHairFront = Math.sin(t * 0.4 + 0.5) * 0.1;
            pHairBack = Math.sin(t * 0.35) * 0.08;
            pRibbon = Math.sin(t * 0.5 + 1) * 0.15;
            pSkirt = Math.sin(t * 0.3 + 0.8) * 0.1;

            // Shoulder — gentle breathing effect
            pShoulder = Math.sin(t * 2) * 0.08;
          }

          // ======================================================
          // 4. APPLY PROCEDURAL PARAMS WITH SMOOTHING
          // ======================================================
          // Smooth all procedural values to prevent snapping on state transitions
          const smoothSpeed = 0.08;
          const applySmoothed = (id: string, target: number) => {
            if (proceduralState[id] === undefined) proceduralState[id] = 0;
            proceduralState[id] = lerp(proceduralState[id], target, smoothSpeed);
            coreModel.setParameterValueById(id, proceduralState[id]);
          };

          // Body
          applySmoothed('ParamBodyAngleX', pBodyAngleX);
          applySmoothed('ParamBodyAngleZ', pBodyAngleZ);
          applySmoothed('ParamShoulder', pShoulder);

          // Head (only apply procedural head if NOT in cursor-tracking mode)
          // During speaking/listening we drive the head; during idle, cursor tracking handles it
          if (state === 'speaking' || state === 'listening') {
            applySmoothed('ParamAngleX', pAngleX);
            applySmoothed('ParamAngleY', pAngleY);
            applySmoothed('ParamAngleZ', pAngleZ);
          }

          // Arms & Hands — blend with emotion targets
          // Procedural movement is additive on top of emotion base
          const emotionArmLA = currentParams['ParamArmLA'] || 0;
          const emotionArmRA = currentParams['ParamArmRA'] || 0;
          const emotionArmLB = currentParams['ParamArmLB'] || 0;
          const emotionArmRB = currentParams['ParamArmRB'] || 0;
          const emotionHandL = currentParams['ParamHandL'] || 0;
          const emotionHandR = currentParams['ParamHandR'] || 0;
          applySmoothed('ParamArmLA', emotionArmLA + pArmLA);
          applySmoothed('ParamArmRA', emotionArmRA + pArmRA);
          applySmoothed('ParamArmLB', emotionArmLB + pArmLB);
          applySmoothed('ParamArmRB', emotionArmRB + pArmRB);
          applySmoothed('ParamHandL', emotionHandL + pHandL);
          applySmoothed('ParamHandR', emotionHandR + pHandR);

          // Hair & Accessories
          applySmoothed('ParamHairFront', pHairFront);
          applySmoothed('ParamHairBack', pHairBack);
          applySmoothed('ParamRibbon', pRibbon);
          applySmoothed('ParamSkirt', pSkirt);
        }

        // --- Global Cursor Tracking (Outside Window) ---
        if (modelRef.current) {
          try {
            const point = cursorPosRef.current;
            const winX = window.screenX;
            const winY = window.screenY;
            
            // Map global screen coordinates into the local Canvas space
            const canvasX = point.x - winX;
            const canvasY = point.y - winY;
            
            // Cursor tracking only when idle (speaking/listening have their own head control)
            if (listenStateRef.current === 'idle') {
              modelRef.current.focus(canvasX, canvasY);
            }
          } catch (err) {}
        }
      };

      // Hook directly into the internal Live2D model update cycle.
      // This is critical because Live2D resets parameters every frame before evaluating physics/rendering.
      // If we use app.ticker, our changes get wiped out before they are drawn!
      model.internalModel.on('beforeModelUpdate', updateFace);
      
      // No resize listener needed; dimensions are locked perfectly for the desktop mascot mode
    } catch (err: any) {
      console.error('Failed to initialize Live2D:', err);
      setErrorMsg(err?.message || 'Unknown error loading the Live2D model.');
      setState('error');
    }
  }, []);

  useEffect(() => {
    initLive2D();
    return () => {
      if (faceLoopRef.current) cancelAnimationFrame(faceLoopRef.current);
      if (lipSyncFrameRef.current !== null) {
        cancelAnimationFrame(lipSyncFrameRef.current);
        lipSyncFrameRef.current = null;
      }
      if (lipSyncSourceRef.current) {
        try { lipSyncSourceRef.current.stop(); } catch {}
        try { lipSyncSourceRef.current.disconnect(); } catch {}
        lipSyncSourceRef.current = null;
      }
      lipSyncAnalyserRef.current = null;
      mouthOpenRef.current = 0;
      if (appRef.current) {
        try { appRef.current.destroy(true, { children: true, texture: true, baseTexture: true }); } catch {}
        appRef.current = null;
        modelRef.current = null;
      }
    };
  }, [initLive2D]);

  // --- Send text to backend, get response + audio, make model speak ---
  const sendToBackend = async (message: string) => {
    if (!message.trim()) return;

    // Stop any previous lip-sync/audio
    if (lipSyncFrameRef.current !== null) {
      cancelAnimationFrame(lipSyncFrameRef.current);
      lipSyncFrameRef.current = null;
    }

    if (lipSyncSourceRef.current) {
      try {
        lipSyncSourceRef.current.stop();
      } catch {}
      lipSyncSourceRef.current.disconnect();
      lipSyncSourceRef.current = null;
    }

    mouthOpenRef.current = 0;

    listenStateRef.current = 'speaking';
    setListenState('speaking');

    try {
      const response = await fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ message }),
      });

      if (!response.ok) {
        throw new Error(`Backend error: ${response.status}`);
      }

      const data = await response.json();

      updateEmotion(data.emotion || 'neutral');

      console.log(`[Reply] [${data.emotion}]`, data.text);

      if (!data.audio_url || !modelRef.current) {
        listenStateRef.current = 'idle';
        setListenState('idle');
        return;
      }

      // ---------------------------------------------------------
      // DOWNLOAD AUDIO
      // ---------------------------------------------------------

      console.log(`[Audio] Fetching: ${data.audio_url}`);

      const audioRes = await fetch(data.audio_url);

      if (!audioRes.ok) {
        throw new Error(`Audio download failed: ${audioRes.status}`);
      }

      const arrayBuffer = await audioRes.arrayBuffer();

      // ---------------------------------------------------------
      // AUDIO CONTEXT
      // ---------------------------------------------------------

      const audioCtx = getAudioContext();

      if (audioCtx.state === 'suspended') {
        await audioCtx.resume();
      }

      // Decode MP3
      const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);

      // ---------------------------------------------------------
      // AUDIO SOURCE
      // ---------------------------------------------------------

      const source = audioCtx.createBufferSource();
      source.buffer = audioBuffer;

      lipSyncSourceRef.current = source;

      // ---------------------------------------------------------
      // ANALYSER
      // ---------------------------------------------------------

      const analyser = audioCtx.createAnalyser();

      analyser.fftSize = 512;

      // Lower value = faster response.
      // Higher value = smoother response.
      analyser.smoothingTimeConstant = 0.25;

      source.connect(analyser);
      analyser.connect(audioCtx.destination);

      lipSyncAnalyserRef.current = analyser;

      const timeData = new Uint8Array(
        analyser.fftSize
      );

      const frequencyData = new Uint8Array(
        analyser.frequencyBinCount
      );

      // ---------------------------------------------------------
      // LIP SYNC STATE
      // ---------------------------------------------------------

      let running = true;

      let previousMouth = 0;

      let noiseFloor = 0.008;

      let lastTime = performance.now();

      // Prevent the mouth from becoming completely static
      // during very quiet speech.
      let speechEnergy = 0;

      // ---------------------------------------------------------
      // HELPER: RMS
      // ---------------------------------------------------------

      const calculateRMS = (
        data: Uint8Array
      ): number => {
        let sum = 0;

        for (let i = 0; i < data.length; i++) {
          const sample =
            (data[i] - 128) / 128;

          sum += sample * sample;
        }

        return Math.sqrt(sum / data.length);
      };

      // ---------------------------------------------------------
      // HELPER: SPEECH FREQUENCY ENERGY
      // ---------------------------------------------------------

      const calculateSpeechEnergy = (): number => {
        analyser.getByteFrequencyData(frequencyData);

        /*
         * Speech is primarily concentrated roughly between
         * 150 Hz and 4 kHz.
         *
         * This prevents very low-frequency noise from driving
         * the mouth too much.
         */

        const nyquist = audioCtx.sampleRate / 2;

        const binWidth =
          nyquist / analyser.frequencyBinCount;

        const minBin = Math.max(
          0,
          Math.floor(150 / binWidth)
        );

        const maxBin = Math.min(
          analyser.frequencyBinCount - 1,
          Math.ceil(4000 / binWidth)
        );

        let sum = 0;
        let count = 0;

        for (
          let i = minBin;
          i <= maxBin;
          i++
        ) {
          sum += frequencyData[i];
          count++;
        }

        if (count === 0) {
          return 0;
        }

        return (sum / count) / 255;
      };

      // ---------------------------------------------------------
      // LIP SYNC LOOP
      // ---------------------------------------------------------

      const updateLipSync = (now: number) => {
        if (!running || !modelRef.current) {
          return;
        }

        const coreModel =
          modelRef.current?.internalModel?.coreModel;

        if (!coreModel) {
          return;
        }

        // -------------------------------------------------------
        // DELTA TIME
        // -------------------------------------------------------

        const deltaTime = Math.min(
          (now - lastTime) / 1000,
          0.05
        );

        lastTime = now;

        // -------------------------------------------------------
        // AUDIO ANALYSIS
        // -------------------------------------------------------

        analyser.getByteTimeDomainData(timeData);

        const rms =
          calculateRMS(timeData);

        const bandEnergy =
          calculateSpeechEnergy();

        /*
         * Combine waveform RMS with speech-band energy.
         *
         * RMS gives us overall loudness.
         * Frequency energy helps suppress non-speech noise.
         */

        const combinedEnergy =
          (rms * 0.7) +
          (bandEnergy * 0.3);

        // -------------------------------------------------------
        // ADAPTIVE NOISE FLOOR
        // -------------------------------------------------------

        if (combinedEnergy < noiseFloor * 1.5) {
          noiseFloor +=
            (combinedEnergy - noiseFloor) *
            Math.min(1, deltaTime * 2);
        }

        noiseFloor = Math.max(
          0.003,
          Math.min(noiseFloor, 0.05)
        );

        // -------------------------------------------------------
        // NORMALIZE
        // -------------------------------------------------------

        const signal =
          Math.max(
            0,
            combinedEnergy - noiseFloor
          );

        /*
         * Instead of the previous:
         *
         * sqrt(rms * 20)
         *
         * use a controlled normalized range.
         */

        const normalized =
          Math.min(
            1,
            signal / 0.12
          );

        // -------------------------------------------------------
        // CURVE
        // -------------------------------------------------------

        /*
         * Gamma > 1 keeps quiet speech subtle.
         * Loud vowels still open the mouth.
         */

        let targetMouth =
          Math.pow(normalized, 0.75);

        targetMouth =
          Math.min(
            1,
            Math.max(0, targetMouth)
          );

        // -------------------------------------------------------
        // SPEECH GATE
        // -------------------------------------------------------

        /*
         * Prevent tiny background noise from opening
         * the mouth.
         */

        if (combinedEnergy < noiseFloor + 0.008) {
          targetMouth = 0;
        }

        // -------------------------------------------------------
        // MICRO DEADZONE
        // -------------------------------------------------------

        if (targetMouth < 0.06) {
          targetMouth = 0;
        }

        // -------------------------------------------------------
        // ATTACK / RELEASE
        // -------------------------------------------------------

        /*
         * Opening should be quick.
         *
         * Closing should be slower.
         *
         * This creates a much more natural speech envelope.
         */

        const attackSpeed = 22;
        const releaseSpeed = 12;

        const speed =
          targetMouth > previousMouth
            ? attackSpeed
            : releaseSpeed;

        const smoothing =
          1 -
          Math.exp(-speed * deltaTime);

        const mouth =
          previousMouth +
          (targetMouth - previousMouth) *
          smoothing;

        previousMouth = mouth;

        mouthOpenRef.current = mouth;

        // -------------------------------------------------------
        // APPLY TO LIVE2D
        // -------------------------------------------------------

        coreModel.setParameterValueById(
          'ParamMouthOpenY',
          mouth
        );

        // Optional logging
        if (
          Math.random() < 0.015
        ) {
          console.log(
            `[LIP] RMS=${rms.toFixed(3)} ` +
            `Band=${bandEnergy.toFixed(3)} ` +
            `Noise=${noiseFloor.toFixed(3)} ` +
            `Target=${targetMouth.toFixed(2)} ` +
            `Mouth=${mouth.toFixed(2)}`
          );
        }

        lipSyncFrameRef.current =
          requestAnimationFrame(updateLipSync);
      };

      // ---------------------------------------------------------
      // AUDIO END
      // ---------------------------------------------------------

      source.onended = () => {
        running = false;

        if (lipSyncFrameRef.current !== null) {
          cancelAnimationFrame(
            lipSyncFrameRef.current
          );

          lipSyncFrameRef.current = null;
        }

        // Smoothly close mouth
        const closeMouth = () => {
          if (!modelRef.current) return;

          const coreModel =
            modelRef.current?.internalModel?.coreModel;

          if (!coreModel) return;

          mouthOpenRef.current *= 0.65;

          coreModel.setParameterValueById(
            'ParamMouthOpenY',
            mouthOpenRef.current
          );

          if (mouthOpenRef.current > 0.01) {
            requestAnimationFrame(closeMouth);
          } else {
            coreModel.setParameterValueById(
              'ParamMouthOpenY',
              0
            );

            mouthOpenRef.current = 0;
          }
        };

        closeMouth();

        listenStateRef.current = 'idle';
        setListenState('idle');

        console.log('[Audio] Finished playing.');

        try {
          source.disconnect();
          analyser.disconnect();
        } catch {}

        lipSyncSourceRef.current = null;
        lipSyncAnalyserRef.current = null;

        // Auto-delete the voice file from the backend once it's finished playing
        if (data.filename) {
          fetch(`http://localhost:8000/api/audio/${data.filename}`, { method: 'DELETE' })
            .catch(err => console.error('[Cleanup] Failed to delete audio:', err));
        }
      };

      // ---------------------------------------------------------
      // START
      // ---------------------------------------------------------

      console.log('[LipSync] Starting...');

      source.start(0);

      lipSyncFrameRef.current =
        requestAnimationFrame(updateLipSync);

    } catch (err) {
      console.error(
        '[Chat/LipSync] Error:',
        err
      );

      if (lipSyncFrameRef.current !== null) {
        cancelAnimationFrame(
          lipSyncFrameRef.current
        );

        lipSyncFrameRef.current = null;
      }

      if (lipSyncSourceRef.current) {
        try {
          lipSyncSourceRef.current.stop();
        } catch {}

        try {
          lipSyncSourceRef.current.disconnect();
        } catch {}

        lipSyncSourceRef.current = null;
      }

      if (modelRef.current?.internalModel?.coreModel) {
        modelRef.current.internalModel.coreModel
          .setParameterValueById(
            'ParamMouthOpenY',
            0
          );
      }

      mouthOpenRef.current = 0;

      listenStateRef.current = 'idle';
      setListenState('idle');
    }
  };

  sendToBackendRef.current = sendToBackend;

  // --- Microphone Recording with Volume-based VAD ---
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

      // Volume-based silence detection
      const audioContext = new AudioContext();
      const analyser = audioContext.createAnalyser();
      const source = audioContext.createMediaStreamSource(stream);
      source.connect(analyser);
      analyser.fftSize = 512;
      const dataArray = new Uint8Array(analyser.frequencyBinCount);

      let silentFrames = 0;
      let hasSpoken = false;
      const SILENCE_THRESHOLD = 15; // Volume level below which is "silence"
      const SILENCE_FRAMES_TO_STOP = 20; // ~2 seconds of silence
      const MAX_RECORD_MS = 15000; // Max 15 seconds

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunks.push(e.data);
      };

      mediaRecorder.onstop = async () => {
        // Cleanup
        stream.getTracks().forEach(t => t.stop());
        audioContext.close();
        isRecordingRef.current = false;

        if (audioChunks.length === 0 || !hasSpoken) {
          listenStateRef.current = 'idle';
          setListenState('idle');
          return;
        }

        // Send audio to backend for transcription
        listenStateRef.current = 'processing';
        setListenState('processing');

        const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });

        // Convert webm blob to WAV manually to avoid ffmpeg dependency on Python backend
        try {
          const arrayBuffer = await audioBlob.arrayBuffer();
          const decodeCtx = new AudioContext();
          const audioBuffer = await decodeCtx.decodeAudioData(arrayBuffer);
          
          const numChannels = audioBuffer.numberOfChannels;
          const sampleRate = audioBuffer.sampleRate;
          const result = new Float32Array(audioBuffer.length * numChannels);
          for (let i = 0; i < numChannels; i++) {
            const channelData = audioBuffer.getChannelData(i);
            for (let j = 0; j < audioBuffer.length; j++) {
              result[j * numChannels + i] = channelData[j];
            }
          }
          
          const dataLength = result.length * 2;
          const bufferLength = 44 + dataLength;
          const wavArrayBuffer = new ArrayBuffer(bufferLength);
          const view = new DataView(wavArrayBuffer);
          
          const writeString = (view: DataView, offset: number, string: string) => {
            for (let i = 0; i < string.length; i++) {
              view.setUint8(offset + i, string.charCodeAt(i));
            }
          };
          
          writeString(view, 0, 'RIFF');
          view.setUint32(4, 36 + dataLength, true);
          writeString(view, 8, 'WAVE');
          writeString(view, 12, 'fmt ');
          view.setUint32(16, 16, true);
          view.setUint16(20, 1, true);
          view.setUint16(22, numChannels, true);
          view.setUint32(24, sampleRate, true);
          view.setUint32(28, sampleRate * numChannels * 2, true);
          view.setUint16(32, numChannels * 2, true);
          view.setUint16(34, 16, true);
          writeString(view, 36, 'data');
          view.setUint32(40, dataLength, true);
          
          let offset = 44;
          for (let i = 0; i < result.length; i++) {
            let s = Math.max(-1, Math.min(1, result[i]));
            view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
            offset += 2;
          }
          
          const wavBlob = new Blob([view], { type: 'audio/wav' });
          const formData = new FormData();
          formData.append('audio', wavBlob, 'recording.wav');

          const res = await fetch('http://localhost:8000/api/transcribe', {
            method: 'POST',
            body: formData,
          });

          if (!res.ok) throw new Error('Transcription failed');
          const data = await res.json();
          const text = data.text?.trim();

          console.log(`📝 Transcribed: "${text}"`);

          if (text && text.length > 1) {
            await sendToBackend(text);
          } else {
            listenStateRef.current = 'idle';
            setListenState('idle');
          }
        } catch (err) {
          console.error('Transcription error:', err);
          listenStateRef.current = 'idle';
          setListenState('idle');
        }
      };

      mediaRecorder.start(250); // Collect data in 250ms chunks

      // VAD loop: detect silence to auto-stop
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
            if (mediaRecorder.state === 'recording') {
              mediaRecorder.stop();
            }
          }
        }
      }, 100);

      // Safety timeout
      setTimeout(() => {
        clearInterval(vadInterval);
        if (mediaRecorder.state === 'recording') {
          mediaRecorder.stop();
        }
      }, MAX_RECORD_MS);

    } catch (err) {
      console.error('Microphone error:', err);
      isRecordingRef.current = false;
      listenStateRef.current = 'idle';
      setListenState('idle');
    }
  };

  const stopListening = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.stop();
    }
  };

  // --- Global Keyboard Shortcut Listener ---
  useEffect(() => {
    try {
      const { ipcRenderer } = (window as any).require('electron');
      const handleHotkey = () => {
        if (state === 'ready') {
          if (listenStateRef.current === 'idle') {
            console.log("Global hotkey pressed! Starting recording...");
            startListening();
          } else if (listenStateRef.current === 'listening') {
            console.log("Global hotkey pressed! Stopping recording early...");
            stopListening();
          }
        }
      };
      
      ipcRenderer.on('hotkey-listen', handleHotkey);
      
      return () => {
        ipcRenderer.removeListener('hotkey-listen', handleHotkey);
      };
    } catch (e) {
      console.warn('Failed to bind IPC hotkey listener');
    }
  }, [state, startListening]);

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
          <button className="error-retry" onClick={initLive2D}>Retry</button>
        </div>
      )}

      {/* Main Transparent Canvas */}
      <div 
        className="canvas-wrapper" 
        ref={canvasRef} 
        onPointerDown={(e) => {
          (e.target as HTMLElement).setPointerCapture(e.pointerId);
          let winPos = [0, 0];
          try {
            const { ipcRenderer } = (window as any).require('electron');
            winPos = ipcRenderer.sendSync('get-window-pos');
          } catch (err) {}

          dragRef.current = {
            isDragging: true,
            startX: e.screenX,
            startY: e.screenY,
            winStartX: winPos[0],
            winStartY: winPos[1],
            hasMoved: false
          };
        }}
        onPointerMove={(e) => {
          if (dragRef.current.isDragging) {
            const dx = e.screenX - dragRef.current.startX;
            const dy = e.screenY - dragRef.current.startY;
            
            // If they moved more than 3 pixels, it's a drag, not a tap
            if (Math.abs(dx) > 3 || Math.abs(dy) > 3) {
              dragRef.current.hasMoved = true;
            }

            if (dragRef.current.hasMoved) {
              try {
                const { ipcRenderer } = (window as any).require('electron');
                const newX = Math.round(Number(dragRef.current.winStartX || 0) + Number(dx || 0));
                const newY = Math.round(Number(dragRef.current.winStartY || 0) + Number(dy || 0));
                
                if (!isNaN(newX) && !isNaN(newY)) {
                  ipcRenderer.send('set-window-pos', newX, newY);
                }
              } catch (err) {}
            }
          }
        }}
        onPointerUp={(e) => {
          (e.target as HTMLElement).releasePointerCapture(e.pointerId);
          dragRef.current.isDragging = false;
          
          // Tap-to-Talk Logic (only triggered if they didn't drag)
          if (!dragRef.current.hasMoved && state === 'ready') {
             if (listenState === 'idle') {
                startListening();
             } else if (listenState === 'listening') {
                stopListening();
             }
          }
        }}
      />

      {/* Floating minimalist status indicators */}
      {state === 'ready' && listenState === 'listening' && (
        <div style={{ position: 'absolute', top: 20, right: 20, color: '#ff4444', animation: 'pulse 1s infinite', fontSize: '24px', pointerEvents: 'none' }}>
          🎤
        </div>
      )}
      {state === 'ready' && listenState === 'processing' && (
        <div style={{ position: 'absolute', top: 20, right: 20, color: '#ffaa00', fontSize: '24px', pointerEvents: 'none' }}>
          ⏳
        </div>
      )}
    </>
  );
}

export default App;
