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
  | 'loving';

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
    'ParamSwitch1', 'ParamSwitch2', 'ParamSwitch3', 'ParamSwitch4',
    'ParamSwitch5', 'ParamSwitch6', 'ParamSwitch7', 'ParamSwitch8',
    'ParamSwitch9', 'ParamSwitch10', 'ParamSwitch11', 'ParamSwitch21'
  ],
  emotionMap: {
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
      Ear_smile: 0.85, // Perked cat ears
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
      Ear_smile: -0.2, // Relaxed cat ears
    },

    // ── NEW EXPRESSIVE EMOTIONS ──────────────────────────────────────────────

    excited: {
      // Wide eyes, huge smile, big blush, perked ears, body bounce via high breath
      ParamEyeLSmile: 1.0, ParamEyeRSmile: 1.0,
      ParamEyeLOpen: 1.3, ParamEyeROpen: 1.3,
      ParamMouthForm: 1.0,
      ParamBrowLY: 0.5, ParamBrowRY: 0.5,
      ParamBrowLForm: 0.6, ParamBrowRForm: 0.6,
      ParamSwitch2: 0.9,   // Intense blush
      ParamSwitch5: 0.55,  // Partial star eyes
      Ear_smile: 1.0,
    },

    embarrassed: {
      // Downcast gaze, flushed cheeks, slight head tilt, ears drooping
      ParamEyeLSmile: 0.3, ParamEyeRSmile: 0.3,
      ParamEyeBallY: -0.5,
      ParamMouthForm: 0.3,
      ParamBrowLY: -0.1, ParamBrowRY: -0.1,
      ParamBrowLForm: 0.3, ParamBrowRForm: 0.3,
      ParamSwitch2: 1.0,   // Maximum blush
      ParamSwitch3: 0.6,   // Extra flush
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
      ParamSwitch1: 0.5,   // Shadow
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
      ParamSwitch5: 1.0,   // Star/heart eyes
      ParamSwitch2: 0.85,  // Deep blush
      ParamAngleY: 3,
      Ear_smile: 0.7,
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
