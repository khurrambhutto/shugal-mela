import { expect, test, type Browser, type Page, type WebSocketRoute } from "@playwright/test";

// The game sockets each player has opened, routed through Playwright so a test can cut them.
const sockets = new Map<string, WebSocketRoute[]>();

async function newPlayer(browser: Browser, nickname: string): Promise<Page> {
  // Reduced motion skips the hop and tumble animations so the match plays quickly.
  const context = await browser.newContext({ reducedMotion: "reduce" });
  const opened: WebSocketRoute[] = [];
  sockets.set(nickname, opened);
  await context.routeWebSocket(/\/ws$/, (ws) => {
    opened.push(ws, ws.connectToServer());
  });
  const page = await context.newPage();
  await page.goto("/");
  await page.getByLabel("Nickname").fill(nickname);
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByRole("status")).toHaveText("Connected");
  return page;
}

async function seatUp(browser: Browser): Promise<[Page, Page]> {
  const ali = await newPlayer(browser, "Ali");
  const sara = await newPlayer(browser, "Sara");
  await ali.getByRole("button", { name: "Create 2-player room" }).click();
  const code = ali.locator(".room-code");
  await expect(code).toHaveText(/^[A-HJ-NP-Z2-9]{6}$/);
  await sara.getByLabel("Room code").fill((await code.textContent())!);
  await sara.getByRole("button", { name: "Join" }).click();
  return [ali, sara];
}

test("the host starts only after the other player is ready", async ({ browser }) => {
  const [ali, sara] = await seatUp(browser);
  const start = ali.getByRole("button", { name: "Start match" });
  await expect(start).toBeDisabled();
  await expect(ali.locator(".hint")).toHaveText("Waiting for Sara to get ready.");
  await expect(sara.getByRole("button", { name: "Start match" })).toBeHidden();

  await sara.getByRole("button", { name: "I'm ready" }).click();
  await expect(ali.locator('.seat[data-colour="yellow"]')).toContainText("Ready");
  await start.click();

  await expect(ali.getByRole("button", { name: "Roll" })).toBeEnabled();
  await expect(sara.getByRole("button", { name: "Roll" })).toBeHidden();
  await expect(sara.locator('.seat[data-colour="red"] .seat-note')).toHaveText("Rolling…");
  // Only the player whose turn it is gets a bright seat.
  await expect(sara.locator(".seat.is-turn")).toHaveCount(1);
  await expect(sara.locator('.seat[data-colour="red"]')).toHaveClass(/is-turn/);
  // Each player sees four tokens per colour, all in their yards.
  await expect(ali.locator(".token:not([hidden])")).toHaveCount(8);
});

test("two players play a full match to a winner", async ({ browser }) => {
  test.setTimeout(240_000);
  const [ali, sara] = await seatUp(browser);
  await sara.getByRole("button", { name: "I'm ready" }).click();
  await ali.getByRole("button", { name: "Start match" }).click();

  const banner = (page: Page) => page.locator(".banner:not(.pause)");
  let actions = 0;
  while (!(await banner(ali).isVisible())) {
    let acted = false;
    for (const page of [ali, sara]) {
      const roll = page.getByRole("button", { name: "Roll" });
      if ((await roll.isVisible()) && (await roll.isEnabled())) {
        await roll.click();
        await expect(roll).toBeHidden({ timeout: 4000 }).catch(() => {});
        acted = true;
      }
      const token = page.locator(".token.is-movable").first();
      if (await token.count()) {
        // The token may stop being movable before the click lands; the loop looks again.
        await token.click({ timeout: 1000 }).catch(() => {});
        acted = true;
      }
    }
    if (acted) actions++;
    expect(actions).toBeLessThan(2000);
  }

  const winner = await banner(ali).locator(".banner-title").textContent();
  expect(winner).toMatch(/^(You win|Sara wins)$/);
  await expect(banner(sara).locator(".banner-title")).toHaveText(winner === "You win" ? "Ali wins" : "You win");
  // Both boards agree on every token.
  const positions = (page: Page) =>
    page.locator(".token:not([hidden])").evaluateAll((els) => els.map((e) => (e as HTMLElement).style.transform));
  expect(await positions(ali)).toEqual(await positions(sara));

  // A rematch gets a fresh board.
  await sara.getByRole("button", { name: "I'm ready" }).click();
  await ali.getByRole("button", { name: "Play again" }).click();
  await expect(banner(ali)).toBeHidden();
  await expect(ali.getByRole("button", { name: "Roll" })).toBeEnabled();
});

test("a refresh mid-match returns the player to their seat", async ({ browser }) => {
  const [ali, sara] = await seatUp(browser);
  await sara.getByRole("button", { name: "I'm ready" }).click();
  await ali.getByRole("button", { name: "Start match" }).click();
  await expect(ali.getByRole("button", { name: "Roll" })).toBeEnabled();

  await ali.reload();
  // No nickname form: the page goes straight back to the same seat and turn.
  await expect(ali.getByRole("status")).toHaveText("Connected");
  await expect(ali.locator('.seat[data-colour="red"] .member-name')).toHaveText("Ali (you)");
  await expect(ali.getByRole("button", { name: "Roll" })).toBeEnabled();
  await expect(sara.locator(".seat.is-away")).toHaveCount(0);
  await expect(sara.locator(".pause")).toBeHidden();
});

test("a dropped connection pauses the match until the player returns", async ({ browser }) => {
  const [ali, sara] = await seatUp(browser);
  await sara.getByRole("button", { name: "I'm ready" }).click();
  await ali.getByRole("button", { name: "Start match" }).click();

  // Lose the network and the open socket, the way a Wi-Fi drop does.
  await sara.context().setOffline(true);
  for (const ws of sockets.get("Sara")!) await ws.close({ code: 4999 }).catch(() => {});
  await expect(ali.locator('.seat[data-colour="yellow"]')).toHaveClass(/is-away/);
  await expect(ali.locator(".pause")).toContainText(/Waiting for Sara to reconnect · \d+s/);
  await expect(ali.getByRole("button", { name: "Roll" })).toBeHidden();
  await expect(sara.getByRole("status")).toHaveText("Reconnecting…");

  await sara.context().setOffline(false);
  await expect(sara.getByRole("status")).toHaveText("Connected", { timeout: 15_000 });
  await expect(ali.locator(".pause")).toBeHidden();
  await expect(ali.getByRole("button", { name: "Roll" })).toBeEnabled();
});
