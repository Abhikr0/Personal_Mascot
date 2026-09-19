declare module 'pixi-live2d-display' {
  import * as PIXI from 'pixi.js';

  export interface Live2DModelOptions {
    autoInteract?: boolean;
    autoUpdate?: boolean;
    idleMotionGroup?: string;
  }

  export class Live2DModel extends PIXI.Sprite {
    static from(
      source: string | object,
      options?: Live2DModelOptions
    ): Promise<Live2DModel>;

    static registerTicker(ticker: typeof PIXI.Ticker): void;

    motion(group: string, index?: number, priority?: number): Promise<boolean>;

    update(dt: number): void;

    interactive: boolean;
    deltaTime: number;
    internalModel: any;
    focus(x: number, y: number, instant?: boolean): void;
    tap(x: number, y: number): void;
  }
}
