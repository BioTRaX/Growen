// NG-HEADER: Nombre de archivo: shell.spec.ts
// NG-HEADER: Ubicación: frontend-vue/tests/e2e/shell.spec.ts
// NG-HEADER: Descripción: Smoke E2E de login, sesión y rutas protegidas Vue.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { expect, test } from '@playwright/test'

test('muestra login y redirige una ruta protegida sin sesión', async ({ page }) => {
  await page.route('**/api/auth/me', (route) => route.fulfill({ json: { is_authenticated: false, role: 'guest' } }))
  await page.goto('/productos')
  await expect(page).toHaveURL(/\/login\?redirect=(%2F|\/)productos/)
  await expect(page.getByRole('heading', { name: 'Growen' })).toBeVisible()
})

test('permite una sesión staff y conserva el shell', async ({ page }) => {
  await page.route('**/api/auth/me', (route) => route.fulfill({ json: {
    is_authenticated: true,
    role: 'colaborador',
    user: { id: 7, identifier: 'qa', role: 'colaborador' },
  } }))
  await page.route('**/api/purchases**', (route) => route.fulfill({ json: { items: [], total: 0, page: 1, page_size: 20 } }))
  await page.goto('/compras')
  await expect(page.getByRole('heading', { name: 'Compras', exact: true })).toBeVisible({ timeout: 15_000 })
  await expect(page.getByText('colaborador', { exact: true })).toBeVisible()
})

test('habilita Servicios y Workers a colaboradores sin exponer MCP', async ({ page }) => {
  await page.route('**/api/auth/me', (route) => route.fulfill({ json: {
    is_authenticated: true,
    role: 'colaborador',
    user: { id: 8, identifier: 'ops', role: 'colaborador' },
  } }))
  await page.route('**/api/admin/services', (route) => route.fulfill({ json: { items: [
    { id: 1, name: 'dramatiq', status: 'running', auto_start: true, uptime_s: 60 },
  ] } }))
  await page.goto('/admin/servicios')
  await expect(page.getByRole('heading', { name: 'Servicios' })).toBeVisible()
  await expect(page.getByText('MCP Tools', { exact: true })).toHaveCount(0)
  await page.goto('/admin/servicios/mcp-tools')
  await expect(page).toHaveURL('/403')
})

test('muestra health MCP a administradores', async ({ page }) => {
  await page.route('**/api/auth/me', (route) => route.fulfill({ json: {
    is_authenticated: true,
    role: 'admin',
    user: { id: 1, identifier: 'admin', role: 'admin' },
  } }))
  await page.route('**/api/admin/mcp/health', (route) => route.fulfill({ json: { context: 'local', servers: [
    { name: 'mcp_products', label: 'MCP Products', url: 'http://127.0.0.1:8100/health', port: 8100, status: 'running', healthy: true, tool_count: 2 },
  ] } }))
  await page.goto('/admin/servicios/mcp-tools')
  await expect(page.getByRole('heading', { name: 'MCP Tools' })).toBeVisible()
  await expect(page.getByText('MCP Products')).toBeVisible()
})

test('reserva Usuarios y Backups al rol admin', async ({ page }) => {
  await page.route('**/api/auth/me', (route) => route.fulfill({ json: {
    is_authenticated: true, role: 'admin', user: { id: 1, identifier: 'admin', role: 'admin' },
  } }))
  await page.route('**/api/auth/users**', (route) => route.fulfill({ json: [] }))
  await page.route('**/api/suppliers/search**', (route) => route.fulfill({ json: [] }))
  await page.route('**/api/admin/backups', (route) => route.fulfill({ json: { items: [] } }))
  await page.goto('/admin/usuarios')
  await expect(page.getByRole('heading', { name: 'Usuarios' })).toBeVisible()
  await page.goto('/admin/backups')
  await expect(page.getByRole('heading', { name: 'Backups' })).toBeVisible()
})
