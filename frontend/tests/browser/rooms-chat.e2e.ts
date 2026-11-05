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

const members = (page: Page) => page.locator(".members li");
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

test("a second tab with the same session is rejected", async ({ browser }) => {
  const first = await newPlayer(browser, "Ali");
  const second = await first.context().newPage();
  await second.goto("/");
  await second.getByLabel("Nickname").fill("Ali");
  await second.getByRole("button", { name: "Continue" }).click();
  await expect(second.getByRole("alert")).toContainText("open in another tab");
  await expect(first.getByRole("status")).toHaveText("Connected");
});

test("stopping the server shows offline and blocks chat", async ({ browser }) => {
  const port = 8766;
  const origin = `http://localhost:${port}`;
  const server = spawn("uv", ["run", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", String(port)], {
    cwd: fileURLToPath(new URL("../../../backend", import.meta.url)),
    env: { ...process.env, APP_MODE: "development", ALLOWED_ORIGINS: origin },
    stdio: "ignore",
  });
  try {
    await expect
      .poll(async () => (await fetch(`${origin}/api/health`).catch(() => null))?.status ?? 0, { timeout: 15_000 })
      .toBe(200);

    const ali = await newPlayer(browser, "Ali", origin);
    await createRoom(ali);

    server.kill("SIGTERM");
    await expect(ali.getByRole("status")).toHaveText("Offline");
    await expect(ali.getByRole("alert")).toContainText("reconnect and rejoin");
    await expect(ali.getByPlaceholder("Message")).toBeDisabled();
    await expect(ali.getByRole("button", { name: "Send" })).toBeDisabled();
    await expect(ali.getByRole("button", { name: "Reconnect" })).toBeVisible();
  } finally {
    server.kill("SIGKILL");
  }
});
