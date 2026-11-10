// Character Profile for Jian (简) - Sylphya Live2D Model Definition

export type AssistantEmotion =
  | 'neutral'
  | 'happy'
  | 'thinking'
  | 'concerned'
  | 'surprised'
  | 'sleeping'
  | 'excited'
  | 'embarrassed'
  | 'curious'
  | 'annoyed'
  | 'playful'
  | 'loving'
  // ── Extended Emotions ────────────────────────────────────────────────────
  | 'angry'
  | 'sad'
  | 'starstruck'
  | 'smug'
  | 'scared'
  | 'adoring'
  | 'bored'
  | 'tsundere'
  | 'overwhelmed';

// Gesture tokens — LLM can request any of these to activate hand/pose params
export type GestureToken =
  | 'idle'
  | 'wave_right'
  | 'wave_left'
  | 'both_hands'
  | 'point_right'
  | 'hand_up'
  | 'thinking_pose'
  | 'reach_out';

// Body posture tokens — override the procedural motion blend
export type BodyToken =
  | 'neutral'
  | 'lean_forward'
  | 'lean_back'
  | 'bow'
  | 'tremble'
  | 'sway'
  | 'rigid';

// Face effect overlay tokens — can stack multiple
export type FaceEffectToken =
  | 'blush'
  | 'sparkle'
  | 'heart_eyes'
  | 'tears'
  | 'angry_lines'
  | 'blank_eyes'
  | 'nosebleed'
  | 'dark';

export interface CharacterProfile {
  id: string;
  name: string;
  shortName: string;
  avatarIcon: string;
  modelPath: string;
  scaleMultiplier: number;
  offsetY: number;
  offsetX: number;
  pokeMessage: string;
  switchIds: string[];
  emotionMap: Record<AssistantEmotion, Record<string, number>>;
}

// ── GESTURE MAP ──────────────────────────────────────────────────────────────
// Maps gesture token → Live2D param overrides applied ON TOP of emotion params
export const GESTURE_MAP: Record<GestureToken, Record<string, number>> = {
  idle: {},
  wave_right: {
    ParamSwitch10: 1.0,  // Right hand raised
  },
  wave_left: {
    ParamSwitch11: 1.0,  // Left hand raised
  },
  both_hands: {
    ParamSwitch10: 1.0,
    ParamSwitch11: 1.0,
  },
  point_right: {
    ParamSwitch10: 0.6,
  },
  hand_up: {
    ParamSwitch10: 0.85,
    ParamAngleZ: -6,     // Slight body lean toward raised hand
  },
  thinking_pose: {
    ParamAngleZ: -12,    // Exaggerated head tilt
    ParamEyeBallX: -0.3,
    ParamEyeBallY: 0.5,
  },
  reach_out: {
    ParamSwitch10: 1.0,
    ParamSwitch11: 0.5,
    ParamAngleY: -5,     // Leaning toward viewer
  },
};

// ── BODY POSTURE MAP ─────────────────────────────────────────────────────────
// Each posture provides multipliers / overrides for the procedural body motion.
// Keys: angleXMul, angleZMul, bodyXMul, bodyZMul, rigidBlend (0–1 freezes motion)
// and optional direct param overrides.
export interface BodyPostureConfig {
  angleXBias: number;   // Added to procedural pAngleX
  angleYBias: number;   // Added to procedural pAngleY
  bodyXMul: number;     // Multiplies procedural pBodyAngleX amplitude
  bodyZMul: number;     // Multiplies procedural pBodyAngleZ amplitude
  rigidBlend: number;   // 0 = full procedural, 1 = fully frozen at bias values
  trembleAmp: number;   // Extra high-freq oscillation for scared/overwhelmed
}

export const BODY_MAP: Record<BodyToken, BodyPostureConfig> = {
  neutral:      { angleXBias:  0,   angleYBias:  0,  bodyXMul: 1.0, bodyZMul: 1.0, rigidBlend: 0,    trembleAmp: 0 },
  lean_forward: { angleXBias:  8,   angleYBias: -8,  bodyXMul: 0.6, bodyZMul: 0.6, rigidBlend: 0.3,  trembleAmp: 0 },
  lean_back:    { angleXBias: -6,   angleYBias:  5,  bodyXMul: 0.5, bodyZMul: 0.5, rigidBlend: 0.3,  trembleAmp: 0 },
  bow:          { angleXBias: -15,  angleYBias:  0,  bodyXMul: 0.4, bodyZMul: 0.4, rigidBlend: 0.5,  trembleAmp: 0 },
  tremble:      { angleXBias:  0,   angleYBias:  0,  bodyXMul: 1.2, bodyZMul: 1.2, rigidBlend: 0,    trembleAmp: 1.0 },
  sway:         { angleXBias:  0,   angleYBias:  0,  bodyXMul: 2.2, bodyZMul: 2.0, rigidBlend: 0,    trembleAmp: 0 },
  rigid:        { angleXBias:  0,   angleYBias:  0,  bodyXMul: 0.1, bodyZMul: 0.1, rigidBlend: 0.9,  trembleAmp: 0 },
};

// ── FACE EFFECT MAP ──────────────────────────────────────────────────────────
// Each token applies param overrides merged ON TOP of emotion base params.
// Face effects are additive — multiple can stack simultaneously.
export const FACE_FX_MAP: Record<FaceEffectToken, Record<string, number>> = {
  blush:       { ParamSwitch2: 1.0 },
  sparkle:     { ParamSwitch5: 1.0 },
  heart_eyes:  { ParamSwitch8: 1.0, ParamSwitch2: 0.35, ParamBrowLForm: 0.9, ParamBrowRForm: 0.9 },
  tears:       { ParamSwitch7: 1.0, ParamSwitch9: 1.0 },
  angry_lines: { ParamSwitch4: 1.0, ParamBrowLForm: -1.0, ParamBrowRForm: -1.0 },
  blank_eyes:  { ParamSwitch6: 1.0 },
  nosebleed:   { ParamSwitch3: 1.0 },
  dark:        { ParamSwitch1: 1.0, ParamSwitch21: 1.0 },
};

export const JIAN_CHARACTER: CharacterProfile = {
  id: 'jian',
  name: 'Jian (简)',
  shortName: 'Jian',
  avatarIcon: '🐱',
  modelPath: './runtime/jian/jian.model3.json',
  scaleMultiplier: 1.82,
  offsetY: 200,
  offsetX: 10,
  pokeMessage: '*pokes your cute cat ears*',
  switchIds: [
    'ParamSwitch1',  // 脸黑  — dark shadow
    'ParamSwitch2',  // 脸红  — blush
    'ParamSwitch3',  // 血    — nosebleed / intense flush
    'ParamSwitch4',  // 生气  — anger lines
    'ParamSwitch5',  // 星星眼 — star eyes
    'ParamSwitch6',  // 白眼  — blank eyes
    'ParamSwitch7',  // 泪花  — teary shimmer
    'ParamSwitch8',  // 爱心眼 — heart eyes
    'ParamSwitch9',  // 眼泪  — flowing tears
    'ParamSwitch10', // 右手  — right hand
    'ParamSwitch11', // 左手  — left hand
    'ParamSwitch21', // 高光消失 — highlight off
  ],
  emotionMap: {
    // ── CORE EMOTIONS ────────────────────────────────────────────────────────
    neutral: {
      ParamEyeLSmile: 0.65, ParamEyeRSmile: 0.65,
      ParamMouthForm: 0.85,
      ParamBrowLY: 0.1, ParamBrowRY: 0.1,
      ParamBrowLForm: 0.2, ParamBrowRForm: 0.2,
      ParamSwitch2: 0.35, // Soft blush
      Ear_smile: 0.25,
    },
    happy: {
      ParamEyeLSmile: 1.0, ParamEyeRSmile: 1.0,
      ParamMouthForm: 1.0,
      ParamBrowLY: 0.25, ParamBrowRY: 0.25,
      ParamBrowLForm: 0.5, ParamBrowRForm: 0.5,
      ParamSwitch2: 0.65, // Cheerful blush
      Ear_smile: 0.85,    // Perked cat ears
    },
    thinking: {
      ParamEyeLSmile: 0, ParamEyeRSmile: 0,
      ParamMouthForm: 0.0,
      ParamBrowLY: -0.35, ParamBrowRY: -0.35,
      ParamBrowLForm: -0.4, ParamBrowRForm: -0.4,
      ParamEyeBallX: -0.4, ParamEyeBallY: 0.4,
      ParamAngleZ: -5,
      ParamSwitch2: 0.1,
      Ear_smile: 0,
    },
    concerned: {
      ParamEyeLSmile: 0, ParamEyeRSmile: 0,
      ParamMouthForm: -0.6,
      ParamBrowLY: -0.35, ParamBrowRY: -0.35,
      ParamBrowLForm: 0.5, ParamBrowRForm: 0.5,
      ParamSwitch7: 0.9, // Teary shimmer
      ParamSwitch1: 0.35, // Worry shadow
      ParamAngleY: -4,
      Ear_smile: -0.3,
    },
    surprised: {
      ParamEyeLSmile: 0, ParamEyeRSmile: 0,
      ParamMouthForm: -0.2,
      ParamBrowLY: 0.8, ParamBrowRY: 0.8,
      ParamBrowLForm: -0.4, ParamBrowRForm: -0.4,
      ParamSwitch5: 1.0, // Star eyes
      ParamSwitch2: 0.4,
      Ear_smile: 0.75,
    },
    sleeping: {
      ParamEyeLOpen: 0.0, ParamEyeROpen: 0.0,
      ParamEyeLSmile: 0.4, ParamEyeRSmile: 0.4,
      ParamMouthForm: 0.1,
      ParamBrowLY: -0.15, ParamBrowRY: -0.15,
      ParamBrowLForm: 0.0, ParamBrowRForm: 0.0,
      ParamSwitch2: 0.25, // Gentle sleepy blush
      ParamAngleX: 2, ParamAngleY: -6, ParamAngleZ: -4,
      Ear_smile: -0.2,    // Relaxed cat ears
    },

    // ── EXPRESSIVE EMOTIONS ──────────────────────────────────────────────────
    excited: {
      // Wide eyes, huge smile, big blush, perked ears, body bounce via high breath
      ParamEyeLSmile: 1.0, ParamEyeRSmile: 1.0,
      ParamEyeLOpen: 1.3, ParamEyeROpen: 1.3,
      ParamMouthForm: 1.0,
      ParamBrowLY: 0.5, ParamBrowRY: 0.5,
      ParamBrowLForm: 0.6, ParamBrowRForm: 0.6,
      ParamSwitch2: 0.9,  // Intense blush
      ParamSwitch5: 0.55, // Partial star eyes
      Ear_smile: 1.0,
    },
    embarrassed: {
      // Downcast gaze, flushed cheeks, slight head tilt, ears drooping
      ParamEyeLSmile: 0.3, ParamEyeRSmile: 0.3,
      ParamEyeBallY: -0.5,
      ParamMouthForm: 0.3,
      ParamBrowLY: -0.1, ParamBrowRY: -0.1,
      ParamBrowLForm: 0.3, ParamBrowRForm: 0.3,
      ParamSwitch2: 1.0,  // Maximum blush
      ParamSwitch3: 0.6,  // Extra flush
      ParamAngleZ: -8,
      Ear_smile: -0.4,
    },
    curious: {
      // Head tilted, one-eye focus, ears perked forward, slight smirk
      ParamEyeLSmile: 0.4, ParamEyeRSmile: 0.7,
      ParamEyeLOpen: 1.1, ParamEyeROpen: 0.85,
      ParamMouthForm: 0.55,
      ParamBrowLY: 0.35, ParamBrowRY: 0.0,
      ParamBrowLForm: 0.2, ParamBrowRForm: -0.15,
      ParamSwitch2: 0.2,
      ParamAngleZ: -10,
      Ear_smile: 0.6,
    },
    annoyed: {
      // Half-closed eyes, flat mouth, furrowed brows, ears flat back
      ParamEyeLSmile: -0.3, ParamEyeRSmile: -0.3,
      ParamEyeLOpen: 0.45, ParamEyeROpen: 0.45,
      ParamMouthForm: -0.4,
      ParamBrowLY: -0.5, ParamBrowRY: -0.5,
      ParamBrowLForm: -0.6, ParamBrowRForm: -0.6,
      ParamSwitch1: 0.5,  // Shadow
      ParamSwitch2: 0.05,
      Ear_smile: -0.7,
    },
    playful: {
      // Wink left eye, smirk, head tilt, ears dancing
      ParamEyeLOpen: 0.05, ParamEyeROpen: 1.15, // Wink!
      ParamEyeLSmile: 1.0, ParamEyeRSmile: 0.8,
      ParamMouthForm: 0.85,
      ParamBrowLY: 0.4, ParamBrowRY: 0.2,
      ParamBrowLForm: 0.5, ParamBrowRForm: 0.3,
      ParamSwitch2: 0.55,
      ParamAngleZ: 8,
      Ear_smile: 0.9,
    },
    loving: {
      // Heart eyes, deep blush, soft smile, relaxed brows
      ParamEyeLSmile: 1.0, ParamEyeRSmile: 1.0,
      ParamMouthForm: 0.95,
      ParamBrowLY: 0.15, ParamBrowRY: 0.15,
      ParamBrowLForm: 0.35, ParamBrowRForm: 0.35,
      ParamSwitch5: 1.0,  // Star/heart eyes
      ParamSwitch2: 0.85, // Deep blush
      ParamAngleY: 3,
      Ear_smile: 0.7,
    },

    // ── NEW EXTENDED EMOTIONS ────────────────────────────────────────────────
    angry: {
      // Hard furrowed brows, narrowed eyes, flat mouth, anger lines, dark shadow
      ParamEyeLSmile: -0.5, ParamEyeRSmile: -0.5,
      ParamEyeLOpen: 0.3, ParamEyeROpen: 0.3,
      ParamMouthForm: -0.8,
      ParamBrowLY: -0.8, ParamBrowRY: -0.8,
      ParamBrowLForm: -1.0, ParamBrowRForm: -1.0,
      ParamSwitch4: 1.0,  // Anger lines
      ParamSwitch1: 0.8,  // Dark shadow
      ParamSwitch21: 0.9, // Eye highlight off
      ParamSwitch2: 0.0,
      ParamAngleY: -3,
      Ear_smile: -1.0,    // Ears slammed back
    },
    sad: {
      // Drooping brows, downcast eyes, slight open mouth, teary
      ParamEyeLSmile: -0.1, ParamEyeRSmile: -0.1,
      ParamEyeLOpen: 0.7, ParamEyeROpen: 0.7,
      ParamEyeBallY: -0.4,
      ParamMouthForm: -0.7,
      ParamBrowLY: -0.6, ParamBrowRY: -0.6,
      ParamBrowLForm: 0.4, ParamBrowRForm: 0.4,
      ParamSwitch7: 0.8,  // Teary shimmer
      ParamSwitch9: 0.5,  // Tears starting
      ParamSwitch2: 0.1,
      ParamAngleX: -4, ParamAngleY: -6,
      Ear_smile: -0.5,
    },
    starstruck: {
      // Maximum wide eyes with stars, agape mouth, full blush, perked ears
      ParamEyeLSmile: 0.8, ParamEyeRSmile: 0.8,
      ParamEyeLOpen: 1.4, ParamEyeROpen: 1.4,
      ParamMouthForm: -0.1, // Slightly open in awe
      ParamBrowLY: 0.9, ParamBrowRY: 0.9,
      ParamBrowLForm: -0.3, ParamBrowRForm: -0.3,
      ParamSwitch5: 1.0,  // Full star eyes
      ParamSwitch2: 0.75, // Blush from amazement
      Ear_smile: 1.0,
    },
    smug: {
      // Half-lidded confident eyes, corner smirk, slight back lean
      ParamEyeLSmile: 0.5, ParamEyeRSmile: 0.3,
      ParamEyeLOpen: 0.55, ParamEyeROpen: 0.65,
      ParamMouthForm: 0.6,
      ParamBrowLY: 0.1, ParamBrowRY: -0.1,
      ParamBrowLForm: 0.0, ParamBrowRForm: -0.2,
      ParamSwitch6: 0.4,  // Mild blank/deadpan eye tint
      ParamSwitch2: 0.15,
      ParamAngleZ: 5,     // Slight confident tilt
      Ear_smile: 0.3,
    },
    scared: {
      // Wide trembling eyes, raised brows, open mouth, ears flat
      ParamEyeLSmile: -0.2, ParamEyeRSmile: -0.2,
      ParamEyeLOpen: 1.5, ParamEyeROpen: 1.5,
      ParamMouthForm: -0.5,
      ParamBrowLY: 0.9, ParamBrowRY: 0.9,
      ParamBrowLForm: -0.5, ParamBrowRForm: -0.5,
      ParamSwitch2: 0.2,
      ParamAngleX: -6, // Head pulling back
      Ear_smile: -0.8,
    },
    adoring: {
      // Heart eyes, full blush, soft dreamy smile, gentle brows
      ParamEyeLSmile: 1.0, ParamEyeRSmile: 1.0,
      ParamEyeLOpen: 0.8, ParamEyeROpen: 0.8,
      ParamMouthForm: 0.9,
      ParamBrowLY: 0.2, ParamBrowRY: 0.2,
      ParamBrowLForm: 0.5, ParamBrowRForm: 0.5,
      ParamSwitch8: 1.0,  // Heart eyes
      ParamSwitch2: 0.9,  // Deep blush
      ParamAngleY: 4,     // Looking up softly
      Ear_smile: 0.6,
    },
    bored: {
      // Drooping half-lidded blank stare, flat ears, dead expression
      ParamEyeLSmile: -0.4, ParamEyeRSmile: -0.4,
      ParamEyeLOpen: 0.35, ParamEyeROpen: 0.35,
      ParamMouthForm: 0.1,
      ParamBrowLY: -0.3, ParamBrowRY: -0.3,
      ParamBrowLForm: 0.0, ParamBrowRForm: 0.0,
      ParamSwitch6: 0.7,  // Blank eyes
      ParamSwitch2: 0.0,
      ParamAngleY: 2,     // Slight lethargic lean
      Ear_smile: -0.6,
    },
    tsundere: {
      // Embarrassed blush + slight annoyance: hand up, pout, flushed
      ParamEyeLSmile: 0.1, ParamEyeRSmile: 0.1,
      ParamEyeLOpen: 0.7, ParamEyeROpen: 0.7,
      ParamMouthForm: -0.2, // Slight pout
      ParamBrowLY: -0.3, ParamBrowRY: -0.3,
      ParamBrowLForm: -0.3, ParamBrowRForm: -0.3,
      ParamSwitch2: 0.9,  // Max blush
      ParamSwitch4: 0.4,  // Mild anger lines
      ParamAngleZ: -6,
      Ear_smile: -0.3,
    },
    overwhelmed: {
      // Excited but crying: star eyes with tears, trembling
      ParamEyeLSmile: 0.7, ParamEyeRSmile: 0.7,
      ParamEyeLOpen: 1.2, ParamEyeROpen: 1.2,
      ParamMouthForm: 0.6,
      ParamBrowLY: 0.5, ParamBrowRY: 0.5,
      ParamBrowLForm: 0.2, ParamBrowRForm: 0.2,
      ParamSwitch5: 0.8,  // Star eyes
      ParamSwitch7: 1.0,  // Teary shimmer
      ParamSwitch9: 0.8,  // Flowing tears
      ParamSwitch2: 0.6,  // Blush
      Ear_smile: 0.5,
    },
  },
};

/**
 * Factory function returning Jian's CharacterProfile configuration.
 */
export function getJianCharacter(): CharacterProfile {
  return JIAN_CHARACTER;
}

export const CHARACTERS: Record<string, CharacterProfile> = {
  jian: JIAN_CHARACTER,
};

export default JIAN_CHARACTER;
