// A 3D CSS die. Each roll tumbles toward the rolled face.

import type { Colour } from "./protocol";

const PIPS: Record<number, number[]> = {
  1: [5],
  2: [3, 7],
  3: [3, 5, 7],
  4: [1, 3, 7, 9],
  5: [1, 3, 5, 7, 9],
  6: [1, 3, 4, 6, 7, 9],
};
// Cube rotation that brings each face to the front.
const FACE_ANGLES: Record<number, [number, number]> = {
  1: [0, 0],
  2: [0, -90],
  3: [-90, 0],
  4: [90, 0],
  5: [0, 90],
  6: [0, 180],
};
const FACE_CLASS: Record<number, string> = { 1: "front", 2: "right", 3: "top", 4: "bottom", 5: "left", 6: "back" };

const rotation = ([x, y]: [number, number]) => `rotateX(${x}deg) rotateY(${y}deg)`;

export class DieView {
  readonly element: HTMLElement;
  private readonly cube: HTMLElement;
  private value = 1;

  constructor(private readonly reducedMotion: () => boolean) {
    this.cube = document.createElement("div");
    this.cube.className = "die-cube";
    for (let value = 1; value <= 6; value++) {
      const face = document.createElement("div");
      face.className = `die-face die-${FACE_CLASS[value]}`;
      for (let slot = 1; slot <= 9; slot++) {
        const pip = document.createElement("span");
        if (PIPS[value]!.includes(slot)) pip.className = "pip";
        face.append(pip);
      }
      this.cube.append(face);
    }
    this.cube.style.transform = rotation(FACE_ANGLES[1]!);
    this.element = document.createElement("div");
    this.element.className = "die";
    this.element.setAttribute("role", "img");
    this.element.append(this.cube);
    this.label();
  }

  colour(colour: Colour | null): void {
    this.element.dataset.colour = colour ?? "";
  }

  show(value: number): void {
    this.value = value;
    this.cube.getAnimations().forEach((a) => a.cancel());
    this.cube.style.transform = rotation(FACE_ANGLES[value]!);
    this.label();
  }

  async tumble(value: number): Promise<void> {
    this.show(value);
    if (this.reducedMotion()) return;
    const [x, y] = FACE_ANGLES[value]!;
    // Two full turns on one axis and one and a half on the other read as a real throw.
    const spinX = 720 * (Math.random() < 0.5 ? 1 : -1);
    const spinY = 540 * (Math.random() < 0.5 ? 1 : -1);
    await this.cube
      .animate(
        [
          { transform: `translateY(-14%) ${rotation([x - spinX, y - spinY])}` },
          { transform: `translateY(4%) ${rotation([x - spinX * 0.15, y - spinY * 0.15])}`, offset: 0.7 },
          { transform: `translateY(0) ${rotation([x, y])}` },
        ],
        { duration: 620, easing: "cubic-bezier(0.23, 1, 0.32, 1)" },
      )
      .finished.catch(() => undefined);
  }

  private label(): void {
    this.element.setAttribute("aria-label", `Die showing ${this.value}`);
  }
}
