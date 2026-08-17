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
const runtimeTarget = resolve(root, 'generated/modules.runtime.json')
const metadataTarget = resolve(root, 'generated/build-metadata.json')
const manifest = JSON.parse(await readFile(source, 'utf8'))
const chatRuntime = process.env.CHAT_MODULE_RUNTIME || 'legacy'
if (!['legacy', 'vue'].includes(chatRuntime)) throw new Error('CHAT_MODULE_RUNTIME inválido')
const chatModule = manifest.modules.find((module) => module.id === 'chat')
if (!chatModule) throw new Error('Módulo chat ausente')
if (chatRuntime === 'vue') {
  chatModule.runtime = 'vue'
  chatModule.state = 'active'
}

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
await writeFile(runtimeTarget, `${JSON.stringify(manifest, null, 2)}\n`, 'utf8')
await writeFile(metadataTarget, `${JSON.stringify({
  sha: process.env.BUILD_SHA || 'local',
  chatRuntime,
  builtAt: process.env.BUILD_DATE || 'local',
}, null, 2)}\n`, 'utf8')
process.stdout.write(`${target}\n`)
