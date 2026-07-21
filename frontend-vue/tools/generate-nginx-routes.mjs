// NG-HEADER: Nombre de archivo: generate-nginx-routes.mjs
// NG-HEADER: Ubicación: frontend-vue/tools/generate-nginx-routes.mjs
// NG-HEADER: Descripción: Valida el manifiesto modular y genera las rutas Nginx para módulos Vue activos.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const source = resolve(root, 'config/modules.json')
const target = resolve(root, 'generated/nginx-spa-routes.conf')
const manifest = JSON.parse(await readFile(source, 'utf8'))

if (manifest.version !== 1 || !Array.isArray(manifest.modules)) throw new Error('Manifiesto frontend inválido')

const ids = new Set()
const lines = ['# Generado desde frontend-vue/config/modules.json. No editar manualmente.']
for (const module of manifest.modules) {
  if (!module.id || ids.has(module.id)) throw new Error(`ID de módulo inválido: ${module.id}`)
  ids.add(module.id)
  if (module.runtime === 'vue' && module.state !== 'active') throw new Error(`${module.id}: runtime vue requiere state active`)
  for (const alias of module.aliases ?? []) {
    const destination = module.routes[0]?.path
    if (!destination || destination.includes(':')) throw new Error(`${module.id}: alias sin destino estático`)
    lines.push(`location = ${alias} { return 308 ${destination}; }`)
  }
  if (module.runtime !== 'vue') continue
  for (const route of module.routes) {
    if (route.path === '/') {
      lines.push('location = / { try_files $uri /vue/index.html; }')
      continue
    }
    if (!route.path.includes(':')) {
      lines.push(`location = ${route.path} { try_files $uri /vue/index.html; }`)
      continue
    }
    const regex = route.path
      .replace(/:[^/]+\(\.\*\)\*/g, '.*')
      .replace(/:[^/]+/g, '[^/]+')
    lines.push(`location ~ ^${regex}/?$ { try_files $uri /vue/index.html; }`)
  }
}

await mkdir(dirname(target), { recursive: true })
await writeFile(target, `${lines.join('\n')}\n`, 'utf8')
process.stdout.write(`${target}\n`)
