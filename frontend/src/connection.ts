// Session bootstrap and the live socket, with command/result correlation.

import {
  PROTOCOL_VERSION,
  newCommandId,
  parseServerMessage,
  type CommandBodies,
  type CommandType,
  type ResultBody,
  type RoomSnapshot,
  type SessionInfo,
} from "./protocol";

const CLOSE_ALREADY_CONNECTED = 4409;

// Thrown for commands whose outcome is unknown because the connection closed.
export class UncertainError extends Error {}

export interface ConnectionEvents {
  onReady(session: SessionInfo): void;
  onSnapshot(snapshot: RoomSnapshot): void;
  onClosed(reason: string): void;
  onUncorrelatedError(result: ResultBody): void;
}

export class SessionError extends Error {}

// Derive the socket URL from the page origin so a tunnel's public host works unchanged.
export function websocketUrl(location: Pick<Location, "protocol" | "host">): string {
  const scheme = location.protocol === "https:" ? "wss:" : "ws:";
  return `${scheme}//${location.host}/ws`;
}

export async function startSession(nickname: string): Promise<SessionInfo> {
  let response: Response;
  try {
    response = await fetch("/api/sessions", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nickname }),
    });
  } catch {
    throw new SessionError("The server is unreachable.");
  }
  if (response.status === 422) throw new SessionError("Nicknames must be 1 to 24 characters.");
  if (response.status === 403) throw new SessionError("This address is not allowed by the server.");
  if (response.status === 409) throw new SessionError("Leave your room before changing nickname.");
  if (!response.ok) throw new SessionError("The server is busy. Try again soon.");
  return (await response.json()) as SessionInfo;
}

interface Pending {
  resolve(result: ResultBody): void;
  reject(error: Error): void;
}

export class Connection {
  private socket: WebSocket | null = null;
  private readonly pending = new Map<string, Pending>();

  constructor(private readonly events: ConnectionEvents) {}

  open(): void {
    this.close();
    const socket = new WebSocket(websocketUrl(window.location));
    this.socket = socket;
    let opened = false;

    socket.addEventListener("open", () => {
      opened = true;
    });
    socket.addEventListener("message", (event: MessageEvent<unknown>) => {
      if (socket !== this.socket || typeof event.data !== "string") return;
      this.receive(event.data);
    });
    socket.addEventListener("close", (event) => {
      if (socket !== this.socket) return;
      this.socket = null;
      this.failPending();
      this.events.onClosed(closeReason(event.code, opened));
    });
  }

  close(): void {
    const socket = this.socket;
    this.socket = null;
    this.failPending();
    socket?.close();
  }

  command<T extends CommandType>(type: T, body: CommandBodies[T]): Promise<ResultBody> {
    const socket = this.socket;
    if (socket === null || socket.readyState !== WebSocket.OPEN) {
      return Promise.reject(new UncertainError("Not connected."));
    }
    const command_id = newCommandId();
    return new Promise<ResultBody>((resolve, reject) => {
      this.pending.set(command_id, { resolve, reject });
      socket.send(JSON.stringify({ version: PROTOCOL_VERSION, command_id, type, body }));
    });
  }

  private receive(raw: string): void {
    const message = parseServerMessage(raw);
    if (message === null) return;
    switch (message.type) {
      case "session.ready":
        this.events.onReady(message.body);
        break;
      case "room.snapshot":
        this.events.onSnapshot(message.body);
        break;
      case "command.result": {
        const id = message.body.command_id;
        const waiter = id === null ? undefined : this.pending.get(id);
        if (id !== null && waiter) {
          this.pending.delete(id);
          waiter.resolve(message.body);
        } else {
          this.events.onUncorrelatedError(message.body);
        }
        break;
      }
    }
  }

  private failPending(): void {
    // Never replay these automatically; the user decides after reconnecting.
    for (const waiter of this.pending.values()) {
      waiter.reject(new UncertainError("Connection lost before the server answered."));
    }
    this.pending.clear();
  }
}

function closeReason(code: number, opened: boolean): string {
  if (code === CLOSE_ALREADY_CONNECTED) {
    return "This session is open in another tab. Use a private window or another browser profile for a second player.";
  }
  if (code === 1009) return "A message was too large and the server closed the connection.";
  if (code === 1013) return "The connection fell behind and was closed. Reconnect to continue.";
  if (!opened) return "Could not connect to the server.";
  return "Disconnected from the server. Your seat was released — reconnect and rejoin.";
}
