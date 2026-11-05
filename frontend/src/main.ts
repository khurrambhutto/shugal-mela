import { Connection, SessionError, UncertainError, startSession } from "./connection";
import type { ResultBody } from "./protocol";
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
import { createUi } from "./ui";

let state: AppState = initialState;
let nickname = "";

const root = document.querySelector<HTMLElement>("#app");
if (!root) throw new Error("missing #app element");

const render = createUi(root, {
  start(name) {
    nickname = name;
    void connect();
  },
  reconnect() {
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
    update(sessionReady(state, session));
  },
  onSnapshot(snapshot) {
    update(applySnapshot(state, snapshot));
  },
  onClosed(reason) {
    update(connectionLost(state, reason));
  },
  onUncorrelatedError(result) {
    if (!result.ok) update(withNotice(state, describeError(result.error)));
  },
});

function update(next: AppState): void {
  state = next;
  render(state);
}

async function connect(): Promise<void> {
  if (!nickname) return;
  update(connecting(state));
  try {
    // Restores the cookie's session when it is still valid, or creates a new one.
    await startSession(nickname);
  } catch (error) {
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

function handleUncertain(error: unknown): void {
  if (!(error instanceof UncertainError)) throw error;
  // The close handler already explains the disconnect; keep its message.
}

render(state);
