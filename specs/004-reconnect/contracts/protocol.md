# Protocol additions for reconnecting

These extend [protocol v1](../../001-online-rooms-chat/contracts/protocol.md) and the
[online Ludo additions](../../003-online-ludo/contracts/protocol.md). Version stays `1`.

## `session.ready`

The body gains `room_code`: the room this session still holds a seat in, or `null`.
When it is not `null`, a `room.snapshot` for that room follows.

## Members

Each entry in `room.snapshot.members` gains `away_ms`:

```json
{"session_id": "session-b", "nickname": "Sara", "away_ms": 41250}
```

`null` means connected. A number is the time left, in milliseconds when the snapshot was built,
before the member's seat is released. Clients count down from the moment they receive it.

## Errors

New codes: `MATCH_PAUSED` (a seated player is reconnecting) and `PLAYER_AWAY`
(a match cannot start while a member is reconnecting).

## Close codes

`4000` replaces `4409`: a newer connection for the same session took over. The client
does not reconnect automatically after `4000`, so two tabs never fight over one seat.
