import { Connection, SessionError, UncertainError, startSession } from "./connection";
import type { CommandBodies, CommandType, ResultBody } from "./protocol";
import {
  applyRoomResult,
  applySnapshot,
  beginRoomCommand,
  canSubmit,
  connecting,
  connectionLost,
  describeError,
  initialState,
  sessionReady,
  withNotice,
  type AppState,
} from "./state";
import { createUi, loadNickname } from "./ui";
import "./styles.css";

let state: AppState = initialState;
let nickname = "";

// Automatic reconnects back off from 0.5 s to 8 s, and give up after two minutes,
// well past the server's 60-second seat window.
const RETRY_FIRST_MS = 500;
const RETRY_MAX_MS = 8000;
const RETRY_GIVE_UP_MS = 120_000;
let retryTimer = 0;
let retryAttempt = 0;
let retryingSince: number | null = null;

// Marks this tab as seated, so a refresh resumes without asking for the nickname again.
const SEATED_KEY = "shugal.seated";

const root = document.querySelector<HTMLElement>("#app");
if (!root) throw new Error("missing #app element");

const render = createUi(root, {
  start(name) {
    nickname = name;
    void connect();
  },
  reconnect() {
    resetRetry();
    void connect();
  },
  create(capacity) {
    if (!canSubmit(state)) return;
    update(beginRoomCommand(state, { kind: "create" }));
    void roomCommand("create", connection.command("room.create", { capacity }));
  },
  join(code) {
    if (!canSubmit(state)) return;
    update(beginRoomCommand(state, { kind: "join", code }));
    void roomCommand("join", connection.command("room.join", { code }));
  },
  leave() {
    if (!canSubmit(state)) return;
    void roomCommand("leave", connection.command("room.leave", {}));
  },
  ready(ready) {
    void gameCommand("match.ready", { ready });
  },
  startMatch() {
    void gameCommand("match.start", {});
  },
  async roll() {
    const match = state.room?.match;
    if (match) await gameCommand("match.roll", { match_id: match.match_id, step: match.step });
  },
  async move(token) {
    const match = state.room?.match;
    return match ? gameCommand("match.move", { match_id: match.match_id, step: match.step, token }) : false;
  },
  async send(text) {
    if (!canSubmit(state)) return false;
    try {
      const result = await connection.command("chat.send", { text });
      if (!result.ok) update(withNotice(state, describeError(result.error)));
      return result.ok;
    } catch (error) {
      handleUncertain(error);
      return false;
    }
  },
});

const connection = new Connection({
  onReady(session) {
    resetRetry();
    update(sessionReady(state, session));
  },
  onSnapshot(snapshot) {
    update(applySnapshot(state, snapshot));
  },
  onClosed(reason, retry) {
    if (retry && state.session !== null) retryLater();
    else update(connectionLost(state, reason));
  },
  onUncorrelatedError(result) {
    if (!result.ok) update(withNotice(state, describeError(result.error)));
  },
});

function update(next: AppState): void {
  state = next;
  rememberSeat();
  render(state);
}

function rememberSeat(): void {
  try {
    if (state.room !== null) sessionStorage.setItem(SEATED_KEY, "1");
    else if (state.status === "connected" && state.pendingRoom === null) sessionStorage.removeItem(SEATED_KEY);
  } catch {
    // Without storage, a refresh shows the welcome form instead.
  }
}

function wasSeated(): boolean {
  try {
    return sessionStorage.getItem(SEATED_KEY) === "1";
  } catch {
    return false;
  }
}

function retryLater(): void {
  window.clearTimeout(retryTimer);
  retryingSince ??= Date.now();
  if (Date.now() - retryingSince > RETRY_GIVE_UP_MS) {
    resetRetry();
    update(connectionLost(state, "Could not reconnect. Check your connection, then press Reconnect."));
    return;
  }
  update(connectionLost(state, "Connection lost. Reconnecting…", true));
  const delay = Math.min(RETRY_MAX_MS, RETRY_FIRST_MS * 2 ** retryAttempt);
  retryAttempt++;
  // Jitter keeps several players from retrying in lockstep after the host's network blips.
  retryTimer = window.setTimeout(() => void connect(), delay * (0.75 + Math.random() * 0.5));
}

function resetRetry(): void {
  window.clearTimeout(retryTimer);
  retryAttempt = 0;
  retryingSince = null;
}

async function connect(): Promise<void> {
  if (!nickname) return;
  update(connecting(state));
  try {
    // Restores the cookie's session when it is still valid, or creates a new one.
    await startSession(nickname);
  } catch (error) {
    if (error instanceof SessionError && error.retry && state.session !== null) {
      retryLater();
      return;
    }
    const message = error instanceof SessionError ? error.message : "Could not start a session.";
    update(connectionLost(state, message));
    return;
  }
  connection.open();
}

async function roomCommand(kind: "create" | "join" | "leave", request: Promise<ResultBody>): Promise<void> {
  try {
    update(applyRoomResult(state, kind, await request));
  } catch (error) {
    handleUncertain(error);
  }
}

// Game results arrive as snapshots; only failures need a message here.
// Resolves to whether the server accepted the command.
async function gameCommand<T extends CommandType>(type: T, body: CommandBodies[T]): Promise<boolean> {
  if (!canSubmit(state)) return false;
  try {
    const result = await connection.command(type, body);
    if (result.ok) {
      if (state.notice) update(withNotice(state, null));
    } else if (result.error.code === "STALE_STATE") {
      // A newer snapshot is already on its way or applied; the board will show it.
    } else {
      update(withNotice(state, describeError(result.error)));
    }
    if (!result.ok) render(state); // Re-enable controls disabled while the command was in flight.
    return result.ok;
  } catch (error) {
    handleUncertain(error);
    return false;
  }
}

function handleUncertain(error: unknown): void {
  if (!(error instanceof UncertainError)) throw error;
  // The close handler already explains the disconnect; keep its message.
}

// Retry at once when the device says its network is back.
window.addEventListener("online", () => {
  if (state.status !== "reconnecting") return;
  window.clearTimeout(retryTimer);
  void connect();
});

render(state);
// A refresh while seated goes straight back to the seat.
const savedNickname = loadNickname();
if (savedNickname && wasSeated()) {
  nickname = savedNickname;
  void connect();
}
