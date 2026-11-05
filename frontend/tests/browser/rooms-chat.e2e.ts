import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

import { expect, test, type Browser, type Page } from "@playwright/test";

async function newPlayer(browser: Browser, nickname: string, baseURL?: string): Promise<Page> {
  // Separate contexts have separate cookie jars, so each is a distinct player.
  const context = await browser.newContext(baseURL ? { baseURL } : {});
  const page = await context.newPage();
  await page.goto("/");
  await page.getByLabel("Nickname").fill(nickname);
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByRole("status")).toHaveText("Connected");
  return page;
}

async function sendChat(page: Page, text: string): Promise<void> {
  await page.getByPlaceholder("Message").fill(text);
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByPlaceholder("Message")).toHaveValue("");
}

async function createRoom(page: Page, capacity: 2 | 4 = 2): Promise<string> {
  await page.getByRole("button", { name: `Create ${capacity}-player room` }).click();
  const code = page.locator(".room-code");
  await expect(code).toHaveText(/^[A-HJ-NP-Z2-9]{6}$/);
  return (await code.textContent())!;
}

const members = (page: Page) => page.locator(".seat:not(.is-empty):not([hidden]) .member-name");
const messageTexts = (page: Page) => page.locator(".messages .text");

test("two players create, join, chat, and leave a room", async ({ browser }) => {
  const ali = await newPlayer(browser, "Ali");
  const sara = await newPlayer(browser, "Sara");

  const code = await createRoom(ali);

  await sara.getByLabel("Room code").fill(code.toLowerCase());
  await sara.getByRole("button", { name: "Join" }).click();
  await expect(members(ali)).toHaveText(["Ali (you)", "Sara"]);
  await expect(members(sara)).toHaveText(["Ali", "Sara (you)"]);
  await expect(ali.locator(".seats")).toHaveText("2/2 players");

  // A third player cannot take a seat in the full room.
  const omar = await newPlayer(browser, "Omar");
  await omar.getByLabel("Room code").fill(code);
  await omar.getByRole("button", { name: "Join" }).click();
  await expect(omar.getByRole("alert")).toHaveText("That room is full.");

  // Omar's own room stays isolated from Ali and Sara's chat.
  expect(await createRoom(omar)).not.toBe(code);

  // Ten alternating messages, five per player: the per-session limit is five per ten seconds.
  // The last one is markup, which must be shown as text and never executed.
  const markup = '<img src=x onerror="window.__pwned=1"><b>bold</b>';
  const expected = [...Array.from({ length: 9 }, (_, i) => `message ${i}`), markup];
  for (const [i, text] of expected.entries()) await sendChat(i % 2 === 0 ? ali : sara, text);

  await expect(messageTexts(ali)).toHaveText(expected);
  await expect(messageTexts(sara)).toHaveText(expected);
  await expect(messageTexts(omar)).toHaveCount(0);
  expect(await ali.locator(".messages img, .messages b").count()).toBe(0);
  expect(await ali.evaluate(() => (window as { __pwned?: number }).__pwned)).toBeUndefined();

  // A sixth message inside ten seconds is refused, and the draft is kept.
  await sara.getByPlaceholder("Message").fill("one too many");
  await sara.getByRole("button", { name: "Send" }).click();
  await expect(sara.getByRole("alert")).toContainText("Slow down");
  await expect(sara.getByPlaceholder("Message")).toHaveValue("one too many");
  await expect(messageTexts(ali)).toHaveCount(10);

  await sara.getByRole("button", { name: "Leave room" }).click();
  await expect(members(ali)).toHaveText(["Ali (you)"]);
  await expect(sara.getByRole("button", { name: "Create 2-player room" })).toBeVisible();
});

test("a second tab with the same session takes over", async ({ browser }) => {
  const first = await newPlayer(browser, "Ali");
  const second = await first.context().newPage();
  await second.goto("/");
  await second.getByLabel("Nickname").fill("Ali");
  await second.getByRole("button", { name: "Continue" }).click();
  await expect(second.getByRole("status")).toHaveText("Connected");
  await expect(first.getByRole("alert")).toContainText("opened in another tab");
  // The replaced tab does not fight back.
  await expect(first.getByRole("status")).toHaveText("Offline");
  await expect(second.getByRole("status")).toHaveText("Connected");
});

test("a server restart reconnects on its own and explains the lost seat", async ({ browser }) => {
  test.setTimeout(60_000);
  const port = 8766;
  const origin = `http://localhost:${port}`;
  const startServer = () =>
    spawn("uv", ["run", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", String(port)], {
      cwd: fileURLToPath(new URL("../../../backend", import.meta.url)),
      env: { ...process.env, APP_MODE: "development", ALLOWED_ORIGINS: origin },
      stdio: "ignore",
      // Its own process group, so stopping it also stops uvicorn under `uv run`.
      detached: true,
    });
  const stop = (signal: NodeJS.Signals) => {
    try {
      process.kill(-server.pid!, signal);
    } catch {
      // Already stopped.
    }
  };
  const healthy = () =>
    expect
      .poll(async () => (await fetch(`${origin}/api/health`).catch(() => null))?.status ?? 0, { timeout: 15_000 })
      .toBe(200);
  let server = startServer();
  try {
    await healthy();
    const ali = await newPlayer(browser, "Ali", origin);
    await createRoom(ali);

    stop("SIGTERM");
    await expect(ali.getByRole("status")).toHaveText("Reconnecting…");
    await expect(ali.getByRole("alert")).toContainText("Reconnecting");
    await expect(ali.getByPlaceholder("Message")).toBeDisabled();
    await expect(ali.getByRole("button", { name: "Send" })).toBeDisabled();
    // The room stays on screen while retrying.
    await expect(ali.locator(".room-code")).toBeVisible();

    // Rooms live in memory, so a restarted server no longer has the seat.
    server = startServer();
    await healthy();
    await expect(ali.getByRole("status")).toHaveText("Connected", { timeout: 20_000 });
    await expect(ali.getByRole("alert")).toContainText("seat was released");
    await expect(ali.getByRole("button", { name: "Create 2-player room" })).toBeEnabled();
  } finally {
    stop("SIGKILL");
  }
});
