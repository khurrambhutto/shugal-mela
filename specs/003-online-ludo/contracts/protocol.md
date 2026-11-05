# Protocol additions for online Ludo

These extend [protocol v1](../../001-online-rooms-chat/contracts/protocol.md). The envelope,
command IDs, deduplication, rate limits, and result format are unchanged. Version stays `1`.

## Commands

- `match.ready`: `{"ready": true}`. Set this member's readiness. Rejected with `MATCH_IN_PROGRESS` during play.
- `match.start`: `{}`. Host only. Needs two or four members and every non-host member ready.
- `match.roll`: `{"match_id": "…", "step": 7}`. The server rolls for the current seat.
- `match.move`: `{"match_id": "…", "step": 8, "token": 2}`. Move one of the session's tokens.

The host is the first member in join order. If the host leaves, the next member becomes host.

## Snapshot additions

`room.snapshot` bodies gain `host`, `ready`, and `match`:

```json
{
  "host": "session-a",
  "ready": ["session-b"],
  "match": {
    "match_id": "4f2c…",
    "status": "playing",
    "seats": [{"session_id": "session-a", "colour": "red"}, {"session_id": "session-b", "colour": "yellow"}],
    "colours": ["red", "yellow"],
    "tokens": {"red": [-1, 0, -1, -1], "yellow": [-1, -1, -1, -1]},
    "current": "red",
    "phase": "awaiting_roll",
    "roll": null,
    "legal_moves": [],
    "winner": null,
    "step": 3,
    "events": [{"kind": "moved", "colour": "red", "token": 1, "from_progress": -1, "to_progress": 0}],
    "ended_reason": null
  }
}
```

`status` is `playing`, `finished`, or `ended`. `match` is `null` before the first start.
`step` increases by one with every accepted roll or move. `events` lists what that step did,
using the event kinds from the rules: `rolled`, `moved`, `captured`, `token_home`, `extra_roll`,
`sixes_forfeited`, `no_legal_move`, `turn_passed`, and `won`.
Token progress uses the rules encoding: `-1` yard, `0`–`50` track, `51`–`55` home column, `56` home.

## Error codes

New codes: `NOT_HOST`, `NOT_READY`, `WRONG_PLAYER_COUNT`, `MATCH_IN_PROGRESS`, `NO_MATCH`,
`STALE_STATE`, `NOT_YOUR_TURN`, `WRONG_PHASE`, and `ILLEGAL_MOVE`.
