// NG-HEADER: Nombre de archivo: check-deps.js
// NG-HEADER: Ubicación: frontend/tools/check-deps.js
// NG-HEADER: Descripción: Pendiente de descripción
// NG-HEADER: Lineamientos: Ver AGENTS.md
/* Simple dependency checker for Growen frontend */
const { execSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

function main() {
  const root = path.resolve(__dirname, '..');
  const pkgPath = path.join(root, 'package.json');
  if (!fs.existsSync(pkgPath)) {
    console.error('package.json not found');
    process.exit(1);
  }
  const pkg = JSON.parse(fs.readFileSync(pkgPath, 'utf-8'));
  const critical = ['react', 'react-dom', 'vite', 'axios'];
  const deps = Object.assign({}, pkg.dependencies || {}, pkg.devDependencies || {});
  const missing = critical.filter((d) => !(d in deps));
  if (missing.length) {
    console.error('Missing critical deps in package.json:', missing);
    process.exit(1);
  }
  try {
    execSync('npm ls --depth=0', { stdio: 'ignore', cwd: root });
  } catch (e) {
    if (String(process.env.ALLOW_AUTO_NPM_INSTALL).toLowerCase() === 'true') {
      console.log('Running npm ci to fix dependencies...');
      execSync('npm ci', { stdio: 'inherit', cwd: root });
    } else {
      console.error('Dependency tree has issues. Set ALLOW_AUTO_NPM_INSTALL=true or run npm ci');
      process.exit(2);
    }
  }
}

main();
