// NG-HEADER: Nombre de archivo: run-e2e.mjs
// NG-HEADER: Ubicación: frontend-vue/tools/run-e2e.mjs
// NG-HEADER: Descripción: Ejecuta Playwright con un Vite aislado y cierre confiable en Windows/CI.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { spawn } from 'node:child_process'
import { resolve } from 'node:path'

const vite = resolve('node_modules/vite/bin/vite.js')
const playwright = resolve('node_modules/@playwright/test/cli.js')
const server = spawn(process.execPath, [vite, '--host', '127.0.0.1', '--port', '5186', '--strictPort'], {
  stdio: 'inherit',
  windowsHide: true,
})

async function waitForServer() {
  const deadline = Date.now() + 60000
  while (Date.now() < deadline) {
    try {
      const response = await fetch('http://127.0.0.1:5186/login')
      if (response.ok) return
    } catch {}
    await new Promise((resolveWait) => setTimeout(resolveWait, 250))
  }
  throw new Error('Vite E2E no respondió en el puerto 5186')
}

function runPlaywright() {
  return new Promise((resolveRun, rejectRun) => {
    const child = spawn(process.execPath, [playwright, 'test'], { stdio: 'inherit', windowsHide: true })
    child.once('error', rejectRun)
    child.once('exit', (code) => resolveRun(code ?? 1))
  })
}

try {
  await waitForServer()
  process.exitCode = await runPlaywright()
} finally {
  server.kill('SIGTERM')
}
