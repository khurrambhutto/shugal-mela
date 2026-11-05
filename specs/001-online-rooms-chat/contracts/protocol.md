# Protocol v1: Online rooms and chat

This contract is proposed for feature 001. No endpoint is implemented yet.
Use JSON over same-origin HTTP and WebSockets. Reject extra command fields.
Count text limits in Unicode code points and transport limits in UTF-8 bytes.

## HTTP

### GET /api/health

Return HTTP 200 with `{"status":"ok"}` while the application is serving requests.
This endpoint exposes no sessions or room information.

### POST /api/sessions

Request body:

```json
{"nickname":"Ali"}
```

Create a guest session or restore the session identified by a valid cookie.
Return HTTP 201 for creation or HTTP 200 for restoration:

```json
{"session_id":"public-session-id","nickname":"Ali","protocol_version":1}
```

Set a session-scoped `shugal_session` cookie with HttpOnly, SameSite=Lax, and Path=/.
Use Secure for the public HTTPS origin. Permit a non-Secure cookie only in explicit local HTTP mode.
The cookie contains an opaque random credential, never the public session ID alone.
An unknown or expired cookie creates a new session and replaces that cookie.
Reject a nickname change with HTTP 409 while the session belongs to a room.

Validate the request origin against `ALLOWED_ORIGINS` before issuing a cookie.
Return HTTP 403 for an untrusted or absent browser origin, HTTP 422 for an invalid body,
and HTTP 503 if the session limit is reached. Browser requests use `credentials: same-origin`.
Use an exact origin, including scheme and port, rather than allowing every hostname.

## WebSocket connection

Connect to `/ws` on the page's origin. Use `ws://` for local HTTP and `wss://` for HTTPS.
The browser supplies its session cookie automatically. Verify the cookie and `Origin`
before accepting. Deny unauthorized or cross-origin handshakes with HTTP 403.

After accepting a valid connection, send:

```json
{"version":1,"type":"session.ready","body":{"session_id":"public-session-id","nickname":"Ali"}}
```

If a session already has an active connection, close the new connection with code 4409.
Show a message that another tab is connected. Distinct test players need separate browser contexts.
Use server WebSocket ping and timeout settings to detect dead connections.
Detected disconnect releases membership in this feature.

> Superseded by [feature 004](../../004-reconnect/contracts/protocol.md): the newest connection
> takes over and the older one closes with `4000`, and a disconnect holds the seat for 60 seconds.

## Commands

Every client command has this envelope:

```json
{"version":1,"command_id":"b838d8b5-dfa6-4f8d-a631-8355c5f003ba","type":"room.join","body":{"code":"ABCD23"}}
```

`command_id` is a UUID generated for a user action. An unchanged retry uses the same ID.
The server derives identity from the authenticated connection. No command body accepts `sender_id`.

Supported types and bodies:

- `room.create`: `{"capacity":2}` or `{"capacity":4}`. Allocate the creator's seat and a unique code.
- `room.join`: `{"code":"ABCD23"}`. Trim and uppercase before lookup.
- `room.leave`: `{}`. Remove the current membership. When already outside a room, succeed without a mutation.
- `room.sync`: `{}`. Return the current snapshot. When outside a room, return `NOT_IN_ROOM`.
- `chat.send`: `{"text":"Hello!"}`. Send only to the connection's current room after trimming and validation.

A create or join succeeds only if the session is outside a room, except that joining
its current room returns existing membership. Serialize that check with the membership update.

## Results and snapshots

For an accepted command, send a result to its initiating connection:

```json
{"version":1,"type":"command.result","body":{"command_id":"b838d8b5-dfa6-4f8d-a631-8355c5f003ba","ok":true,"room_code":"ABCD23","revision":2}}
```

For `chat.send`, also include `message_id` in the result body.
For leave, the result uses `room_code:null` and `revision:null`, and the client clears room state.
For an unchanged join, return the existing revision and send that member a current snapshot.
For sync, return the current revision and send a snapshot only to the requester.

A state-changing create, join, leave, chat, or disconnect broadcasts a full snapshot
to the affected room's remaining members. A creator or joining member receives that snapshot too:

```json
{
  "version":1,
  "type":"room.snapshot",
  "body":{
    "code":"ABCD23",
    "capacity":2,
    "revision":2,
    "members":[
      {"session_id":"session-a","nickname":"Ali"},
      {"session_id":"session-b","nickname":"Sara"}
    ],
    "messages":[]
  }
}
```

Each message in `messages` has `message_id`, `sender_session_id`, `sender_nickname`,
`text`, and `sent_at`, with `sent_at` as an ISO 8601 UTC string.
Replace the client's bounded history with the snapshot history. Ignore a lower revision
for the same room and never subscribe a session to a room without accepted membership.
Revisions from different rooms are not comparable.

An acknowledgement and its snapshot may arrive in either order.
Register the pending join target before sending its command so an initial snapshot can be accepted safely.
Accept snapshots only for the current room or pending create/join operation on that connection.
After a successful leave, clear room state and ignore snapshots for the old room.
Membership locking and per-connection send ordering must keep a leave result after any snapshot
from the old membership. Test leave-versus-broadcast races rather than relying only on browser filters.

For create, whose code is not yet known, the first snapshot on that connection establishes
the room only while a create is pending. The server remains responsible for room isolation.

## Errors

A rejected command returns:

```json
{"version":1,"type":"command.result","body":{"command_id":"b838d8b5-dfa6-4f8d-a631-8355c5f003ba","ok":false,"error":{"code":"ROOM_FULL","message":"This room has no available seats."}}}
```

Define these codes:

- `VALIDATION_ERROR`: malformed JSON, invalid field, or unknown command. Without a valid ID, use `command_id:null`.
- `UNSUPPORTED_VERSION`: the requested protocol version is unsupported.
- `ROOM_NOT_FOUND`: the code has no active room.
- `ROOM_FULL`: no seat is available.
- `ALREADY_IN_ROOM`: the session must leave its other room first.
- `NOT_IN_ROOM`: the command requires membership.
- `RATE_LIMITED`: the applicable rate is exceeded. Include `retry_after_ms` inside `error`.
- `COMMAND_ID_REUSED`: an existing ID names different command contents.
- `SERVER_BUSY`: a configured capacity limit prevents the operation.

An error result with a valid ID completes that command. A new user attempt after a
rate limit uses a new ID. Retry a completed command automatically only to recover its original result.
Do not expose stack traces or credential details in errors.

## Bounds and recovery

- At most 20 rooms and 100 unexpired sessions by default.
- At most 30 commands per session in a rolling ten-second interval.
- At most five chat commands per session in a rolling ten-second interval, within the overall limit.
- At most 20 session-creation attempts per minute across the process. This is a development default,
  not a production abuse-control claim. Existing valid sessions may be restored without allocating new ones.
- Maximum incoming message size is 8 KiB. Close with code 1009 on an oversized frame.
- At most 32 pending outbound messages per connection. Close with code 1013 on overflow.
- Retain at most 100 completed command results per session for ten minutes.
- Retain 50 chat messages per room and expire disconnected sessions after 30 minutes of inactivity.

On closure, disable mutations, reject pending UI actions as uncertain, and show the rejoin option.
Do not automatically replay uncertain mutations in this feature. After manual reconnect,
establish the session and read fresh state before sending new user actions.
Server restart invalidates all in-memory identities and rooms.
