import { defineConfig, devices } from "@playwright/test";
import { resolve } from "node:path";
export default defineConfig({testDir:"./tests/browser",fullyParallel:false,workers:1,
  use:{baseURL:"http://127.0.0.1:3100",trace:"retain-on-failure"},
  projects:[{name:"desktop",use:{...devices["Desktop Chrome"],channel:"chrome"}},
    {name:"mobile",use:{...devices["iPhone 13"],defaultBrowserType:"chromium",channel:"chrome"}}],
  timeout:60000,expect:{timeout:15000},
  webServer:[{command:'".venv/Scripts/python.exe" tests/support/integration_server.py',cwd:resolve(__dirname,".."),url:"http://127.0.0.1:8100/api/v1/health",reuseExistingServer:false,timeout:60000},
    {command:"npm run start -- --port 3100",url:"http://127.0.0.1:3100",reuseExistingServer:false,timeout:60000}]
});
