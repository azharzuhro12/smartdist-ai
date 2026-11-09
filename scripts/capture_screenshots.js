/**
 * Automated Screenshot Capture for SmartDist AI Portfolio.
 * Uses puppeteer-core with system Google Chrome.
 * Captures 6 high-resolution 1440x1000 desktop screenshots from live running services.
 */

const puppeteer = require('puppeteer-core');
const path = require('path');
const fs = require('fs');

const BASE_URL = 'http://localhost:3030';
const VIEWPORT = { width: 1440, height: 1000, deviceScaleFactor: 1 };
const CHROME_PATH = '/usr/bin/google-chrome';

const SCREENSHOT_TARGETS = [
  {
    name: 'Executive Overview',
    url: `${BASE_URL}/`,
    outputPath: path.resolve(__dirname, '../screenshots/dashboard/executive-overview.png'),
    waitSelector: 'main',
    additionalWaitMs: 3000,
  },
  {
    name: 'Sales Analytics',
    url: `${BASE_URL}/sales`,
    outputPath: path.resolve(__dirname, '../screenshots/dashboard/sales-analytics.png'),
    waitSelector: 'main',
    additionalWaitMs: 3000,
  },
  {
    name: 'Demand Forecasting',
    url: `${BASE_URL}/forecasting`,
    outputPath: path.resolve(__dirname, '../screenshots/forecasting/demand-forecasting.png'),
    waitSelector: 'main',
    additionalWaitMs: 3500,
  },
  {
    name: 'Inventory Optimization',
    url: `${BASE_URL}/inventory`,
    outputPath: path.resolve(__dirname, '../screenshots/inventory/inventory-optimization.png'),
    waitSelector: 'main',
    additionalWaitMs: 3000,
  },
  {
    name: 'Anomaly Detection',
    url: `${BASE_URL}/anomalies`,
    outputPath: path.resolve(__dirname, '../screenshots/anomalies/anomaly-detection.png'),
    waitSelector: 'main',
    additionalWaitMs: 3000,
  },
];

async function run() {
  console.log('Launching browser with Chrome at:', CHROME_PATH);
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu', '--window-size=1440,1000'],
    defaultViewport: VIEWPORT,
  });

  const page = await browser.newPage();
  await page.setViewport(VIEWPORT);

  page.on('console', (msg) => console.log('[BROWSER]', msg.type(), msg.text()));
  page.on('pageerror', (err) => console.log('[PAGE ERROR]', err.message));

  try {
    // 1. Authenticate via login page
    console.log(`Navigating to login page: ${BASE_URL}/login`);
    await page.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle2' });

    const adminPassword = process.env.INITIAL_ADMIN_PASSWORD || 'Admin@SmartDist2026!';
    console.log('Filling login credentials...');
    await page.waitForSelector('#username');
    await page.type('#username', 'admin');
    await page.type('#password', adminPassword);
    
    // Submit form
    console.log('Submitting login form...');
    await page.click('button[type="submit"]');

    // Wait for client-side routing to /
    console.log('Waiting for redirect to /...');
    await page.waitForFunction(() => window.location.pathname === '/', { timeout: 15000 });
    console.log('Logged in successfully. Current URL:', page.url());

    // 2. Capture standard dashboard pages
    for (const target of SCREENSHOT_TARGETS) {
      console.log(`Capturing: ${target.name} (${target.url})...`);
      await page.goto(target.url, { waitUntil: 'networkidle2' });
      await page.waitForSelector(target.waitSelector, { timeout: 10000 });
      if (target.additionalWaitMs) {
        await new Promise((r) => setTimeout(r, target.additionalWaitMs));
      }
      
      // Ensure target directory exists
      fs.mkdirSync(path.dirname(target.outputPath), { recursive: true });
      await page.screenshot({ path: target.outputPath, type: 'png' });
      console.log(`✓ Saved ${target.name} to ${target.outputPath}`);
    }

    // 3. Capture AI Business Assistant with an active conversation
    console.log('Capturing: AI Business Assistant...');
    const assistantUrl = `${BASE_URL}/assistant`;
    await page.goto(assistantUrl, { waitUntil: 'networkidle2' });
    await page.waitForSelector('main', { timeout: 10000 });

    // Look for suggested prompts and click the top-selling products prompt
    const promptButtons = await page.$$('button');
    let clicked = false;
    for (const btn of promptButtons) {
      const text = await page.evaluate(el => el.textContent, btn);
      if (text && text.includes('top 5 selling products')) {
        console.log('Clicking suggested prompt:', text.trim());
        await btn.click();
        clicked = true;
        break;
      }
    }

    // If suggested button was not clicked, type directly into the input
    if (!clicked) {
      console.log('Typing query into input...');
      const input = await page.$('input[placeholder*="Ask"]');
      if (input) {
        await input.type('What are the top 5 selling products by volume?');
        const sendBtn = await page.$('button[type="submit"]');
        if (sendBtn) await sendBtn.click();
      }
    }

    // Wait for the assistant response to render
    console.log('Waiting for assistant response...');
    await new Promise((r) => setTimeout(r, 6000));

    const assistantOutputPath = path.resolve(__dirname, '../screenshots/assistant/ai-business-assistant.png');
    fs.mkdirSync(path.dirname(assistantOutputPath), { recursive: true });
    await page.screenshot({ path: assistantOutputPath, type: 'png' });
    console.log(`✓ Saved AI Business Assistant to ${assistantOutputPath}`);

    console.log('\nAll 6 screenshots successfully captured!');
  } catch (err) {
    console.error('Error during screenshot capture:', err);
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
}

run();

