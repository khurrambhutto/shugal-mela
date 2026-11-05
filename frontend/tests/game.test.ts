import { describe, expect, it } from "vitest";

import fixtures from "../../tests/fixtures/protocol/v1.json";
import { hopPath, tokenPoint, TRACK } from "../src/board";
import { lobbyStatus, pausedFor, seatNote, seatOf, seatPlan, secondsLeft } from "../src/game";
import type { MatchState, RoomSnapshot } from "../src/protocol";

const base = fixtures.server_messages["room.snapshot.match"].body as unknown as RoomSnapshot;
const match = base.match!;

function room(overrides: Partial<MatchState> = {}, extra: Partial<RoomSnapshot> = {}): RoomSnapshot {
  return { ...base, ...extra, match: { ...match, ...overrides } };
}

describe("board geometry", () => {
  it("has 52 distinct track squares", () => {
    expect(new Set(TRACK.map(([c, r]) => `${c},${r}`)).size).toBe(52);
  });

  it("places each colour's start beside its yard", () => {
    expect(tokenPoint("red", 0, 0)).toEqual({ x: 1.5, y: 6.5 });
    expect(tokenPoint("green", 0, 0)).toEqual({ x: 8.5, y: 1.5 });
    expect(tokenPoint("yellow", 0, 0)).toEqual({ x: 13.5, y: 8.5 });
    expect(tokenPoint("blue", 0, 0)).toEqual({ x: 6.5, y: 13.5 });
  });

  it("turns into the home column after the last track square", () => {
    expect(tokenPoint("red", 50, 0)).toEqual({ x: 0.5, y: 7.5 });
    expect(tokenPoint("red", 51, 0)).toEqual({ x: 1.5, y: 7.5 });
    expect(tokenPoint("yellow", 55, 0)).toEqual({ x: 9.5, y: 7.5 });
  });

  it("hops through every square of a move", () => {
    expect(hopPath("red", 0, 3, 0)).toHaveLength(3);
    expect(hopPath("red", -1, 0, 2)).toEqual([tokenPoint("red", 0, 2)]);
  });
});

describe("seats", () => {
  it("finds a player's seat", () => {
    expect(seatOf(match, "session-b")).toBe("yellow");
    expect(seatOf(match, "someone")).toBeNull();
  });

  it("puts each player at their match colour", () => {
    const plan = seatPlan(room());
    expect([...plan].map(([c, m]) => [c, m.nickname])).toEqual([
      ["red", "Ali"],
      ["yellow", "Sara"],
    ]);
  });

  it("shows where the next match will seat everyone", () => {
    const four = ["Ali", "Sara", "Omar", "Zara"].map((nickname, i) => ({ session_id: `s${i}`, nickname, away_ms: null }));
    const plan = seatPlan({ ...base, match: null, members: four });
    expect([...plan.keys()]).toEqual(["red", "green", "yellow", "blue"]);
    expect([...seatPlan({ ...base, match: null }).keys()]).toEqual(["red", "yellow"]);
  });

  it("notes whose turn it is and what they are doing", () => {
    expect(seatNote(room(), "red", "red")).toBe("Your turn");
    expect(seatNote(room(), "red", "yellow")).toBe("Rolling…");
    expect(seatNote(room(), "yellow", "red")).toBe("");
    const moving = room({ phase: "awaiting_move", roll: 1, legal_moves: [1] });
    expect(seatNote(moving, "red", "red")).toBe("Pick a glowing token");
    expect(seatNote(moving, "red", "yellow")).toBe("Moving…");
    expect(seatNote(room({ status: "finished", winner: "yellow" }), "yellow", "red")).toBe("Winner!");
  });
});

describe("reconnecting", () => {
  const away = (ms: number | null) => base.members.map((m, i) => ({ ...m, away_ms: i === 1 ? ms : null }));

  it("pauses a match only for seated players who are away", () => {
    expect(pausedFor(room())).toEqual([]);
    expect(pausedFor(room({}, { members: away(41_000) })).map((m) => m.nickname)).toEqual(["Sara"]);
    expect(pausedFor(room({ status: "ended" }, { members: away(41_000) }))).toEqual([]);
  });

  it("counts down from when the snapshot arrived", () => {
    expect(secondsLeft(41_000, 0)).toBe(41);
    expect(secondsLeft(41_000, 1_500)).toBe(40);
    expect(secondsLeft(500, 2_000)).toBe(0);
  });

  it("holds the lobby while someone reconnects", () => {
    const lobby = { ...base, match: null, ready: ["session-b"], members: away(30_000) };
    expect(lobbyStatus(lobby, "session-a")).toMatchObject({ canStart: false, hint: "Waiting for Sara to reconnect." });
  });
});

describe("lobby", () => {
  const lobby = (extra: Partial<RoomSnapshot>) => ({ ...base, match: null, ...extra });

  it("waits for players to get ready", () => {
    const status = lobbyStatus(lobby({ ready: [] }), "session-a");
    expect(status).toMatchObject({ isHost: true, canStart: false, hint: "Waiting for Sara to get ready." });
  });

  it("lets only the host start once everyone is ready", () => {
    expect(lobbyStatus(lobby({ ready: ["session-b"] }), "session-a").canStart).toBe(true);
    expect(lobbyStatus(lobby({ ready: ["session-b"] }), "session-b")).toMatchObject({ canStart: false, isReady: true });
  });

  it("explains player counts that cannot start", () => {
    const solo = lobby({ members: [base.members[0]!], ready: [] });
    expect(lobbyStatus(solo, "session-a").hint).toContain("at least one friend");
    const three = lobby({ members: [...base.members, { session_id: "c", nickname: "Omar", away_ms: null }], ready: [] });
    expect(lobbyStatus(three, "session-a").hint).toContain("two or four players");
  });
});
