import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
export default defineConfig({
 plugins: [react()],
 test: { environment: 'jsdom', setupFiles: ['./src/test/setup.ts'], include: ['src/**/*.test.{ts,tsx}'],
 reporters: ['default', 'html', 'json', 'junit'],
 outputFile: { html: 'reports/qa/components.html', json: 'reports/qa/results.json', junit: 'reports/qa/junit.xml' },
 coverage: { provider: 'v8', reportsDirectory: 'reports/qa/coverage', reporter: ['text','html','json-summary'],
 include: ['src/pages/Login/Login.tsx','src/pages/Users/Users.tsx','src/pages/Analysis/Alerts.tsx','src/services/auth.ts','src/services/userAccess.ts','src/services/permissions.ts','src/services/http.ts'] }
 }
});
