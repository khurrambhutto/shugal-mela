# Data model: Online rooms and chat

All data is process-local in this feature. These are design contracts, not implemented models.

## Session

Fields include public `session_id`, a private credential hash, trimmed `nickname`,
optional `room_code`, active connection identity, last activity time, and recent command outcomes.
Issue credentials from a cryptographically secure random source with at least 256 bits of entropy.
Use the opaque credential only in the session cookie. Keep its hash in the session lookup.
Expire a disconnected session after 30 minutes of inactivity. Keep connected sessions active.

Nickname length is 1 through 24 Unicode code points after trimming.
Nicknames need not be unique. A session belongs to at most one room.
After joining, change a nickname only after leaving the room in this feature.

## Room

Fields include `code`, `capacity`, ordered member session IDs, `revision`, and recent messages.
Generate a six-character code from `ABCDEFGHJKLMNPQRSTUVWXYZ23456789` and retry on collisions.
Capacity is two or four. The creator occupies the first seat.
A new room starts at revision 1. Every accepted membership or chat change increments its revision once.
An unchanged join or duplicate command does not increment it. Delete a room when empty.

Public snapshots include code, capacity, public member IDs and nicknames, recent messages,
and revision. They exclude session credentials, credential hashes, and internal connection objects.

## Message

Fields include `message_id`, `sender_session_id`, `sender_nickname`, `text`, and `sent_at`.
The server assigns the ID and a UTC timestamp when accepting the message.
Keep accepted order, even if wall-clock timestamps match or the clock changes.
Store at most the last 50 messages per room. Text contains 1 through 500 Unicode code points after trimming.

## Completed command

Fields include session ID, command ID, normalized request content, original result, and accepted or rejected time.
Remember up to the last 100 completed commands per session for ten minutes.
Within those bounds, an identical retry returns the original result without another mutation.
A different request with the same command ID returns `COMMAND_ID_REUSED`.
Beyond those bounds, retries have no exactly-once promise. The UI must not replay old offline commands.
This feature does not persist outcomes across server restarts.

## State transitions and invariants

- A new session has no room. Creation or join allocates one seat and sends a snapshot.
- Join checks session membership and room capacity within the coordinated state change.
- Leave or detected disconnect removes exactly that session's membership.
- Reject a second live connection for the same session. Cleanup is tied to the registered connection identity.
- A chat command requires current membership and room capacity does not affect chat authorization.
- Each room's member count stays within capacity, and members are unique.
- Session membership and room membership agree after every accepted command.
- Rejected commands leave room state and revision unchanged.
- Distinct rooms share no messages or membership broadcasts.
