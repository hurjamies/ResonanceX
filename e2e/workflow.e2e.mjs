// End-to-end user workflow through the real UI (Playwright, Chromium).
//
// Usage: BASE_URL=http://127.0.0.1:8000 AUDIO_DIR=/path/to/audio SHOT_DIR=/tmp/shots node e2e/workflow.e2e.mjs
// AUDIO_DIR must contain several analysable audio files plus "Suno Result.wav"
// (scripts/e2e.sh generates synthetic ones and starts a throwaway server).
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const BASE = process.env.BASE_URL ?? "http://127.0.0.1:8000";
const AUDIO = process.env.AUDIO_DIR;
const SHOTS = process.env.SHOT_DIR ?? "";
if (!AUDIO) throw new Error("AUDIO_DIR is required");

const library = fs.readdirSync(AUDIO).filter((f) => f.endsWith(".mp3")).map((f) => path.join(AUDIO, f));
const result = path.join(AUDIO, "Suno Result.wav");
const errors = [];
const step = (m) => console.log(`✔ ${m}`);
const shot = async (page, name) => SHOTS && (await page.screenshot({ path: path.join(SHOTS, `${name}.png`), fullPage: true }));
const api = async (p, init) => {
  const r = await fetch(BASE + p, { headers: { "Content-Type": "application/json" }, ...init });
  if (!r.ok) throw new Error(`${p}: ${r.status} ${await r.text()}`);
  return r.json();
};

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
await ctx.grantPermissions(["clipboard-read", "clipboard-write"], { origin: BASE });
const page = await ctx.newPage();
page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
page.on("pageerror", (e) => errors.push(String(e)));

// 1. Overview, empty state
await page.goto(BASE + "/");
await page.getByText("Decode what").waitFor();
await page.getByText("Tuo ensimmäiset kappaleesi").waitFor();
await shot(page, "01-overview-empty");
step("overview renders the honest empty state");

// 2. Library upload (batch) – rights confirmation is required
await page.goto(BASE + "/library");
await page.getByRole("button", { name: "Valitse tiedostot" }).waitFor();
await page.setInputFiles('input[type="file"]', library);
const submit = page.getByRole("button", { name: /analysoi/ });
if (!(await submit.isDisabled())) throw new Error("upload must require rights confirmation");
await page.getByRole("checkbox").check();
await submit.click();
await page.getByText("lisätty analyysijonoon").first().waitFor();
await page.goto(BASE + "/library");
await page.waitForFunction((n) => document.querySelectorAll("li .text-ok").length >= n, library.length, { timeout: 240_000 });
await shot(page, "02-library");
step(`uploaded and analysed ${library.length} tracks`);

// 3. Track workspace: timeline, playback, seek, marker, rating
const assets = await api("/api/assets");
const byTitle = Object.fromEntries(assets.map((a) => [a.title, a]));
const target = byTitle["Deep Current"];
await page.goto(`${BASE}/tracks/${target.id}`);
await page.getByText("Mitä musiikissa tapahtuu nyt?").waitFor();
const canvases = await page.locator("canvas").count();
if (canvases < 8) throw new Error(`expected timeline lanes, got ${canvases} canvases`);
const lane = page.locator("canvas").nth(2);
const box = await lane.boundingBox();
await page.mouse.click(box.x + box.width * 0.6, box.y + box.height / 2);
await page.waitForFunction(() => /0:4[0-9]\.\d/.test(document.body.innerText));
step("clicking the timeline seeks playback (~60 %)");
await page.getByRole("button", { name: "Kylmät väreet", exact: true }).click();
await page.getByLabel("Muistiinpano").fill("bassonousu");
await page.getByRole("button", { name: "Merkitse" }).click();
await page.getByText("bassonousu").waitFor();
step("timeline marker created");
// drag to select an interval and mark it
await lane.scrollIntoViewIfNeeded();
const box2 = await lane.boundingBox();
await page.mouse.move(box2.x + box2.width * 0.2, box2.y + box2.height / 2);
await page.mouse.down();
await page.mouse.move(box2.x + box2.width * 0.35, box2.y + box2.height / 2, { steps: 6 });
await page.mouse.up();
await page.getByRole("button", { name: "Zoomaa valintaan" }).waitFor();
await page.getByRole("button", { name: "Tunnehuippu", exact: true }).click();
await page.getByRole("button", { name: "Merkitse" }).click();
await page.waitForFunction(() => document.body.innerText.includes("Tunnehuippu ·") || document.querySelectorAll("ul li .font-mono.text-cyan").length >= 2);
step("interval marker created from drag selection");
// rate
for (const [label, v] of [["Yleinen mieltymys", 8], ["Kehollinen resonanssi", 9], ["Tunteen voimakkuus", 8], ["Uppoutuminen", 9]]) {
  const slider = page.getByLabel(label, { exact: true });
  await slider.fill(String(v));
}
await page.getByRole("tab", { name: /^Keho/ }).click();
await page.getByRole("button", { name: "Kylmät väreet / kananliha" }).click();
await page.getByRole("tab", { name: "Pohdinta" }).click();
await page.getByLabel("Mitä tämä musiikki saa minut tuntemaan?").fill("Hidas, painava aalto.");
await page.getByRole("button", { name: "Tallenna", exact: true }).click();
await page.getByText("Tallennettu", { exact: false }).first().waitFor();
await shot(page, "03-track");
step("song-level experience saved through the UI");

// Rate the rest via the API (keeps the test fast); varied, including negatives
const plan = {
  "Slow Gravity": [9, 9, 9, 8, 8], "Undertow": [7, 8, 7, 8, 6], "Ritual Pulse": [8, 7, 8, 7, 7],
  "Night Engine": [6, 4, 4, 5, 3], "Paper Sun": [5, 3, 3, 3, 2], "Glass Morning": [2, 1, 2, 2, 1], "Bright Market": [3, 2, 2, 2, 1],
};
for (const [t, [pref, body, emo, imm, sig]] of Object.entries(plan)) {
  await api(`/api/assets/${byTitle[t].id}/rating`, { method: "PUT", body: JSON.stringify({ dimensions: { preference: pref, bodily_resonance: body, emotional_intensity: emo, immersion: imm, significance: sig } }) });
}
await api(`/api/assets/${byTitle["Slow Gravity"].id}/markers`, { method: "POST", body: JSON.stringify({ start_seconds: 55, label: "chills" }) });
await api(`/api/assets/${byTitle["Undertow"].id}/markers`, { method: "POST", body: JSON.stringify({ start_seconds: 60, label: "body_reaction" }) });

// 4. Pairwise comparison through the UI
await page.goto(`${BASE}/sonic-dna/compare?a=${byTitle["Slow Gravity"].id}&b=${byTitle["Glass Morning"].id}`);
await page.getByText("Kumpi vaikuttaa sinuun voimakkaammin?").waitFor();
await page.locator("fieldset").nth(0).getByRole("button", { name: "A", exact: true }).click();
await page.locator("fieldset").nth(1).getByRole("button", { name: "A", exact: true }).click();
await page.getByRole("button", { name: "Tallenna vertailu" }).click();
await page.getByText("Tallennettu – profiili päivittyy.").waitFor();
step("pairwise comparison saved");

// 5. SonicDNA profile with grounded insights
await page.goto(BASE + "/sonic-dna");
await page.getByText("Henkilökohtainen SonicDNA").waitFor();
await page.getByText(/Havainnot \(\d+\)/).waitFor();
const nInsights = Number((await page.getByText(/Havainnot \(\d+\)/).innerText()).match(/\d+/)[0]);
if (nInsights < 1) throw new Error("expected at least one insight");
await shot(page, "04-sonicdna");
step(`SonicDNA profile shows ${nInsights} evidence-backed insights`);

// 6. Prompt Studio → three genuinely different variants
await page.goto(BASE + "/prompt-studio");
await page.getByText("Valitse lähdekappaleet").waitFor();
await page.getByLabel("Hae lähteitä").fill("Deep");
await page.locator("label", { hasText: "Deep Current" }).locator('input[type="checkbox"]').check();
await page.getByRole("button", { name: "Melankolia" }).click();
await page.getByRole("button", { name: "Luo kolme kehotetta" }).click();
await page.getByText("Style of Music").first().waitFor();
const styles = [];
for (const tab of ["A · Syvä resonanssi", "B · Tunteen voimistaminen", "C · Tuntematon alue"]) {
  await page.getByRole("tab", { name: tab }).click();
  const block = page.locator("div.rounded-lg", { has: page.getByText("Style of Music", { exact: true }) }).locator("pre");
  styles.push(await block.innerText());
}
if (new Set(styles).size !== 3) throw new Error("variants should differ: " + styles.join(" | "));
await page.getByRole("tab", { name: "A · Syvä resonanssi" }).click();
await page.getByRole("button", { name: "Kopioi kaikki" }).click();
const clip = await page.evaluate(() => navigator.clipboard.readText());
if (!clip.includes("Style of Music:")) throw new Error("copy all failed");
await shot(page, "05-prompt-studio");
step("three distinct Suno prompt packages generated; copy-all works");
// edit + save
await page.getByRole("button", { name: "Muokkaa" }).click();
await page.getByLabel("Title").fill("Raskas Aalto");
await page.getByRole("button", { name: "Tallenna muutokset" }).click();
await page.getByText("muokattu").first().waitFor();
step("prompt edited and persisted");

// 7. Import the "Suno" result and associate with the prompt
await page.getByRole("button", { name: "Tuo Suno-tulos" }).click();
await page.locator('dialog[open] input[type="file"]').setInputFiles(result);
await page.locator("dialog[open]").getByRole("checkbox").check();
await page.locator("dialog[open]").getByRole("button", { name: "Tuo ja analysoi tulos" }).click();
await page.locator("dialog[open]").getByText("lisätty analyysijonoon").waitFor({ timeout: 60_000 });
await page.keyboard.press("Escape");
await page.goto(BASE + "/experiments");
await page.getByText("1 · Tekninen vastaavuus").waitFor({ timeout: 120_000 });
await page.getByText("Kokemusta ei ole vielä arvioitu.").waitFor();
const exp = (await api("/api/experiments"))[0];
await api(`/api/assets/${exp.asset.id}/rating`, { method: "PUT", body: JSON.stringify({ dimensions: { preference: 8, bodily_resonance: 9, emotional_intensity: 8, immersion: 8, significance: 7 } }) });
await page.reload();
await page.getByText("Resonanssi", { exact: true }).waitFor();
await shot(page, "06-experiments");
step(`result imported, analysed and compared (${exp.alignment.matches}/${exp.alignment.total} targets met)`);

// 8. Persistence after reload; feedback became part of the profile
const prof = await api("/api/profile");
if (prof.counts.generated_tracks !== 1 || prof.counts.tracks_rated !== 9) throw new Error("profile did not absorb feedback");
await page.goto(BASE + "/");
await page.getByText("Viimeisimmät havainnot").waitFor();
await shot(page, "07-overview");
step(`profile v${prof.version} includes the generated track's feedback`);

// 9. Mobile
const m = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1, isMobile: true, hasTouch: true });
const mp = await m.newPage();
mp.on("pageerror", (e) => errors.push(String(e)));
await mp.goto(`${BASE}/tracks/${target.id}`);
await mp.getByText("Mitä musiikissa tapahtuu nyt?").waitFor();
const overflow = await mp.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
if (overflow > 2) throw new Error(`horizontal overflow on mobile: ${overflow}px`);
await shot(mp, "08-mobile-track");
await mp.goto(BASE + "/prompt-studio");
await mp.getByRole("button", { name: "Avaa valikko" }).click();
await mp.getByRole("link", { name: "SonicDNA" }).click();
await mp.getByText("Henkilökohtainen SonicDNA").waitFor();
step("mobile layout has no horizontal overflow and navigation works");

await browser.close();
const relevant = errors.filter((e) => !/Failed to load resource.*(404|416)/.test(e));
if (relevant.length) {
  console.error("Console errors:\n" + relevant.join("\n"));
  process.exit(1);
}
console.log("\nE2E workflow passed.");
