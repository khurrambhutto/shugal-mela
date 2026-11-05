# Tasks: Recover from connection loss

**Status:** T001–T008 complete on 2026-11-05: backend 278 passed, frontend 32 unit tests passed,
7 Chromium browser tests passed, including refresh mid-match, a dropped socket pausing and resuming
the match, a second tab taking over, and a server restart. T009 needs real devices.

- [x] T001 Keep away members in rooms with a deadline, reconnect them, and release expired seats.
- [x] T002 Replace older connections with `4000` and ignore cleanup of a replaced connection.
- [x] T003 Pause matches while a seated player is away; block starting while anyone is away.
- [x] T004 Add `room_code` to `session.ready`, `away_ms` to members, and the new codes to models and fixtures.
- [x] T005 Add `backend/tests/test_reconnect.py`: seat kept, snapshot on return, pause, expiry in lobby and
  in a match, replacement, and a retried roll command ID after reconnecting rolling once.
- [x] T006 Client: automatic reconnect with backoff, room kept while reconnecting, refresh resumes the seat.
- [x] T007 UI: away countdown on seats, paused banner, controls disabled while paused or offline.
- [x] T008 Browser test: refresh mid-match keeps the seat; going offline pauses and coming back resumes.
- [ ] T009 Manual check across networks: refresh, toggle Wi-Fi briefly, and stay offline past 60 seconds.
