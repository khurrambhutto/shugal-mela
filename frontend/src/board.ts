// The Ludo board: geometry from rules progress to grid cells, the static SVG, and token motion.
//
// The board is a 15 x 15 grid. Red's yard is top-left and play runs clockwise:
// red, green, yellow, blue. Track index 0 is red's start square, matching
// START in backend/app/ludo/rules.py (red 0, green 13, yellow 26, blue 39).

import type { Colour, MatchEvent, MatchState } from "./protocol";

type Cell = readonly [number, number];
interface Point {
  x: number;
  y: number;
}

export const COLOURS: readonly Colour[] = ["red", "green", "yellow", "blue"];
const START: Record<Colour, number> = { red: 0, green: 13, yellow: 26, blue: 39 };
const HOME = 56;
const STAR_TRACK = new Set([8, 21, 34, 47]);

function run(from: Cell, dx: number, dy: number, count: number): Cell[] {
  return Array.from({ length: count }, (_, i) => [from[0] + dx * i, from[1] + dy * i] as const);
}

// The 52 shared squares, clockwise from red's start.
export const TRACK: readonly Cell[] = [
  ...run([1, 6], 1, 0, 5),
  ...run([6, 5], 0, -1, 6),
  ...run([7, 0], 1, 0, 2),
  ...run([8, 1], 0, 1, 5),
  ...run([9, 6], 1, 0, 6),
  ...run([14, 7], 0, 1, 2),
  ...run([13, 8], -1, 0, 5),
  ...run([8, 9], 0, 1, 6),
  ...run([7, 14], -1, 0, 2),
  ...run([6, 13], 0, -1, 5),
  ...run([5, 8], -1, 0, 6),
  ...run([0, 7], 0, -1, 2),
];

const HOME_COLUMN: Record<Colour, readonly Cell[]> = {
  red: run([1, 7], 1, 0, 5),
  green: run([7, 1], 0, 1, 5),
  yellow: run([13, 7], -1, 0, 5),
  blue: run([7, 13], 0, -1, 5),
};

const YARD_ORIGIN: Record<Colour, Cell> = { red: [0, 0], green: [9, 0], yellow: [9, 9], blue: [0, 9] };
const YARD_SPOTS: readonly Cell[] = [
  [2, 2],
  [4, 2],
  [2, 4],
  [4, 4],
];
// Where finished tokens gather, inside each colour's centre triangle.
const HOME_POINT: Record<Colour, Point> = {
  red: { x: 6.55, y: 7.5 },
  green: { x: 7.5, y: 6.55 },
  yellow: { x: 8.45, y: 7.5 },
  blue: { x: 7.5, y: 8.45 },
};

const center = ([c, r]: Cell): Point => ({ x: c + 0.5, y: r + 0.5 });

export function tokenPoint(colour: Colour, progress: number, token: number): Point {
  if (progress < 0) {
    const [ox, oy] = YARD_ORIGIN[colour];
    const [sx, sy] = YARD_SPOTS[token]!;
    return { x: ox + sx, y: oy + sy };
  }
  if (progress >= HOME) {
    const p = HOME_POINT[colour];
    const spread = [-0.22, -0.07, 0.07, 0.22][token]!;
    return colour === "red" || colour === "yellow" ? { x: p.x, y: p.y + spread } : { x: p.x + spread, y: p.y };
  }
  if (progress > 50) return center(HOME_COLUMN[colour][progress - 51]!);
  return center(TRACK[(START[colour] + progress) % TRACK.length]!);
}

/** Every square a token visits, in order, moving between two progress values. */
export function hopPath(colour: Colour, from: number, to: number, token: number): Point[] {
  if (from < 0) return [tokenPoint(colour, 0, token)];
  const points: Point[] = [];
  for (let p = from + 1; p <= to; p++) points.push(tokenPoint(colour, p, token));
  return points;
}

// Static board drawing

const SVG_NS = "http://www.w3.org/2000/svg";

function svg<K extends keyof SVGElementTagNameMap>(
  tag: K,
  attrs: Record<string, string | number>,
  ...children: SVGElement[]
): SVGElementTagNameMap[K] {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, String(v));
  node.append(...children);
  return node;
}

function star(cx: number, cy: number, r: number): string {
  const points: string[] = [];
  for (let i = 0; i < 10; i++) {
    const radius = i % 2 === 0 ? r : r * 0.45;
    const angle = (Math.PI / 5) * i - Math.PI / 2;
    points.push(`${(cx + radius * Math.cos(angle)).toFixed(3)},${(cy + radius * Math.sin(angle)).toFixed(3)}`);
  }
  return points.join(" ");
}

function drawBoard(): SVGSVGElement {
  const root = svg("svg", { viewBox: "0 0 15 15", class: "board-svg", "aria-hidden": "true" });
  root.append(svg("rect", { x: 0, y: 0, width: 15, height: 15, class: "sq-base" }));

  for (const colour of COLOURS) {
    const [ox, oy] = YARD_ORIGIN[colour];
    const yard = svg(
      "g",
      { class: `yard yard-${colour}`, "data-colour": colour },
      svg("rect", { x: ox, y: oy, width: 6, height: 6, class: `fill-${colour}` }),
      svg("rect", { x: ox + 0.85, y: oy + 0.85, width: 4.3, height: 4.3, rx: 0.55, class: "yard-court" }),
      ...YARD_SPOTS.map(([sx, sy]) =>
        svg("circle", { cx: ox + sx, cy: oy + sy, r: 0.56, class: `yard-well well-${colour}` }),
      ),
    );
    root.append(yard);
  }

  TRACK.forEach((cell, index) => {
    const startOf = COLOURS.find((c) => START[c] === index);
    const cls = startOf ? `sq fill-${startOf}` : "sq";
    root.append(svg("rect", { x: cell[0], y: cell[1], width: 1, height: 1, class: cls }));
    if (STAR_TRACK.has(index)) {
      root.append(svg("polygon", { points: star(cell[0] + 0.5, cell[1] + 0.5, 0.36), class: "glyph-star" }));
    } else if (startOf) {
      root.append(svg("circle", { cx: cell[0] + 0.5, cy: cell[1] + 0.5, r: 0.26, class: "glyph-start" }));
    }
  });
  for (const colour of COLOURS) {
    for (const cell of HOME_COLUMN[colour]) {
      root.append(svg("rect", { x: cell[0], y: cell[1], width: 1, height: 1, class: `sq fill-${colour}` }));
    }
  }

  const triangles: Record<Colour, string> = {
    red: "6,6 6,9 7.5,7.5",
    green: "6,6 9,6 7.5,7.5",
    yellow: "9,6 9,9 7.5,7.5",
    blue: "6,9 9,9 7.5,7.5",
  };
  for (const colour of COLOURS) root.append(svg("polygon", { points: triangles[colour], class: `fill-${colour} centre-tri` }));
  root.append(svg("rect", { x: 6, y: 6, width: 3, height: 3, class: "centre-edge" }));
  return root;
}

// Tokens and motion

const EASE_IN_OUT = "cubic-bezier(0.77, 0, 0.175, 1)";
const EASE_OUT = "cubic-bezier(0.23, 1, 0.32, 1)";
const HOP_MS = 150;

interface Placement {
  point: Point;
  scale: number;
}

function transformFor({ point, scale }: Placement): string {
  // Translate percentages are relative to the token itself, which is exactly one cell.
  return `translate(${((point.x - 0.5) * 100).toFixed(2)}%, ${((point.y - 0.5) * 100).toFixed(2)}%) scale(${scale})`;
}

function placements(match: MatchState): Map<string, Placement> {
  const result = new Map<string, Placement>();
  const groups = new Map<string, string[]>();
  for (const colour of match.colours) {
    match.tokens[colour]!.forEach((progress, token) => {
      const key = `${colour}-${token}`;
      const point = tokenPoint(colour, progress, token);
      result.set(key, { point, scale: progress >= HOME ? 0.62 : 1 });
      if (progress >= 0 && progress < HOME) {
        const cell = `${Math.floor(point.x)},${Math.floor(point.y)}`;
        groups.set(cell, [...(groups.get(cell) ?? []), key]);
      }
    });
  }
  // Tokens sharing a square shrink and fan out so each stays visible and clickable.
  const fan = [
    [],
    [[0, 0]],
    [[-0.2, 0], [0.2, 0]],
    [[-0.2, -0.16], [0.2, -0.16], [0, 0.18]],
    [[-0.2, -0.2], [0.2, -0.2], [-0.2, 0.2], [0.2, 0.2]],
  ];
  for (const keys of groups.values()) {
    if (keys.length < 2) continue;
    const offsets = fan[Math.min(keys.length, 4)]!;
    keys.forEach((key, i) => {
      const p = result.get(key)!;
      const [dx, dy] = offsets[i % offsets.length]!;
      result.set(key, { point: { x: p.point.x + dx!, y: p.point.y + dy! }, scale: keys.length > 2 ? 0.62 : 0.74 });
    });
  }
  return result;
}

export interface BoardOptions {
  onMove(token: number): void;
  reducedMotion(): boolean;
}

export class BoardView {
  readonly element: HTMLElement;
  private readonly stage: HTMLElement;
  private readonly tokens = new Map<string, HTMLButtonElement>();
  private shown: MatchState | null = null;
  private pending: { match: MatchState | null; me: Colour | null } | null = null;
  private me: Colour | null = null;
  private animating = false;

  constructor(private readonly options: BoardOptions) {
    this.stage = document.createElement("div");
    this.stage.className = "board-stage";
    this.stage.append(drawBoard());
    for (const colour of COLOURS) {
      for (let token = 0; token < 4; token++) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = `token token-${colour}`;
        button.dataset.colour = colour;
        button.dataset.token = String(token);
        button.disabled = true;
        button.style.transform = transformFor({ point: tokenPoint(colour, -1, token), scale: 1 });
        button.addEventListener("click", () => {
          // One pick per turn: nothing else is movable until the next state arrives.
          this.setInteractive(null, null);
          this.options.onMove(token);
        });
        this.tokens.set(`${colour}-${token}`, button);
        this.stage.append(button);
      }
    }
    const frame = document.createElement("div");
    frame.className = "board-frame";
    frame.append(this.stage);
    this.element = frame;
  }

  update(match: MatchState | null, me: Colour | null): void {
    this.pending = { match, me };
    this.me = me;
    if (!this.animating) void this.flush();
  }

  /** Restores the movable tokens after a refused move. */
  refresh(): void {
    if (!this.animating && !this.pending) this.setInteractive(this.shown, this.me);
  }

  private async flush(): Promise<void> {
    while (this.pending) {
      const { match, me } = this.pending;
      this.pending = null;
      const previous = this.shown;
      this.shown = match;
      this.setInteractive(null, null);

      if (match === null) {
        this.showIdle();
        continue;
      }
      const sequential =
        previous !== null && previous.match_id === match.match_id && match.step === previous.step + 1;
      if (sequential && !this.options.reducedMotion() && !this.pending) {
        this.animating = true;
        try {
          await this.animate(previous, match);
        } finally {
          this.animating = false;
        }
      }
      this.place(match);
      this.setInteractive(match, me);
    }
  }

  private showIdle(): void {
    this.stage.dataset.turn = "";
    for (const [key, el] of this.tokens) {
      const [colour, token] = key.split("-") as [Colour, string];
      el.hidden = false;
      el.classList.add("is-idle");
      el.style.transform = transformFor({ point: tokenPoint(colour, -1, Number(token)), scale: 1 });
    }
  }

  private place(match: MatchState): void {
    const layout = placements(match);
    for (const [key, el] of this.tokens) {
      const placement = layout.get(key);
      el.hidden = placement === undefined;
      el.classList.remove("is-idle");
      if (placement) el.style.transform = transformFor(placement);
    }
    this.stage.dataset.turn = match.status === "playing" ? match.current : "";
  }

  private setInteractive(match: MatchState | null, me: Colour | null): void {
    const canMove =
      match !== null && match.status === "playing" && match.phase === "awaiting_move" && match.current === me;
    for (const [key, el] of this.tokens) {
      const [colour, token] = key.split("-") as [Colour, string];
      const movable = canMove && colour === me && match.legal_moves.includes(Number(token));
      el.disabled = !movable;
      el.classList.toggle("is-movable", movable);
      el.setAttribute(
        "aria-label",
        movable ? `Move ${colour} token ${Number(token) + 1}` : `${colour} token ${Number(token) + 1}`,
      );
    }
  }

  private async animate(previous: MatchState, next: MatchState): Promise<void> {
    const moves = next.events.filter((e): e is Extract<MatchEvent, { kind: "moved" }> => e.kind === "moved");
    const captures = next.events.filter((e): e is Extract<MatchEvent, { kind: "captured" }> => e.kind === "captured");
    const before = placements(previous);

    for (const move of moves) {
      const el = this.tokens.get(`${move.colour}-${move.token}`);
      const start = before.get(`${move.colour}-${move.token}`);
      if (!el || !start) continue;
      const path = hopPath(move.colour, move.from_progress, move.to_progress, move.token);
      const frames: Keyframe[] = [{ transform: transformFor(start), offset: 0, easing: EASE_IN_OUT }];
      path.forEach((point, i) => {
        const at = (i + 1) / path.length;
        const mid = (i + 0.5) / path.length;
        const from = i === 0 ? start.point : path[i - 1]!;
        // Each hop lifts toward its midpoint and settles on the square.
        frames.push({ transform: transformFor({ point: lerp(from, point), scale: 1.16 }), offset: mid, easing: EASE_IN_OUT });
        frames.push({ transform: transformFor({ point, scale: 1 }), offset: at, easing: EASE_IN_OUT });
      });
      el.classList.add("is-hopping");
      await el.animate(frames, { duration: Math.max(220, path.length * HOP_MS) })
        .finished.catch(() => undefined);
      el.classList.remove("is-hopping");
      el.style.transform = transformFor({ point: path[path.length - 1]!, scale: 1 });
    }

    await Promise.all(
      captures.map(async (capture) => {
        const el = this.tokens.get(`${capture.colour}-${capture.token}`);
        const start = before.get(`${capture.colour}-${capture.token}`);
        if (!el || !start) return;
        const home = { point: tokenPoint(capture.colour, -1, capture.token), scale: 1 };
        el.style.transform = transformFor(home);
        await el
          .animate(
            [
              { transform: transformFor({ ...start, scale: 1.25 }), opacity: 1 },
              { transform: transformFor({ ...start, scale: 0.7 }), opacity: 0.5, offset: 0.25, easing: EASE_IN_OUT },
              { transform: transformFor(home), opacity: 1 },
            ],
            { duration: 520, easing: EASE_OUT },
          )
          .finished.catch(() => undefined);
      }),
    );
  }
}

function lerp(a: Point, b: Point): Point {
  return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
}
