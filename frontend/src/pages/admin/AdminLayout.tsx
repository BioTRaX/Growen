import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useEffect } from 'react'
import http from '../../services/http'
import { useToast } from '../../components/ToastProvider'
import { PATHS } from '../../routes/paths'

export default function AdminLayout() {
  const nav = useNavigate()
  const loc = useLocation()
  const { push } = useToast()

  // Persist last admin tab
  useEffect(() => {
    const tab = loc.pathname
    if (tab.startsWith(PATHS.admin + '/')) {
      localStorage.setItem('lastAdminTab', tab)
    }
  }, [loc.pathname])

  // If landing on /admin without section, redirect to last or services
  useEffect(() => {
    if (loc.pathname === PATHS.admin) {
      const last = localStorage.getItem('lastAdminTab') || PATHS.adminServices
      if (last !== PATHS.admin) nav(last, { replace: true })
    }
  }, [loc.pathname, nav])

  // Notificar una vez por día si corrió el autobackup en el último arranque
  useEffect(() => {
    const key = 'notified-auto-backup'
    const today = new Date().toISOString().slice(0,10)
    const stamp = localStorage.getItem(key)
    if (stamp === today) return
    ;(async () => {
      try {
        const r = await http.get('/admin/backups/last-auto')
        const meta = r.data?.meta
        if (meta && meta.action === 'run' && meta.ok) {
          push({ kind: 'success', title: 'Backup diario', message: 'Se creó un backup automático al iniciar la app.' })
          localStorage.setItem(key, today)
        }
      } catch {}
    })()
  }, [push])

  const goBack = () => {
    // In Admin, Back should always return to Main
    nav(PATHS.home)
  }

  const crumbs = () => {
    const leaf = loc.pathname.includes('/servicios') ? 'Servicios' : loc.pathname.includes('/usuarios') ? 'Usuarios' : loc.pathname.includes('/imagenes') || loc.pathname.includes('/imagenes-productos') ? 'Imágenes de productos' : ''
    return `Inicio › Admin${leaf ? ` › ${leaf}` : ''}`
  }

  return (
    <div className="panel" style={{ padding: 12, margin: 12 }}>
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div style={{ color: 'var(--muted)', fontSize: 12 }}>{crumbs()}</div>
          <h2 style={{ marginTop: 6 }}>Admin</h2>
        </div>
        <button className="btn" onClick={goBack}>Volver</button>
      </div>
      <div className="row" style={{ gap: 8, marginTop: 8, marginBottom: 12 }}>
        <NavLink to={PATHS.adminServices} className="btn" style={({ isActive }) => ({ borderColor: isActive ? 'var(--primary)' : undefined, color: isActive ? 'var(--primary)' : undefined, textDecoration: 'none' })}>Servicios</NavLink>
        <NavLink to={PATHS.adminUsers} className="btn" style={({ isActive }) => ({ borderColor: isActive ? 'var(--primary)' : undefined, color: isActive ? 'var(--primary)' : undefined, textDecoration: 'none' })}>Usuarios</NavLink>
  <NavLink to={PATHS.adminImages} className="btn" style={({ isActive }) => ({ borderColor: isActive ? 'var(--primary)' : undefined, color: isActive ? 'var(--primary)' : undefined, textDecoration: 'none' })}>Imágenes de productos</NavLink>
  <NavLink to={PATHS.adminBackups} className="btn" style={({ isActive }) => ({ borderColor: isActive ? 'var(--primary)' : undefined, color: isActive ? 'var(--primary)' : undefined, textDecoration: 'none' })}>Backups</NavLink>
        <NavLink to={PATHS.adminCatalogDiagnostics} className="btn" style={({ isActive }) => ({ borderColor: isActive ? 'var(--primary)' : undefined, color: isActive ? 'var(--primary)' : undefined, textDecoration: 'none' })}>Catálogos (Diag)</NavLink>
      </div>
      <Outlet />
    </div>
  )
}
