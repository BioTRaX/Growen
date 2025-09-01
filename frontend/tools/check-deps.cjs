#!/usr/bin/env node
/* Simple Node doctor: checks core deps and optionally auto-installs. */
const { execSync, spawnSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

function log(msg) { console.log(`[doctor-node] ${msg}`); }

const root = path.resolve(__dirname, '..');
const pkgPath = path.join(root, 'package.json');
if (!fs.existsSync(pkgPath)) {
  log('package.json not found');
  process.exit(1);
}
const pkg = JSON.parse(fs.readFileSync(pkgPath, 'utf-8'));

const mustDeps = ['react', 'react-dom', 'vite'];
const missing = mustDeps.filter((d) => !((pkg.dependencies && pkg.dependencies[d]) || (pkg.devDependencies && pkg.devDependencies[d])));
if (missing.length) {
  log(`Missing deps in package.json: ${missing.join(', ')}`);
}

// npm ls --depth=0 to detect missing/invalid
let lsOk = true;
try {
  const out = execSync('npm ls --depth=0', { cwd: root, stdio: 'pipe' }).toString();
  if (/missing/i.test(out) || /invalid/i.test(out)) {
    lsOk = false;
    log('npm ls reports missing/invalid packages');
  }
} catch (e) {
  lsOk = false;
  log('npm ls failed (likely missing install)');
}

if ((!lsOk || missing.length) && process.env.ALLOW_AUTO_NPM_INSTALL === 'true') {
  log('Attempting npm ci ...');
  const res = spawnSync(process.platform === 'win32' ? 'npm.cmd' : 'npm', ['ci'], { cwd: root, stdio: 'inherit' });
  if (res.status !== 0) {
    log('npm ci failed');
    process.exit(2);
  }
  log('npm ci complete');
  process.exit(0);
}

if (!lsOk || missing.length) {
  log('Dependencies not healthy. Set ALLOW_AUTO_NPM_INSTALL=true to auto-fix.');
  process.exit(1);
}

// Optional TS quick check
try {
  const tsc = spawnSync(process.platform === 'win32' ? 'npx.cmd' : 'npx', ['tsc', '--noEmit'], { cwd: root, stdio: 'inherit' });
  if (tsc.status !== 0) {
    process.exit(3);
  }
} catch (_) {}

log('OK');
process.exit(0);

