import {defineConfig} from '@playwright/test';
import {randomBytes} from 'node:crypto';

if (!process.env.E2E_PYTHON) throw new Error('Set E2E_PYTHON to the project interpreter.');
process.env.E2E_TEST_ONLY='1';
process.env.E2E_PASSWORD??=randomBytes(32).toString('hex');
const apiPort=Number(process.env.E2E_API_PORT||8000);
const webPort=Number(process.env.E2E_WEB_PORT||5173);
process.env.E2E_API_URL=`http://127.0.0.1:${apiPort}`;

export default defineConfig({
  testDir:'./e2e', workers:1, fullyParallel:false, retries:0,
  reporter:'list', timeout:30000,
  use:{baseURL:`http://127.0.0.1:${webPort}`, channel:'chrome', headless:true, launchOptions:{args:['--enable-unsafe-swiftshader','--use-angle=swiftshader']}, trace:'off', screenshot:'off', video:'off'},
  webServer:[
    {command:'"$E2E_PYTHON" ../scripts/e2e_server.py', url:`http://127.0.0.1:${apiPort}/api/health`, reuseExistingServer:false, timeout:30000},
    {command:`npm run dev -- --port ${webPort} --strictPort`, url:`http://127.0.0.1:${webPort}`, reuseExistingServer:false, timeout:30000},
  ],
});
