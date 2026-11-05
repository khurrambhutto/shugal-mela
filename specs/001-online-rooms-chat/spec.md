# Feature specification: Online rooms and chat

**Feature:** `001-online-rooms-chat`.
**Created:** 2026-11-05.
**Status:** Specified. Implementation pending.
**Input:** Host a FastAPI and TypeScript browser application on a laptop so friends on different networks can join private rooms and chat without paid hosting.

## User scenarios and testing

### US1: Join a private room, priority P1

As a player, I enter a nickname, create a room, and share its code with friends.
Friends join using that code and see the same player list.

**Why this priority:** Rooms establish the player grouping that Ludo and voice will reuse.
**Independent test:** Use separate browser profiles to create and join a room without sending chat.

Acceptance scenarios:

1. Given a new browser session, when I enter a valid nickname and create a two-player room,
   then I see a room code, my membership, and one available seat.
2. Given that code, when another session joins, then both players see the same two members.
3. Given a full room, when another session tries to join, then it receives `ROOM_FULL` and no membership changes.
4. Given a member, when that member leaves or disconnects, then the other members see the updated list.
5. Given two simultaneous requests for the last seat, when the server handles them,
   then exactly one succeeds.

### US2: Exchange room messages, priority P1

As a room member, I send text messages and see messages from the other members.

**Why this priority:** Chat proves bidirectional updates and makes the first network milestone useful.
**Independent test:** In an existing room fixture, exchange text between two sessions and observe a separate room.

Acceptance scenarios:

1. Given two connected members, when one sends a valid message,
   then both see it once with the server-assigned sender, message ID, and time.
2. Given a member in another room, when the first room receives a message,
   then the other room receives no update or message from that exchange.
3. Given an outsider, when it tries to send to a room, then the server rejects it without broadcasting.
4. Given a previously accepted command ID, when the same session retries the same command,
   then the original result is returned and the message is not appended again.
5. Given markup-like text, when it is sent, then the browser displays it as text without executing it.

### US3: Play host for friends on other networks, priority P1

As the host, I run the application and tunnel on my laptop and share one public address.
A friend opens that address without installing software or changing router settings.

**Why this priority:** Cross-network access is an explicit project requirement.
**Independent test:** Use the built application from a phone with Wi-Fi disabled and a laptop on Wi-Fi.

Acceptance scenarios:

1. Given the configured public address, when two devices on different networks open it,
   then both can join a room and exchange messages in both directions.
2. Given a public page, when it connects, then its requests target the public origin rather than either player's `localhost`.
3. Given an interrupted tunnel or server, when the connection closes,
   then the UI shows that it is offline and disables message submission.
4. Given a restarted service or changed public address, when sessions are no longer available,
   then the UI explains that the player must rejoin rather than claiming the room was recovered.

## Functional requirements

- **FR-001:** A guest can choose a trimmed nickname of 1 through 24 Unicode characters without account registration.
- **FR-002:** The server establishes identity through a private browser credential. Commands cannot select their own sender identity.
- **FR-003:** A guest can create a room with capacity two or four, including the creator's seat.
- **FR-004:** Each room has a unique six-character uppercase join code. Join codes accept lowercase input and exclude `I` and `O`.
- **FR-005:** A session belongs to at most one room and has at most one active connection. Conflicting operations return a clear error.
- **FR-006:** Room creation, joining, leaving, and detected disconnects update every affected member's player list. Empty rooms are deleted.
- **FR-007:** Only room members can send chat or receive the room's state. Joining an unknown or full room fails without changing membership.
- **FR-008:** Chat contains 1 through 500 Unicode characters after trimming. The server assigns message IDs, timestamps, and sender details.
- **FR-009:** Each room retains its most recent 50 accepted messages in server order. New members receive that history.
- **FR-010:** A session may submit at most five chat messages in a rolling ten-second interval. Excess messages receive `RATE_LIMITED` with a retry delay.
- **FR-011:** Commands have unique IDs. For ten minutes, up to the most recent 100 completed commands per session return their original outcome when retried unchanged. Reusing an ID with different contents is rejected.
- **FR-012:** Public room snapshots have monotonically increasing revisions. A browser ignores older snapshots for that room.
- **FR-013:** Malformed, oversized, unauthorized, and unsupported requests produce defined errors or connection closures without corrupting state.
- **FR-014:** A disconnect releases the player's seat when the server detects it. Automatic seat recovery and offline command replay are outside this feature.
- **FR-015:** The built frontend, API, and live connection work through one public HTTPS origin, with no required client installation or router configuration.
- **FR-016:** Server or tunnel loss produces a visible offline state. A player can reconnect manually, refresh state, and rejoin an available room.
- **FR-017:** Application state is temporary. Restarting the backend clears rooms, sessions, deduplication records, and messages. The interface explains this limitation.
- **FR-018:** Logs and public snapshots exclude session credentials. The browser renders chat and nicknames as plain text.
- **FR-019:** The application bounds room count, session count, message size, request rate, and pending outbound messages. Exceeding a limit returns a defined failure and keeps other rooms responsive.

## Key entities

- **Guest session:** Private identity, public session ID, nickname, expiry, and current room membership.
- **Room:** Code, capacity, member list in join order, revision, and recent chat history.
- **Chat message:** Server-assigned ID, sender identity and display name, text, and accepted time.
- **Command result:** The original outcome associated with a session and command ID during the deduplication window.

## Edge cases

- Two users may choose the same nickname. Public session IDs still distinguish them.
- A lost acknowledgement may lead to a retry. The command ID prevents a second chat append within the documented window.
- A duplicate join for the same current room returns its existing membership without allocating another seat.
- A session already in a different room must leave before joining or creating another room.
- A second tab with the same cookie is the same session. Reject its competing connection and explain how to use a separate profile for testing.
- A slow browser is disconnected if its bounded outbound queue fills. Other members continue to receive updates.
- A room disappears after its last member leaves. Reusing its old code fails unless a newly created room independently receives that code.
- A broken connection may take time for heartbeat detection. The seat remains occupied until detection; there is no guaranteed instant network-failure notification.

## Success criteria

- **SC-001:** Two sessions create and join a room, agree on its membership, and leave it successfully.
- **SC-002:** Each of 20 sequential accepted messages appears once in the same order for both members.
- **SC-003:** All room-isolation, invalid-command, duplicate-command, and concurrent-final-seat checks pass.
- **SC-004:** Two real devices on different networks exchange messages through the laptop's public address. Record the actual networks and outcome.
- **SC-005:** Stopping the server or tunnel results in an offline display once disconnection is detected. The browser accepts no new chat submission while offline.
- **SC-006:** The host can reproduce startup and remote access using the documented procedure without a paid host or purchased domain.

## Assumptions and exclusions

Target current desktop Chrome or Firefox and mobile Chrome or Safari.
The host keeps the laptop awake and online. A tunnel provider is available under its current free terms.
Rooms are private by unlisted join code, not protected by a separate password or account invitation system.
Capacity and rate limits are defaults that can be adjusted after observing actual use.

Ludo, match readiness, creator controls, reconnect seat reservations, SQLite, voice, accounts,
matchmaking, and leaderboards belong to later features. Focused automated checks in the plan
are required because room isolation and concurrent membership are core behavior.
