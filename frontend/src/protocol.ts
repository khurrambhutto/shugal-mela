// Protocol v1 types. Mirrors backend/app/protocol.py and contracts/protocol.md.

export const PROTOCOL_VERSION = 1;

export type ErrorCode =
  | "VALIDATION_ERROR"
  | "UNSUPPORTED_VERSION"
  | "ROOM_NOT_FOUND"
  | "ROOM_FULL"
  | "ALREADY_IN_ROOM"
  | "NOT_IN_ROOM"
  | "RATE_LIMITED"
  | "COMMAND_ID_REUSED"
  | "SERVER_BUSY";

export interface CommandBodies {
  "room.create": { capacity: 2 | 4 };
  "room.join": { code: string };
  "room.leave": Record<string, never>;
  "room.sync": Record<string, never>;
  "chat.send": { text: string };
}

export type CommandType = keyof CommandBodies;

export interface Command<T extends CommandType = CommandType> {
  version: typeof PROTOCOL_VERSION;
  command_id: string;
  type: T;
  body: CommandBodies[T];
}

export interface SessionInfo {
  session_id: string;
  nickname: string;
}

export interface Member {
  session_id: string;
  nickname: string;
}

export interface ChatMessage {
  message_id: string;
  sender_session_id: string;
  sender_nickname: string;
  text: string;
  sent_at: string;
}

export interface RoomSnapshot {
  code: string;
  capacity: number;
  revision: number;
  members: Member[];
  messages: ChatMessage[];
}

export interface CommandError {
  code: ErrorCode;
  message: string;
  retry_after_ms?: number;
}

export type ResultBody =
  | {
      command_id: string | null;
      ok: true;
      room_code: string | null;
      revision: number | null;
      message_id?: string;
    }
  | { command_id: string | null; ok: false; error: CommandError };

export type ServerMessage =
  | { version: 1; type: "session.ready"; body: SessionInfo }
  | { version: 1; type: "command.result"; body: ResultBody }
  | { version: 1; type: "room.snapshot"; body: RoomSnapshot };

export function parseServerMessage(raw: string): ServerMessage | null {
  let data: unknown;
  try {
    data = JSON.parse(raw);
  } catch {
    return null;
  }
  if (typeof data !== "object" || data === null) return null;
  const { version, type, body } = data as Record<string, unknown>;
  if (version !== PROTOCOL_VERSION || typeof body !== "object" || body === null) return null;
  if (type === "session.ready" || type === "command.result" || type === "room.snapshot") {
    return data as ServerMessage;
  }
  return null;
}

export function newCommandId(): string {
  if (typeof crypto.randomUUID === "function") return crypto.randomUUID();
  // randomUUID requires a secure context; fall back to a v4 UUID from random bytes.
  const b = crypto.getRandomValues(new Uint8Array(16));
  b[6] = (b[6]! & 0x0f) | 0x40;
  b[8] = (b[8]! & 0x3f) | 0x80;
  const hex = Array.from(b, (x) => x.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}
