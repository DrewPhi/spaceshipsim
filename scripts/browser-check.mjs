import assert from 'node:assert/strict';
import { chromium } from 'playwright';

// Use installed Chrome with a fresh temporary browser profile.
const browser = await chromium.launch({ channel: 'chrome', headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  await page.setContent('<label>Message<input></label><button>Transmit</button><output></output>');
  await page.getByRole('button').evaluate(button => {
    button.addEventListener('click', () => {
      document.querySelector('output').textContent = document.querySelector('input').value;
    });
  });
  await page.getByLabel('Message').fill('Browser control verified');
  await page.getByRole('button', { name: 'Transmit' }).click();
  assert.equal(await page.locator('output').textContent(), 'Browser control verified');
  const screenshot = '/tmp/space-crew-browser-check.png';
  await page.screenshot({ path: screenshot });
  console.log(`PASS: Chrome launch, text entry, button click, DOM inspection, screenshot (${screenshot}).`);
} finally {
  await browser.close();
}
