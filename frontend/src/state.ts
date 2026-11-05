// Client state transitions. Pure functions so they can be tested without a browser.

import type { CommandError, ResultBody, RoomSnapshot, SessionInfo } from "./protocol";

export type ConnectionStatus = "idle" | "connecting" | "connected" | "offline";

// A create or join that has been sent but whose room is not yet established.
export type PendingRoom = { kind: "create" } | { kind: "join"; code: string } | null;

export interface AppState {
  status: ConnectionStatus;
  session: SessionInfo | null;
  room: RoomSnapshot | null;
  pendingRoom: PendingRoom;
  // The room this client was in when the connection dropped, offered for rejoining.
  lastRoomCode: string | null;
  notice: string | null;
}

export const initialState: AppState = {
  status: "idle",
  session: null,
  room: null,
  pendingRoom: null,
  lastRoomCode: null,
  notice: null,
};

export function canSubmit(state: AppState): boolean {
  return state.status === "connected" && state.session !== null;
}

export function connecting(state: AppState): AppState {
  return { ...state, status: "connecting", notice: null };
}

export function sessionReady(state: AppState, session: SessionInfo): AppState {
  // A new connection starts outside any room: the server released the old seat.
  return { ...state, status: "connected", session, room: null, pendingRoom: null };
}

export function connectionLost(state: AppState, notice: string): AppState {
  return {
    ...state,
    status: "offline",
    pendingRoom: null,
    lastRoomCode: state.room?.code ?? state.lastRoomCode,
    notice,
  };
}

// Register the expected room before sending, so an early snapshot can be accepted.
export function beginRoomCommand(state: AppState, pending: NonNullable<PendingRoom>): AppState {
  const normalized =
    pending.kind === "join" ? { kind: "join" as const, code: pending.code.trim().toUpperCase() } : pending;
  return { ...state, pendingRoom: normalized, notice: null };
}

export function applySnapshot(state: AppState, snapshot: RoomSnapshot): AppState {
  if (state.status !== "connected") return state;

  if (state.room !== null) {
    // Revisions only compare within one room. Ignore other rooms and older revisions.
    if (snapshot.code !== state.room.code || snapshot.revision < state.room.revision) return state;
    return { ...state, room: snapshot };
  }

  const pending = state.pendingRoom;
  const expected =
    (pending?.kind === "create") || (pending?.kind === "join" && pending.code === snapshot.code);
  if (!expected) return state;
  return { ...state, room: snapshot, pendingRoom: null, lastRoomCode: null };
}

export function applyRoomResult(
  state: AppState,
  kind: "create" | "join" | "leave",
  result: ResultBody,
): AppState {
  if (!result.ok) {
    return { ...state, pendingRoom: kind === "leave" ? state.pendingRoom : null, notice: describeError(result.error) };
  }
  if (kind === "leave") {
    return { ...state, room: null, pendingRoom: null, lastRoomCode: null, notice: null };
  }
  const code = result.room_code;
  if (code === null) return state;
  if (state.room?.code === code) return { ...state, pendingRoom: null };
  // The result arrived before its snapshot: wait for a snapshot of exactly this room.
  return { ...state, pendingRoom: { kind: "join", code } };
}

export function withNotice(state: AppState, notice: string | null): AppState {
  return { ...state, notice };
}

export function describeError(error: CommandError): string {
  switch (error.code) {
    case "ROOM_FULL":
      return "That room is full.";
    case "ROOM_NOT_FOUND":
      return "No room has that code. Check it and try again.";
    case "ALREADY_IN_ROOM":
      return "Leave your current room first.";
    case "NOT_IN_ROOM":
      return "You are not in a room.";
    case "RATE_LIMITED": {
      const seconds = Math.ceil((error.retry_after_ms ?? 1000) / 1000);
      return `Slow down — try again in ${seconds}s.`;
    }
    case "SERVER_BUSY":
      return "The server is at capacity. Try again later.";
    default:
      return error.message;
  }
}
