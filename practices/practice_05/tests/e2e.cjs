/* Real browser integration plus clearly labelled controlled UI failure cases. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { spawn } = require("node:child_process");
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");

const project = path.resolve(__dirname, "..");
const evidence = path.join(project, "evidence");
const screenshots = path.join(evidence, "screenshots");
const python = process.env.PRACTICE05_PYTHON || (process.platform === "win32" ? "python" : "python3");
const report = { status: "running", scenarios: [], browser: null };
fs.mkdirSync(screenshots, { recursive: true });

async function run() {
  let browser;
  let page;
  let stderr = "";
  const server = spawn(python, ["-u", "-m", "app.server", "--demo", "--port", "0"], {
    cwd: project,
    windowsHide: true,
    stdio: ["ignore", "pipe", "pipe"],
    env: { ...process.env, PYTHONUTF8: "1" },
  });
  server.stderr.on("data", (data) => { stderr += data; });
  try {
    const baseURL = await new Promise((resolve, reject) => {
      let text = "";
      const timer = setTimeout(() => reject(new Error(`Server startup timed out: ${stderr}`)), 15000);
      server.on("error", (error) => { clearTimeout(timer); reject(error); });
      server.once("exit", (code) => {
        clearTimeout(timer);
        reject(new Error(`Server exited ${code}: ${stderr}`));
      });
      server.stdout.on("data", (data) => {
        text += data;
        const match = text.match(/http:\/\/127\.0\.0\.1:\d+/);
        if (match) { clearTimeout(timer); resolve(match[0]); }
      });
    });
    const options = { headless: true };
    if (process.env.PRACTICE05_BROWSER_CHANNEL) options.channel = process.env.PRACTICE05_BROWSER_CHANNEL;
    browser = process.env.PRACTICE05_CDP_URL
      ? await chromium.connectOverCDP(process.env.PRACTICE05_CDP_URL)
      : await chromium.launch(options);
    report.browser = browser.version();
    page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    page.setDefaultTimeout(8000);

    const screenshot = async (name) => {
      // Explicit clip avoids Edge CDP reporting content width minus a scrollbar.
      const size = await page.evaluate(() => ({ width: window.innerWidth, height: document.documentElement.scrollHeight }));
      await page.screenshot({ path: path.join(screenshots, name), clip: { x: 0, y: 0, ...size }, captureBeyondViewport: true });
    };

    const names = () => page.locator("#results > li").evaluateAll(
      (items) => items.map((item) => item.dataset.name || item.textContent.trim()),
    );
    const expectNames = async (expected) => {
      await page.waitForFunction((wanted) => {
        const actual = Array.from(document.querySelectorAll("#results > li"),
          (item) => item.dataset.name || item.textContent.trim());
        return JSON.stringify(actual) === JSON.stringify(wanted);
      }, expected);
      assert.deepEqual(await names(), expected);
    };
    const search = async (query, enter = false) => {
      await page.locator("#search-input").fill(query);
      const response = page.waitForResponse((r) => new URL(r.url()).pathname === "/api/subscribers");
      if (enter) await page.locator("#search-input").press("Enter");
      else await page.locator("#search-form button[type=submit]").click();
      return response;
    };
    const scenario = async (name, kind, fn) => {
      const started = Date.now();
      try {
        const details = await fn();
        report.scenarios.push({ name, kind, status: "passed", duration_ms: Date.now() - started, ...details });
        console.log(`PASS ${name}`);
      } catch (error) {
        report.scenarios.push({ name, kind, status: "failed", error: error.message });
        throw error;
      }
    };

    await scenario("Initial list through real API", "end-to-end", async () => {
      await page.goto(baseURL);
      await expectNames(["Alice", "Bob", "Анна", "Борис"]);
      assert.match(await page.locator("#result-count").innerText(), /4/);
      await screenshot("desktop.png");
      return { expected: "Four sorted demo subscribers", actual: await names() };
    });
    await scenario("Latin search and server-side trim", "end-to-end", async () => {
      const response = await search("  ALI  ");
      assert.equal(response.status(), 200);
      assert.deepEqual(await response.json(), { query: "ALI", items: ["Alice"], total: 1 });
      await expectNames(["Alice"]);
    });
    await scenario("Cyrillic search using Enter", "end-to-end", async () => {
      assert.equal((await search("АН", true)).status(), 200);
      await expectNames(["Анна"]);
    });
    await scenario("No matches is an empty state", "end-to-end", async () => {
      assert.equal((await search("not-a-subscriber")).status(), 200);
      await expectNames([]);
      await page.getByText("Ничего не найдено", { exact: false }).waitFor();
    });
    await scenario("Reset restores all and input focus", "end-to-end", async () => {
      const response = page.waitForResponse((r) => new URL(r.url()).pathname === "/api/subscribers");
      await page.locator("#reset-button").click();
      assert.equal((await response).status(), 200);
      await expectNames(["Alice", "Bob", "Анна", "Борис"]);
      assert.equal(await page.locator("#search-input").inputValue(), "");
      assert.equal(await page.locator("#search-input").evaluate((el) => el === document.activeElement), true);
    });
    await scenario("Unicode boundary: 100 accepted, 101 rejected", "end-to-end", async () => {
      assert.equal((await search("😀".repeat(100))).status(), 200);
      await expectNames([]);
      const response = await search("😀".repeat(101));
      assert.equal(response.status(), 400);
      assert.equal((await response.json()).error.code, "query_too_long");
      await page.locator("#retry-button").waitFor({ state: "visible" });
      assert.match(await page.locator("body").innerText(), /100/);
      await screenshot("query-error.png");
    });
    await scenario("Network failure and retry of last submitted query", "controlled-ui-failure", async () => {
      const fail = (route) => route.abort("failed");
      await page.route("**/api/subscribers**", fail);
      await page.locator("#search-input").fill("ALI");
      await page.locator("#search-form button[type=submit]").click();
      await page.locator("#retry-button").waitFor({ state: "visible" });
      await page.unroute("**/api/subscribers**", fail);
      await page.locator("#search-input").fill("Бор");
      const response = page.waitForResponse((r) => new URL(r.url()).pathname === "/api/subscribers");
      await page.locator("#retry-button").click();
      assert.equal(new URL((await response).url()).searchParams.get("q"), "ALI");
      await expectNames(["Alice"]);
    });
    await scenario("Malformed success response is an error, retry recovers", "controlled-ui-failure", async () => {
      const invalid = (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ items: "wrong", query: "ali", total: 1 }) });
      await page.route("**/api/subscribers**", invalid);
      await search("ali");
      await page.locator("#retry-button").waitFor({ state: "visible" });
      await page.unroute("**/api/subscribers**", invalid);
      await page.locator("#retry-button").click();
      await expectNames(["Alice"]);
    });
    await scenario("Older response cannot replace newer search", "controlled-ui-race", async () => {
      const delayed = async (route) => {
        if (new URL(route.request().url()).searchParams.get("q") === "Alice") {
          await new Promise((resolve) => setTimeout(resolve, 350));
        }
        try { await route.continue(); } catch (error) {
          if (!/abort|cancel|closed|handled/i.test(error.message)) throw error;
        }
      };
      await page.route("**/api/subscribers**", delayed);
      await page.locator("#search-input").fill("Alice");
      await page.locator("#search-form button[type=submit]").click();
      await search("Bob");
      await expectNames(["Bob"]);
      await page.waitForTimeout(500);
      await expectNames(["Bob"]);
      await page.unroute("**/api/subscribers**", delayed);
    });
    await scenario("API strings render as text", "controlled-ui-input", async () => {
      const unsafeName = '<img src=x onerror="window.__searchXss = true">';
      const unsafe = (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ query: "unsafe", items: [unsafeName], total: 1 }) });
      await page.route("**/api/subscribers**", unsafe);
      await search("unsafe");
      await expectNames([unsafeName]);
      assert.equal(await page.locator("#results img").count(), 0);
      assert.equal(await page.evaluate(() => window.__searchXss === true), false);
      await page.unroute("**/api/subscribers**", unsafe);
    });
    await scenario("Mobile layout has no horizontal overflow", "browser-layout", async () => {
      await page.setViewportSize({ width: 390, height: 844 });
      const response = page.waitForResponse((r) => new URL(r.url()).pathname === "/api/subscribers");
      await page.locator("#reset-button").click();
      await response;
      await expectNames(["Alice", "Bob", "Анна", "Борис"]);
      const layout = await page.evaluate(() => ({ scrollWidth: document.documentElement.scrollWidth, clientWidth: document.documentElement.clientWidth, viewportWidth: window.innerWidth }));
      assert.equal(layout.scrollWidth <= layout.clientWidth, true);
      await screenshot("mobile.png");
      return { layout };
    });
    assert.deepEqual(errors, [], "Uncaught browser errors");
    report.status = "passed";
  } catch (error) {
    report.status = "failed";
    report.error = error.stack;
    if (page) await page.screenshot({ path: path.join(screenshots, "failure.png"), fullPage: true }).catch(() => {});
    throw error;
  } finally {
    fs.writeFileSync(path.join(evidence, "e2e.json"), JSON.stringify(report, null, 2));
    if (browser) await browser.close();
    server.kill();
  }
}

run().catch((error) => { console.error(error); process.exitCode = 1; });
