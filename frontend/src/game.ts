// Plain-language descriptions of lobby and match state. Pure, so they are easy to test.

import type { Colour, MatchState, Member, RoomSnapshot } from "./protocol";

export const COLOUR_NAMES: Record<Colour, string> = {
  red: "Red",
  green: "Green",
  yellow: "Yellow",
  blue: "Blue",
};

export function seatOf(match: MatchState | null, sessionId: string | null): Colour | null {
  return match?.seats.find((s) => s.session_id === sessionId)?.colour ?? null;
}

export function nameOf(room: RoomSnapshot, colour: Colour): string {
  const seat = room.match?.seats.find((s) => s.colour === colour);
  return room.members.find((m) => m.session_id === seat?.session_id)?.nickname ?? COLOUR_NAMES[colour];
}

/** Who sits at each colour: the match's seats, or the seats the next match will use. */
export function seatPlan(room: RoomSnapshot): Map<Colour, Member> {
  const plan = new Map<Colour, Member>();
  const byId = new Map(room.members.map((m) => [m.session_id, m]));
  if (room.match) {
    for (const seat of room.match.seats) {
      const member = byId.get(seat.session_id);
      if (member) plan.set(seat.colour, member);
    }
    if (room.match.status === "playing") return plan;
    plan.clear(); // Between matches, show where the next match will seat everyone.
  }
  // Matches the server: two players take red and yellow, four take every colour in join order.
  const colours: readonly Colour[] = room.members.length === 2 ? ["red", "yellow"] : ["red", "green", "yellow", "blue"];
  room.members.slice(0, colours.length).forEach((m, i) => plan.set(colours[i]!, m));
  return plan;
}

/** Seated players a playing match is waiting for. */
export function pausedFor(room: RoomSnapshot): Member[] {
  const match = room.match;
  if (match?.status !== "playing") return [];
  const seated = new Set(match.seats.map((s) => s.session_id));
  return room.members.filter((m) => m.away_ms !== null && seated.has(m.session_id));
}

/** Whole seconds left to reconnect, counting down from when the snapshot arrived. */
export function secondsLeft(awayMs: number, elapsedMs: number): number {
  return Math.max(0, Math.ceil((awayMs - elapsedMs) / 1000));
}

/** A short line under a seated player's name. */
export function seatNote(room: RoomSnapshot, colour: Colour, me: Colour | null): string {
  const match = room.match;
  if (!match) return "";
  if (match.status === "finished") return match.winner === colour ? "Winner!" : "";
  if (match.status !== "playing" || match.current !== colour) return "";
  if (colour === me) {
    if (match.phase === "awaiting_roll") return "Your turn";
    return "Pick a glowing token";
  }
  return match.phase === "awaiting_roll" ? "Rolling…" : "Moving…";
}

export interface LobbyStatus {
  isHost: boolean;
  isReady: boolean;
  canStart: boolean;
  hint: string;
}

export function lobbyStatus(room: RoomSnapshot, sessionId: string | null): LobbyStatus {
  const isHost = room.host === sessionId;
  const isReady = sessionId !== null && room.ready.includes(sessionId);
  const count = room.members.length;
  const waitingFor = room.members.filter((m) => m.session_id !== room.host && !room.ready.includes(m.session_id));
  let hint: string;
  let canStart = false;
  const away = room.members.filter((m) => m.away_ms !== null);
  if (away.length > 0) hint = `Waiting for ${away.map((m) => m.nickname).join(" and ")} to reconnect.`;
  else if (count < 2) hint = "Share the room code. You need at least one friend.";
  else if (count === 3) hint = "Ludo needs two or four players. Wait for one more, or ask someone to leave.";
  else if (waitingFor.length > 0) hint = `Waiting for ${waitingFor.map((m) => m.nickname).join(" and ")} to get ready.`;
  else {
    canStart = true;
    hint = isHost ? "Everyone is ready." : "Everyone is ready. The host starts the match.";
  }
  return { isHost, isReady, canStart: canStart && isHost, hint };
}
