declare module 'pixi-live2d-display' {
  import * as PIXI from 'pixi.js';

  export interface Live2DModelOptions {
    autoInteract?: boolean;
    autoUpdate?: boolean;
  }

  export class Live2DModel extends PIXI.Sprite {
    static from(
      source: string | object,
      options?: Live2DModelOptions
    ): Promise<Live2DModel>;

    motion(group: string, index?: number, priority?: number): Promise<boolean>;

    interactive: boolean;
  }
}
