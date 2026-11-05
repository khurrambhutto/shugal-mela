# Host a game for friends

Run Shugal Mela on your laptop and let friends on other networks join through a
free Cloudflare Quick Tunnel. Friends need only a browser and the link. They install nothing.

```text
Friend's browser ──https/wss──▶ Cloudflare ◀──outbound tunnel── cloudflared ──▶ FastAPI on 127.0.0.1:8000
```

`cloudflared` connects outward from your laptop, so there is no router port forwarding,
and it works behind home NAT or a mobile carrier's CGNAT. FastAPI still listens only on
loopback. Everything public goes through the tunnel's single HTTPS origin.

## One-time setup

You need uv, Python 3.12, Node.js with npm, and `cloudflared`.
Install `cloudflared` without root by placing the official binary on your `PATH`:

```bash
curl -fL -o ~/.local/bin/cloudflared \
  https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
chmod +x ~/.local/bin/cloudflared
cloudflared --version
```

Quick Tunnels need no Cloudflare account.

## Start a session

From the project root:

```bash
./scripts/host
```

The script:

1. Builds the frontend into `frontend/dist/`.
2. Installs the locked backend dependencies.
3. Starts `cloudflared tunnel --url http://127.0.0.1:8000` and waits for its `https://….trycloudflare.com` address.
4. Starts one Uvicorn worker with `APP_MODE=public` and `ALLOWED_ORIGINS` set to that exact address.

Public mode marks the session cookie `Secure` and accepts only `https://` origins.
Because the tunnel starts first, the backend never needs a restart to learn the address.
Use `PORT=8100 ./scripts/host` if port 8000 is taken.

Share the printed address and, once you create a room, its six-character code.
Open the public address on your own laptop too. `http://localhost:8000` is rejected in public
mode because it is a different origin.

### Manual equivalent

```bash
cd frontend && npm ci && npm run build && cd ..
cloudflared tunnel --url http://127.0.0.1:8000      # terminal 1: note the https address
cd backend                                          # terminal 2
APP_MODE=public ALLOWED_ORIGINS=https://<address>.trycloudflare.com \
  uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --ws-max-size 8192
```

Keep one worker. Rooms live in that process's memory.

## Stop

Press Ctrl+C in the `./scripts/host` terminal. Uvicorn closes every WebSocket,
browsers show **Offline**, and the script stops the tunnel.

## When the address changes

A Quick Tunnel gets a new random address every time it starts, and it has no uptime guarantee.
After a restart:

- Send friends the new address. The old one stops working.
- Cookies belong to the old address, so everyone enters a nickname again.
- Rooms and chat are gone. They live in memory until phase 7 adds SQLite.

If only the tunnel or a player's Wi-Fi drops, browsers show **Reconnecting…** and retry on their own.
The server holds each seat for 60 seconds and pauses a match until everyone is back. Refreshing the
page also returns to the same seat. After 60 seconds the seat is released and a match ends.

## Limits and failure modes

- Keep the laptop awake and online. Sleep or a network change disconnects everyone.
- Anyone with the address can load the page. Joining a room still needs its code, and the
  server enforces origin checks, sessions, rate limits, and room and session caps.
- Cloudflare may close long-lived connections. The browser detects the closure and shows Offline.
- Quick Tunnels are meant for testing and have no SLA. Check Cloudflare's current terms
  before relying on them.
- Two tabs in the same browser profile share one session; the second is rejected.

## Verify cross-network play

Follow the "Check different-network access" steps in
[the quickstart](../specs/001-online-rooms-chat/quickstart.md). One device must use a different
network, such as a phone with Wi-Fi turned off. Two devices on the same Wi-Fi do not count.
