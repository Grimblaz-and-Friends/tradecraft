#!/bin/bash
# The probe's smoke job (#929): the steps that once needed root run as
# ci-runner under NoNewPrivileges. Chromium is installed with no --with-deps
# and no install-deps, because the setup pre-installed its system libraries.
set -euo pipefail
version=$1
mkdir -p pw
cd pw
npm init -y >/dev/null
npm install --no-audit --no-fund "playwright@$version" >/dev/null
npx playwright install chromium
node -e "
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto('about:blank');
  console.log('chromium ' + browser.version() + ' launched headless');
  await browser.close();
})().catch((error) => { console.error(error); process.exit(1); });
"
