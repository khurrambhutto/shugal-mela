// DOM rendering. All player-supplied text is set with textContent, never as HTML.

import { BoardView } from "./board";
import { DieView } from "./dice";
import { COLOURS } from "./board";
import { COLOUR_NAMES, lobbyStatus, pausedFor, seatNote, seatOf, seatPlan, secondsLeft } from "./game";
import type { ChatMessage, Colour, MatchState, RoomSnapshot } from "./protocol";
import { canSubmit, type AppState, type ConnectionStatus } from "./state";

export interface UiActions {
  start(nickname: string): void;
  reconnect(): void;
  create(capacity: 2 | 4): void;
  join(code: string): void;
  leave(): void;
  send(text: string): Promise<boolean>;
  ready(ready: boolean): void;
  startMatch(): void;
  roll(): Promise<void>;
  move(token: number): Promise<boolean>;
}

const STATUS_LABELS: Record<ConnectionStatus, string> = {
  idle: "Not connected",
  connecting: "Connecting…",
  connected: "Connected",
  reconnecting: "Reconnecting…",
  offline: "Offline",
};

const reducedMotion = (): boolean => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function el<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  props: Partial<HTMLElementTagNameMap[K]> = {},
  ...children: (Node | string)[]
): HTMLElementTagNameMap[K] {
  const node = Object.assign(document.createElement(tag), props);
  node.append(...children);
  return node;
}

export function createUi(root: HTMLElement, actions: UiActions): (state: AppState) => void {
  // Shared chrome
  const status = el("p", { className: "status" });
  status.setAttribute("role", "status");
  const who = el("span", { className: "who" });
  const notice = el("p", { className: "notice" });
  notice.setAttribute("role", "alert");
  const reconnect = el("button", { type: "button", className: "btn btn-light", textContent: "Reconnect" });
  reconnect.addEventListener("click", () => actions.reconnect());

  // Welcome
  const nicknameInput = el("input", { name: "nickname", maxLength: 24, required: true });
  nicknameInput.setAttribute("autocomplete", "nickname");
  nicknameInput.value = loadNickname();
  const welcome = el(
    "form",
    { className: "welcome" },
    el("p", { className: "lede", textContent: "Ludo with your friends, wherever they are tonight." }),
    el("label", { className: "field" }, el("span", { textContent: "Nickname" }), nicknameInput),
    el("button", { type: "submit", className: "btn btn-marigold", textContent: "Continue" }),
  );
  welcome.addEventListener("submit", (event) => {
    event.preventDefault();
    const nickname = nicknameInput.value.trim();
    if (!nickname) return;
    saveNickname(nickname);
    actions.start(nickname);
  });

  // Lobby
  const create2 = el("button", { type: "button", className: "btn btn-marigold", textContent: "Create 2-player room" });
  const create4 = el("button", { type: "button", className: "btn btn-light", textContent: "Create 4-player room" });
  create2.addEventListener("click", () => actions.create(2));
  create4.addEventListener("click", () => actions.create(4));
  const codeInput = el("input", { name: "code", maxLength: 6, placeholder: "ABCD23", spellcheck: false });
  codeInput.autocomplete = "off";
  codeInput.className = "code-input";
  const joinButton = el("button", { type: "submit", className: "btn btn-light", textContent: "Join" });
  const joinForm = el(
    "form",
    { className: "join" },
    el("label", { className: "field" }, el("span", { textContent: "Room code" }), codeInput),
    joinButton,
  );
  joinForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const code = codeInput.value.trim();
    if (code) actions.join(code);
  });
  const lobby = el(
    "section",
    { className: "lobby" },
    el("h2", { textContent: "Start a table" }),
    el("div", { className: "row" }, create2, create4),
    el("p", { className: "or", textContent: "or join a friend's room" }),
    joinForm,
  );

  // Room: header
  const roomCode = el("strong", { className: "room-code" });
  const copyButton = el("button", { type: "button", className: "btn btn-ghost copy", textContent: "Copy" });
  copyButton.addEventListener("click", () => {
    void navigator.clipboard?.writeText(roomCode.textContent ?? "").then(() => {
      copyButton.textContent = "Copied";
      window.setTimeout(() => (copyButton.textContent = "Copy"), 1400);
    });
  });
  const seats = el("span", { className: "seats" });
  const leaveButton = el("button", { type: "button", className: "btn btn-ghost", textContent: "Leave room" });
  leaveButton.addEventListener("click", () => actions.leave());
  const roomBar = el(
    "div",
    { className: "room-bar" },
    el("div", { className: "room-id" }, el("span", { className: "label", textContent: "Room" }), roomCode, copyButton),
    seats,
    leaveButton,
  );

  // Room: board, with each player's die and name at their corner
  // A picked token holds the board still until the server answers; a refusal lets the player pick again.
  const board = new BoardView({
    onMove: (token) => void actions.move(token).then((ok) => ok || board.refresh()),
    reducedMotion,
  });
  const banner = el("div", { className: "banner" });
  banner.hidden = true;
  const pauseTitle = el("p", { className: "banner-title", textContent: "Paused" });
  const pauseText = el("p");
  const pauseBanner = el("div", { className: "banner pause" }, pauseTitle, pauseText);
  pauseBanner.hidden = true;
  pauseBanner.setAttribute("role", "status");
  const boardWrap = el("div", { className: "board-wrap" }, board.element, banner, pauseBanner);

  const rollButton = el("button", { type: "button", className: "btn btn-roll", textContent: "Roll" });
  rollButton.addEventListener("click", () => {
    rollButton.disabled = true;
    void actions.roll();
  });
  const seatViews = new Map(COLOURS.map((colour) => [colour, new SeatView(colour, reducedMotion)]));
  for (const seat of seatViews.values()) {
    // The die itself is a shortcut for the Roll button beside it.
    seat.die.element.addEventListener("click", () => {
      if (seat.element.contains(rollButton) && !rollButton.hidden && !rollButton.disabled) rollButton.click();
    });
  }

  const readyButton = el("button", { type: "button", className: "btn btn-marigold" });
  readyButton.addEventListener("click", () => actions.ready(readyButton.dataset.ready !== "true"));
  const startButton = el("button", { type: "button", className: "btn btn-marigold", textContent: "Start match" });
  startButton.addEventListener("click", () => actions.startMatch());
  const lobbyHint = el("p", { className: "hint" });
  const lobbyPanel = el("div", { className: "table-lobby" }, lobbyHint, el("div", { className: "row" }, readyButton, startButton));
  const stage = el("div", { className: "stage" }, ...[...seatViews.values()].map((s) => s.element), boardWrap, lobbyPanel);

  // Room: chat
  const messageList = el("ol", { className: "messages" });
  messageList.setAttribute("aria-live", "polite");
  const chatInput = el("input", { name: "text", maxLength: 500, placeholder: "Message" });
  chatInput.autocomplete = "off";
  const sendButton = el("button", { type: "submit", className: "btn btn-light", textContent: "Send" });
  const composer = el("form", { className: "composer" }, chatInput, sendButton);
  composer.addEventListener("submit", (event) => {
    event.preventDefault();
    const text = chatInput.value.trim();
    if (!text) return;
    void actions.send(text).then((sent) => {
      if (sent && chatInput.value.trim() === text) chatInput.value = "";
    });
  });
  const side = el(
    "aside",
    { className: "side" },
    el("section", { className: "panel chat" }, el("h2", { textContent: "Chat" }), messageList, composer),
  );
  const room = el("section", { className: "room" }, roomBar, el("div", { className: "table" }, stage, side));

  const header = el(
    "header",
    { className: "masthead" },
    el("h1", { className: "wordmark", textContent: "Shugal Mela" }),
    el("div", { className: "conn" }, who, status),
  );
  root.replaceChildren(header, notice, reconnect, welcome, lobby, room);

  let renderedRoom: RoomSnapshot | null = null;
  let renderedLive = false;
  let shownStep: string | null = null;
  // When the rendered snapshot arrived, for counting down away players' time.
  let snapshotAt = 0;
  window.setInterval(tickAway, 1000);

  return (state: AppState): void => {
    const live = canSubmit(state);
    const me = state.session?.session_id ?? null;
    status.dataset.state = state.status;
    status.textContent = STATUS_LABELS[state.status];
    who.textContent = state.session ? state.session.nickname : "";
    notice.textContent = state.notice ?? "";
    notice.hidden = state.notice === null;

    reconnect.hidden = !(state.status === "offline" && state.session !== null);
    welcome.hidden = state.session !== null || state.status === "connecting";
    lobby.hidden = state.session === null || state.room !== null || state.status !== "connected";
    room.hidden = state.room === null;
    document.body.dataset.screen = state.room ? "room" : "front";

    const busy = state.pendingRoom !== null;
    for (const control of [create2, create4, codeInput, joinButton]) control.disabled = !live || busy;
    if (state.status === "offline" && state.lastRoomCode && !codeInput.value) codeInput.value = state.lastRoomCode;
    for (const control of [chatInput, sendButton, leaveButton]) control.disabled = !live;

    const snapshot = state.room;
    room.dataset.offline = String(!live);
    if (snapshot !== renderedRoom || live !== renderedLive) {
      if (snapshot !== renderedRoom) snapshotAt = performance.now();
      renderedRoom = snapshot;
      renderedLive = live;
      if (snapshot) renderRoom(snapshot, me, live);
    }
    if (snapshot) renderControls(snapshot, me, live);
  };

  function renderRoom(snapshot: RoomSnapshot, me: string | null, live: boolean): void {
    roomCode.textContent = snapshot.code;
    seats.textContent = `${snapshot.members.length}/${snapshot.capacity} players`;
    const match = snapshot.match;
    const myColour = seatOf(match, me);

    const plan = seatPlan(snapshot);
    const playing = match?.status === "playing";
    stage.dataset.players = String(plan.size);
    for (const [colour, seat] of seatViews) {
      const member = plan.get(colour) ?? null;
      const tags: string[] = [];
      if (member && member.session_id === snapshot.host) tags.push("Host");
      if (member && !playing && snapshot.ready.includes(member.session_id)) tags.push("Ready");
      seat.update({
        name: member ? (member.session_id === me ? `${member.nickname} (you)` : member.nickname) : null,
        tags: tags.join(" · "),
        note: seatNote(snapshot, colour, myColour),
        // Out of play during a match; open for someone to take in the lobby.
        empty: !playing && snapshot.members.length < snapshot.capacity && (snapshot.capacity === 4 || PAIR.has(colour)),
        lit: match?.status === "finished" ? match.winner === colour : playing ? match.current === colour : true,
        turn: playing && match.current === colour,
        awayMs: member?.away_ms ?? null,
      });
    }
    tickAway();

    const nearBottom = messageList.scrollHeight - messageList.scrollTop - messageList.clientHeight < 40;
    messageList.replaceChildren(...snapshot.messages.map((m) => renderMessage(m, me)));
    if (nearBottom) messageList.scrollTop = messageList.scrollHeight;

    // Nothing is movable while the match is paused or this browser is offline.
    const frozen = !live || pausedFor(snapshot).length > 0;
    board.update(match && frozen ? { ...match, legal_moves: [] } : match, myColour);
    boardWrap.dataset.turn = match?.status === "playing" ? match.current : "";
    renderMatchMoment(snapshot, match, myColour);
  }

  function renderMatchMoment(snapshot: RoomSnapshot, match: MatchState | null, myColour: Colour | null): void {
    const key = match ? `${match.match_id}:${match.step}` : null;
    if (key === shownStep) return;
    const previousKey = shownStep;
    shownStep = key;
    if (!match) {
      for (const seat of seatViews.values()) seat.die.show(1);
      banner.hidden = true;
      return;
    }

    const fresh = previousKey !== null && previousKey.startsWith(`${match.match_id}:`);
    if (!fresh) for (const seat of seatViews.values()) seat.die.show(1);
    // Everyone watches the roller's own die tumble, even when the turn passes straight on.
    const rolled = match.events.find((e) => e.kind === "rolled");
    if (rolled && rolled.kind === "rolled") {
      const seat = seatViews.get(rolled.colour)!;
      seat.rolled(rolled.value, fresh);
      if (fresh && match.events.some((e) => e.kind === "sixes_forfeited")) seat.flash("Three sixes, turn lost");
      else if (fresh && match.events.some((e) => e.kind === "no_legal_move")) seat.flash("No move");
    }

    banner.hidden = match.status === "playing";
    banner.replaceChildren();
    if (match.status === "finished" && match.winner) {
      banner.dataset.colour = match.winner;
      const winnerName = match.winner === myColour ? "You win" : `${nameFor(snapshot, match.winner)} wins`;
      banner.append(
        el("p", { className: "banner-title", textContent: winnerName }),
        el("p", { textContent: "Ready up to play again." }),
      );
      if (fresh && !reducedMotion()) celebrate(boardWrap, match.winner);
    } else if (match.status === "ended") {
      banner.dataset.colour = "";
      banner.append(
        el("p", { className: "banner-title", textContent: "Match ended" }),
        el("p", { textContent: match.ended_reason ?? "" }),
      );
    }
  }

  function renderControls(snapshot: RoomSnapshot, me: string | null, live: boolean): void {
    const match = snapshot.match;
    const playing = match?.status === "playing";
    const myColour = seatOf(match, me);

    lobbyPanel.hidden = playing;
    const canRoll =
      playing && match.current === myColour && match.phase === "awaiting_roll" && pausedFor(snapshot).length === 0;
    if (myColour) seatViews.get(myColour)!.actions.append(rollButton);
    rollButton.hidden = !canRoll;
    rollButton.disabled = !live || !canRoll;
    rollButton.dataset.colour = myColour ?? "";
    for (const [colour, seat] of seatViews) seat.element.classList.toggle("can-roll", canRoll && colour === myColour);
    if (!playing) {
      const lobbyState = lobbyStatus(snapshot, me);
      lobbyHint.textContent = lobbyState.hint;
      readyButton.hidden = lobbyState.isHost;
      readyButton.dataset.ready = String(lobbyState.isReady);
      readyButton.textContent = lobbyState.isReady ? "Not ready" : "I'm ready";
      readyButton.classList.toggle("btn-marigold", !lobbyState.isReady);
      readyButton.classList.toggle("btn-light", lobbyState.isReady);
      readyButton.disabled = !live;
      startButton.hidden = !lobbyState.isHost;
      startButton.disabled = !live || !lobbyState.canStart;
      startButton.textContent = match ? "Play again" : "Start match";
    }
  }

  function tickAway(): void {
    const elapsed = performance.now() - snapshotAt;
    for (const seat of seatViews.values()) seat.tick(elapsed);
    const waiting = renderedRoom ? pausedFor(renderedRoom) : [];
    pauseBanner.hidden = waiting.length === 0;
    if (waiting.length === 0) return;
    const names = waiting.map((m) => m.nickname).join(" and ");
    const seconds = Math.max(...waiting.map((m) => secondsLeft(m.away_ms!, elapsed)));
    pauseText.textContent = `Waiting for ${names} to reconnect · ${seconds}s`;
  }
}

interface SeatState {
  name: string | null;
  tags: string;
  note: string;
  empty: boolean;
  lit: boolean;
  turn: boolean;
  awayMs: number | null;
}

const PAIR = new Set<Colour>(["red", "yellow"]);

/** One player's corner: their die, name, and what they are doing. */
class SeatView {
  readonly element: HTMLDivElement;
  readonly die: DieView;
  readonly actions = el("div", { className: "seat-actions" });
  private readonly name = el("span", { className: "member-name" });
  private readonly tags = el("span", { className: "tag" });
  private readonly note = el("span", { className: "seat-note" });
  private flashTimer = 0;
  private rollTimer = 0;
  private awayMs: number | null = null;
  private plainNote = "";

  constructor(colour: Colour, reducedMotion: () => boolean) {
    this.die = new DieView(reducedMotion);
    this.die.colour(colour);
    this.element = el(
      "div",
      { className: "seat" },
      this.die.element,
      el("div", { className: "seat-info" }, this.name, this.tags, this.note),
      this.actions,
    );
    this.element.dataset.colour = colour;
  }

  update(state: SeatState): void {
    this.element.hidden = state.name === null && !state.empty;
    this.element.classList.toggle("is-empty", state.name === null);
    this.element.classList.toggle("is-lit", state.lit && state.name !== null);
    this.element.classList.toggle("is-turn", state.turn);
    this.name.textContent = state.name ?? "Open seat";
    this.tags.textContent = state.tags;
    this.plainNote = state.note;
    this.awayMs = state.awayMs;
    this.element.classList.toggle("is-away", state.awayMs !== null);
    if (!this.flashTimer && state.awayMs === null) this.note.textContent = state.note;
  }

  /** Counts down an away player's reconnect window. */
  tick(elapsedMs: number): void {
    if (this.awayMs === null) return;
    this.note.textContent = `Reconnecting… ${secondsLeft(this.awayMs, elapsedMs)}s`;
  }

  /** Tumbles the die; the seat stays lit while it lands, even if the turn has passed on. */
  rolled(value: number, animate: boolean): void {
    if (!animate) return this.die.show(value);
    this.flash(null);
    window.clearTimeout(this.rollTimer);
    this.element.classList.add("is-rolling");
    void this.die.tumble(value);
    this.rollTimer = window.setTimeout(() => this.element.classList.remove("is-rolling"), 1100);
  }

  /** Briefly says something the board can't show, such as a lost turn. */
  flash(text: string | null): void {
    window.clearTimeout(this.flashTimer);
    this.flashTimer = 0;
    this.note.textContent = this.plainNote;
    this.note.classList.remove("is-flash");
    if (text === null) return;
    this.note.textContent = text;
    this.note.classList.add("is-flash");
    this.flashTimer = window.setTimeout(() => this.flash(null), 1800);
  }
}

function nameFor(snapshot: RoomSnapshot, colour: Colour): string {
  const seat = snapshot.match?.seats.find((s) => s.colour === colour);
  return snapshot.members.find((m) => m.session_id === seat?.session_id)?.nickname ?? COLOUR_NAMES[colour];
}

function renderMessage(message: ChatMessage, me: string | null): HTMLLIElement {
  const time = new Date(message.sent_at);
  return el(
    "li",
    { className: message.sender_session_id === me ? "mine" : "" },
    el("span", { className: "sender", textContent: message.sender_nickname }),
    el("span", { className: "text", textContent: message.text }),
    el("time", {
      dateTime: message.sent_at,
      textContent: time.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    }),
  );
}

// A short burst of paper for a win. Rare, so it gets the delight budget.
function celebrate(host: HTMLElement, colour: Colour): void {
  const layer = el("div", { className: "confetti" });
  layer.setAttribute("aria-hidden", "true");
  const palette = [colour, colour, "marigold", "ivory"];
  for (let i = 0; i < 46; i++) {
    const piece = el("span");
    piece.dataset.colour = palette[i % palette.length]!;
    const angle = Math.random() * Math.PI * 2;
    const distance = 30 + Math.random() * 45;
    piece.style.setProperty("left", `${50 + (Math.random() - 0.5) * 8}%`);
    piece.style.setProperty("top", `${46 + (Math.random() - 0.5) * 8}%`);
    layer.append(piece);
    piece.animate(
      [
        { transform: "translate(0, 0) rotate(0deg)", opacity: 1 },
        {
          transform: `translate(${Math.cos(angle) * distance}vmin, ${Math.sin(angle) * distance + 25}vmin) rotate(${Math.random() * 720 - 360}deg)`,
          opacity: 0,
        },
      ],
      { duration: 1400 + Math.random() * 700, easing: "cubic-bezier(0.23, 1, 0.32, 1)", fill: "forwards" },
    );
  }
  host.append(layer);
  window.setTimeout(() => layer.remove(), 2300);
}

export function loadNickname(): string {
  try {
    return localStorage.getItem("shugal.nickname") ?? "";
  } catch {
    return "";
  }
}

function saveNickname(nickname: string): void {
  try {
    localStorage.setItem("shugal.nickname", nickname);
  } catch {
    // Storage is only a convenience.
  }
}
