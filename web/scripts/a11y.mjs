// Automated accessibility check of the guide, the home and the transparency page (K18).
//
//   BASE_URL=http://localhost:3000 node scripts/a11y.mjs
//
// Needs @playwright/test and @axe-core/playwright (the CI job installs them with `npm install --no-save`,
// at fixed versions). Exit codes tell the cause apart:
//   0  no violation
//   1  accessibility VIOLATIONS (the page is wrong: fix the page)
//   2  INFRASTRUCTURE problem (browser, server or network: not a finding about the pages)
//
// Each page is checked at 320 px and 1280 px in the light theme. With A11Y_DARK=1 the (latent) dark theme tokens
// are also checked, by adding the `dark` class: the app has no theme switch yet, so that pass is informational.
import { readFileSync } from "node:fs";

const BASE = (process.env.BASE_URL ?? "http://localhost:3000").replace(/\/$/, "");
const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa", "best-practice"];
const VIEWPORTS = [
  { name: "320 px", width: 320, height: 700 },
  { name: "1280 px", width: 1280, height: 800 },
];
// The dark pass is informational: the app has no theme switch, so no user reaches it today.
const THEMES = process.env.A11Y_DARK ? ["claro", "escuro"] : ["claro"];

function infra(message, error) {
  console.error(`INFRA: ${message}${error ? ` (${error.message ?? error})` : ""}`);
  console.error("INFRA: this is not an accessibility finding. Re-run the job; if it repeats, check the browser download and the server.");
  process.exit(2);
}

let chromium;
let AxeBuilder;
try {
  ({ chromium } = await import("@playwright/test"));
  ({ default: AxeBuilder } = await import("@axe-core/playwright"));
} catch (error) {
  infra("Playwright or axe is not installed", error);
}

const guide = JSON.parse(readFileSync(new URL("../src/content/guide.json", import.meta.url), "utf8"));
const routes = ["/", "/transparencia", ...guide.pages.map((page) => page.path)];

let browser;
try {
  browser = await chromium.launch();
} catch (error) {
  infra("could not start the browser (was `npx playwright install chromium` run?)", error);
}

const violations = [];
let checked = 0;

for (const viewport of VIEWPORTS) {
  for (const theme of THEMES) {
    const context = await browser.newContext({ viewport: { width: viewport.width, height: viewport.height } });
    const page = await context.newPage();
    for (const route of routes) {
      const where = `${route} [${viewport.name}, tema ${theme}]`;
      try {
        const response = await page.goto(`${BASE}${route}`, { waitUntil: "networkidle", timeout: 45000 });
        if (!response || !response.ok()) infra(`${where}: HTTP ${response ? response.status() : "sem resposta"}`);
      } catch (error) {
        infra(`${where}: the page did not load`, error);
      }
      if (theme === "escuro") await page.evaluate(() => document.documentElement.classList.add("dark"));

      let results;
      try {
        results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
      } catch (error) {
        infra(`${where}: axe could not run`, error);
      }
      checked += 1;
      for (const violation of results.violations) {
        violations.push({
          where,
          rule: violation.id,
          impact: violation.impact,
          help: violation.help,
          nodes: violation.nodes.slice(0, 3).map((node) => node.target.join(" ")),
        });
      }
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      if (overflow > 0) {
        violations.push({ where, rule: "reflow", impact: "serious", help: `horizontal scroll of ${overflow}px`, nodes: [] });
      }
      const mains = await page.evaluate(() => document.querySelectorAll("main#conteudo").length);
      if (mains !== 1) {
        violations.push({ where, rule: "skip-target", impact: "serious", help: `${mains} elements main#conteudo (expected 1)`, nodes: [] });
      }
    }
    await context.close();
  }
}
await browser.close();

console.log(`A11Y: ${checked} page checks (${routes.length} routes x ${VIEWPORTS.length} widths x ${THEMES.length} themes).`);
if (violations.length > 0) {
  console.error(`A11Y: ${violations.length} VIOLATION(S) found (these are real findings about the pages):`);
  for (const item of violations) {
    console.error(`- ${item.where}: ${item.rule} (${item.impact}) ${item.help}${item.nodes.length ? ` -> ${item.nodes.join(" | ")}` : ""}`);
  }
  process.exit(1);
}
console.log("A11Y: no violations.");
