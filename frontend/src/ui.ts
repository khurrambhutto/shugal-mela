// DOM rendering. All player-supplied text is set with textContent, never as HTML.

import type { ChatMessage, RoomSnapshot } from "./protocol";
import { canSubmit, type AppState, type ConnectionStatus } from "./state";

export interface UiActions {
  start(nickname: string): void;
  reconnect(): void;
  create(capacity: 2 | 4): void;
  join(code: string): void;
  leave(): void;
  send(text: string): Promise<boolean>;
}

const STATUS_LABELS: Record<ConnectionStatus, string> = {
  idle: "Not connected",
  connecting: "Connecting…",
  connected: "Connected",
  offline: "Offline",
};

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
  const status = el("p", { className: "status" });
  status.setAttribute("role", "status");
  const who = el("span", { className: "who" });
  const reconnect = el("button", { type: "button", textContent: "Reconnect" });
  reconnect.addEventListener("click", () => actions.reconnect());
  const notice = el("p", { className: "notice" });
  notice.setAttribute("role", "alert");

  // Nickname entry
  const nicknameInput = el("input", { name: "nickname", maxLength: 24, required: true, autocomplete: "nickname" as AutoFill });
  nicknameInput.value = loadNickname();
  const nicknameForm = el(
    "form",
    { className: "card" },
    el("label", {}, "Nickname ", nicknameInput),
    el("button", { type: "submit", textContent: "Continue" }),
  );
  nicknameForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const nickname = nicknameInput.value.trim();
    if (!nickname) return;
    saveNickname(nickname);
    actions.start(nickname);
  });

  // Lobby
  const create2 = el("button", { type: "button", textContent: "Create 2-player room" });
  const create4 = el("button", { type: "button", textContent: "Create 4-player room" });
  create2.addEventListener("click", () => actions.create(2));
  create4.addEventListener("click", () => actions.create(4));
  const codeInput = el("input", {
    name: "code",
    maxLength: 6,
    placeholder: "ABCD23",
    autocomplete: "off",
    spellcheck: false,
  });
  codeInput.className = "code-input";
  const joinButton = el("button", { type: "submit", textContent: "Join" });
  const joinForm = el("form", { className: "row" }, el("label", {}, "Room code ", codeInput), joinButton);
  joinForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const code = codeInput.value.trim();
    if (code) actions.join(code);
  });
  const lobby = el("section", { className: "card" }, el("div", { className: "row" }, create2, create4), joinForm);

  // Room
  const roomCode = el("strong", { className: "room-code" });
  const seats = el("span", { className: "seats" });
  const leaveButton = el("button", { type: "button", textContent: "Leave room" });
  leaveButton.addEventListener("click", () => actions.leave());
  const memberList = el("ul", { className: "members" });
  const messageList = el("ol", { className: "messages" });
  messageList.setAttribute("aria-live", "polite");
  const chatInput = el("input", { name: "text", maxLength: 500, autocomplete: "off", placeholder: "Message" });
  const sendButton = el("button", { type: "submit", textContent: "Send" });
  const composer = el("form", { className: "row composer" }, chatInput, sendButton);
  composer.addEventListener("submit", (event) => {
    event.preventDefault();
    const text = chatInput.value.trim();
    if (!text) return;
    void actions.send(text).then((sent) => {
      if (sent && chatInput.value.trim() === text) chatInput.value = "";
    });
  });
  const room = el(
    "section",
    { className: "card" },
    el("div", { className: "row spread" }, el("span", {}, "Room ", roomCode, " ", seats), leaveButton),
    memberList,
    messageList,
    composer,
  );

  root.replaceChildren(
    el("div", { className: "row spread" }, status, who),
    notice,
    reconnect,
    nicknameForm,
    lobby,
    room,
  );

  let renderedRoom: RoomSnapshot | null = null;

  return (state: AppState): void => {
    const live = canSubmit(state);
    status.dataset.state = state.status;
    status.textContent = STATUS_LABELS[state.status];
    who.textContent = state.session ? `Playing as ${state.session.nickname}` : "";
    notice.textContent = state.notice ?? "";
    notice.hidden = state.notice === null;

    reconnect.hidden = !(state.status === "offline" && state.session !== null);
    nicknameForm.hidden = state.session !== null || state.status === "connecting";
    lobby.hidden = state.session === null || state.room !== null || state.status !== "connected";
    room.hidden = state.room === null;

    const busy = state.pendingRoom !== null;
    for (const control of [create2, create4, codeInput, joinButton]) control.disabled = !live || busy;
    if (state.status === "offline" && state.lastRoomCode && !codeInput.value) codeInput.value = state.lastRoomCode;
    for (const control of [chatInput, sendButton, leaveButton]) control.disabled = !live;

    if (state.room !== renderedRoom) {
      renderedRoom = state.room;
      if (state.room) renderRoom(state.room, state.session?.session_id ?? null);
    }
  };

  function renderRoom(snapshot: RoomSnapshot, me: string | null): void {
    roomCode.textContent = snapshot.code;
    seats.textContent = `${snapshot.members.length}/${snapshot.capacity} players`;
    memberList.replaceChildren(
      ...snapshot.members.map((m) =>
        el("li", { textContent: m.session_id === me ? `${m.nickname} (you)` : m.nickname }),
      ),
    );
    const nearBottom = messageList.scrollHeight - messageList.scrollTop - messageList.clientHeight < 40;
    messageList.replaceChildren(...snapshot.messages.map((m) => renderMessage(m, me)));
    if (nearBottom) messageList.scrollTop = messageList.scrollHeight;
  }
}

function renderMessage(message: ChatMessage, me: string | null): HTMLLIElement {
  const time = new Date(message.sent_at);
  const item = el(
    "li",
    { className: message.sender_session_id === me ? "mine" : "" },
    el("span", { className: "sender", textContent: message.sender_nickname }),
    el("span", { className: "text", textContent: message.text }),
    el("time", {
      dateTime: message.sent_at,
      textContent: time.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    }),
  );
  return item;
}

function loadNickname(): string {
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
