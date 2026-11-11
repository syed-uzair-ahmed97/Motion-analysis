import { writeFile } from "node:fs/promises";
import { chromium } from "file:///C:/Users/HAIER/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs";

const baseURL = "http://127.0.0.1:8765";
const meshPath = "C:/Users/HAIER/Documents/Capyteine_Motion_analysis/meshes/demo_barge.obj";
const evidenceDir = "C:/Users/HAIER/.codex/visualizations/2026/08/04/019fcdef-7c09-7cc1-8ed8-28c9207b219a";
const reportPath = `${evidenceDir}/dashboard-qa.json`;
const messages = [];
const checks = {};

const browser = await chromium.launch({
  executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe",
  headless: true,
});

try {
  const context = await browser.newContext({ viewport: { width: 1536, height: 1024 }, deviceScaleFactor: 1 });
  const page = await context.newPage();
  page.on("console", (message) => {
    if (["error", "warning"].includes(message.type())) messages.push(`${message.type()}: ${message.text()}`);
  });
  page.on("pageerror", (error) => messages.push(`pageerror: ${error.message}`));

  await page.goto(baseURL, { waitUntil: "networkidle" });
  checks.title = await page.title();
  checks.healthVersion = (await page.getByText(/Capytaine 2\.3\.1/).first().textContent())?.trim();
  checks.initialMissingMesh = await page.getByText("OBJ mesh missing").isVisible();

  await page.setInputFiles('input[type="file"]', meshPath);
  await page.getByText("demo_barge.obj", { exact: true }).first().waitFor();
  checks.upload = await page.getByText("demo_barge.obj", { exact: true }).first().isVisible();
  await page.screenshot({ path: `${evidenceDir}/dashboard-hull.png` });

  await page.getByRole("button", { name: /Continue to vessel/i }).click();
  await page.getByRole("heading", { name: "Vessel" }).waitFor();
  checks.rotationInputCount = await page.locator('input[aria-label*="rotation" i]').count();
  checks.cgFields = await page.locator('input[aria-label^="Centre of gravity"]').count();

  await page.getByRole("button", { name: /Continue to environment/i }).click();
  await page.getByRole("button", { name: /Continue to waves/i }).click();
  await page.getByLabel("Minimum wave period").fill("2");
  await page.getByLabel("Maximum wave period").fill("6");
  await page.getByLabel("Number of wave periods").fill("3");
  await page.getByLabel("Wave headings").fill("0, 90");
  for (const dof of ["Surge", "Sway", "Pitch", "Yaw"]) {
    await page.getByRole("button", { name: dof, exact: true }).click();
  }
  await page.getByRole("button", { name: /Continue to damping/i }).click();

  checks.dampingExplanation = await page.getByText(/independently for every active DOF/i).isVisible();
  checks.heaveUnits = await page.getByText("N·s/m", { exact: true }).first().isVisible();
  checks.rollUnits = await page.getByText("N·m·s/rad", { exact: true }).first().isVisible();
  await page.getByLabel("Heave linear damping").fill("50");
  await page.getByLabel("Roll linear damping").fill("1200");
  checks.heaveDamping = await page.getByLabel("Heave linear damping").inputValue();
  checks.rollDamping = await page.getByLabel("Roll linear damping").inputValue();
  await page.screenshot({ path: `${evidenceDir}/dashboard-damping.png` });

  await page.getByRole("button", { name: /Continue to review/i }).click();
  checks.reviewCgReference = await page.getByText("Centre of gravity", { exact: true }).last().isVisible();
  checks.reviewDofs = await page.getByText("Heave, Roll", { exact: true }).isVisible();

  const createdResponse = page.waitForResponse((response) => response.url().endsWith("/api/analysis") && response.request().method() === "POST");
  await page.getByRole("button", { name: "Run analysis" }).click();
  const created = await (await createdResponse).json();
  checks.jobId = created.job_id;

  let finalState = created;
  const deadline = Date.now() + 300_000;
  while (["queued", "running"].includes(finalState.status) && Date.now() < deadline) {
    await page.waitForTimeout(1500);
    const response = await page.request.get(`${baseURL}/api/analysis/${created.job_id}`);
    finalState = await response.json();
  }
  checks.jobStatus = finalState.status;
  checks.outputNames = (finalState.outputs || []).map((item) => item.name);
  if (finalState.status !== "completed") {
    throw new Error(`Solver status ${finalState.status}: ${finalState.error || finalState.message || "unknown error"}`);
  }

  await page.getByText("Analysis complete", { exact: true }).waitFor({ timeout: 15_000 });
  await page.getByAltText("Response Amplitude Operator magnitude plot").waitFor({ state: "visible" });
  await page.waitForFunction(() => {
    const image = document.querySelector('img[alt="Response Amplitude Operator magnitude plot"]');
    return image?.complete && image.naturalWidth > 0;
  });
  checks.raoMagnitudeLoaded = true;
  checks.downloadCount = await page.locator(".outputs-list a[download]").count();
  await page.screenshot({ path: `${evidenceDir}/dashboard-results.png` });

  await page.getByRole("tab", { name: "RAO phase" }).click();
  await page.getByAltText("Response Amplitude Operator phase plot").waitFor({ state: "visible" });
  await page.waitForFunction(() => {
    const image = document.querySelector('img[alt="Response Amplitude Operator phase plot"]');
    return image?.complete && image.naturalWidth > 0;
  });
  checks.raoPhaseLoaded = true;

  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: `${evidenceDir}/dashboard-mobile.png` });
  checks.mobileHorizontalOverflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  checks.consoleMessages = messages;
  await writeFile(reportPath, JSON.stringify(checks, null, 2), "utf8");
  process.stdout.write(`${JSON.stringify(checks, null, 2)}\n`);
} finally {
  await browser.close();
}
