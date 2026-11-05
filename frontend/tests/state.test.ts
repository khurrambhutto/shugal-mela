import { describe, expect, it } from "vitest";

import fixtures from "../../tests/fixtures/protocol/v1.json";
import { websocketUrl } from "../src/connection";
import { parseServerMessage, type ResultBody, type RoomSnapshot } from "../src/protocol";
import {
  applyRoomResult,
  applySnapshot,
  beginRoomCommand,
  canSubmit,
  connectionLost,
  initialState,
  sessionReady,
  type AppState,
} from "../src/state";

const me = { session_id: "session-a", nickname: "Ali" };

function snapshot(code: string, revision: number, texts: string[] = []): RoomSnapshot {
  return {
    code,
    capacity: 2,
    revision,
    members: [me],
    messages: texts.map((text, i) => ({
      message_id: `m${i}`,
      sender_session_id: me.session_id,
      sender_nickname: me.nickname,
      text,
      sent_at: "2026-11-05T12:00:00.000Z",
    })),
  };
}

const ok = (room_code: string | null, revision: number | null): ResultBody => ({
  command_id: "c",
  ok: true,
  room_code,
  revision,
});

const connected: AppState = sessionReady(initialState, me);

function inRoom(code = "ABCD23", revision = 2): AppState {
  return applySnapshot(beginRoomCommand(connected, { kind: "join", code }), snapshot(code, revision));
}

describe("protocol fixtures", () => {
  it("parses every server message fixture", () => {
    for (const [name, message] of Object.entries(fixtures.server_messages)) {
      expect(parseServerMessage(JSON.stringify(message)), name).not.toBeNull();
    }
  });

  it("rejects unknown or malformed messages", () => {
    expect(parseServerMessage("not json")).toBeNull();
    expect(parseServerMessage(JSON.stringify({ version: 2, type: "room.snapshot", body: {} }))).toBeNull();
    expect(parseServerMessage(JSON.stringify({ version: 1, type: "room.explode", body: {} }))).toBeNull();
  });
});

describe("snapshots", () => {
  it("ignores snapshots when no room is current or pending", () => {
    expect(applySnapshot(connected, snapshot("ABCD23", 1)).room).toBeNull();
  });

  it("accepts the first snapshot while a create is pending", () => {
    const state = applySnapshot(beginRoomCommand(connected, { kind: "create" }), snapshot("NEW234", 1));
    expect(state.room?.code).toBe("NEW234");
    expect(state.pendingRoom).toBeNull();
  });

  it("accepts a pending join only for the requested code, case-insensitively", () => {
    const pending = beginRoomCommand(connected, { kind: "join", code: " abcd23 " });
    expect(applySnapshot(pending, snapshot("OTHER2", 5)).room).toBeNull();
    expect(applySnapshot(pending, snapshot("ABCD23", 2)).room?.code).toBe("ABCD23");
  });

  it("ignores reordered older revisions and other rooms", () => {
    const state = applySnapshot(inRoom("ABCD23", 2), snapshot("ABCD23", 4, ["new"]));
    expect(applySnapshot(state, snapshot("ABCD23", 3, ["old"])).room?.revision).toBe(4);
    expect(applySnapshot(state, snapshot("ZZZZ22", 99)).room?.code).toBe("ABCD23");
  });

  it("replaces chat history instead of appending it", () => {
    let state = applySnapshot(inRoom(), snapshot("ABCD23", 3, ["a", "b"]));
    state = applySnapshot(state, snapshot("ABCD23", 4, ["b", "c"]));
    expect(state.room?.messages.map((m) => m.text)).toEqual(["b", "c"]);
  });
});

describe("command results", () => {
  it("waits for the snapshot when a create result arrives first", () => {
    let state = applyRoomResult(beginRoomCommand(connected, { kind: "create" }), "create", ok("NEW234", 1));
    expect(state.pendingRoom).toEqual({ kind: "join", code: "NEW234" });
    expect(applySnapshot(state, snapshot("OTHER2", 1)).room).toBeNull();
    state = applySnapshot(state, snapshot("NEW234", 1));
    expect(state.room?.code).toBe("NEW234");
  });

  it("clears the pending room after a join result that follows its snapshot", () => {
    const state = applyRoomResult(inRoom(), "join", ok("ABCD23", 2));
    expect(state.pendingRoom).toBeNull();
    expect(state.room?.code).toBe("ABCD23");
  });

  it("clears the room after a successful leave and ignores old snapshots", () => {
    const left = applyRoomResult(inRoom(), "leave", ok(null, null));
    expect(left.room).toBeNull();
    expect(applySnapshot(left, snapshot("ABCD23", 9)).room).toBeNull();
  });

  it("shows an error and clears the pending join on failure", () => {
    const failed = applyRoomResult(beginRoomCommand(connected, { kind: "join", code: "FULL22" }), "join", {
      command_id: "c",
      ok: false,
      error: { code: "ROOM_FULL", message: "This room has no available seats." },
    });
    expect(failed.pendingRoom).toBeNull();
    expect(failed.notice).toBe("That room is full.");
  });

  it("describes rate limits with the retry delay", () => {
    const state = applyRoomResult(inRoom(), "join", {
      command_id: "c",
      ok: false,
      error: { code: "RATE_LIMITED", message: "", retry_after_ms: 2500 },
    });
    expect(state.notice).toContain("3s");
  });
});

describe("offline behavior", () => {
  it("blocks submission and remembers the room for rejoining", () => {
    const offline = connectionLost(inRoom("ABCD23"), "Disconnected");
    expect(canSubmit(offline)).toBe(false);
    expect(offline.lastRoomCode).toBe("ABCD23");
    expect(offline.notice).toBe("Disconnected");
    expect(applySnapshot(offline, snapshot("ABCD23", 10)).room?.revision).toBe(2);
  });

  it("starts outside any room after reconnecting", () => {
    const back = sessionReady(connectionLost(inRoom(), "x"), me);
    expect(back.room).toBeNull();
    expect(canSubmit(back)).toBe(true);
  });
});

describe("websocket URL", () => {
  it("uses the page origin and wss for https", () => {
    expect(websocketUrl({ protocol: "https:", host: "abc.trycloudflare.com" })).toBe("wss://abc.trycloudflare.com/ws");
    expect(websocketUrl({ protocol: "http:", host: "localhost:8000" })).toBe("ws://localhost:8000/ws");
  });
});
