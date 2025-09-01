// NG-HEADER: Nombre de archivo: ProtectedRoute.tsx
// NG-HEADER: Ubicación: frontend/src/auth/ProtectedRoute.tsx
// NG-HEADER: Descripción: Pendiente de descripción
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { Navigate } from 'react-router-dom'
import { Role, useAuth } from './AuthContext'

interface Props {
  roles?: Role[]
  children: React.ReactElement
}

export default function ProtectedRoute({ roles, children }: Props) {
  const { state } = useAuth()

  // Si la ruta permite 'guest', no exigimos autenticación previa; se muestra
  // el contenido con visibilidad mínima cuando el rol sea 'guest'.
  if (roles && roles.includes('guest' as Role)) {
    if (state.role === 'guest') return children
    // Para otros roles, sí requerimos autenticación
    if (!state.isAuthenticated) return <Navigate to="/login" replace />
    return roles.includes(state.role) ? children : <div className="panel p-4">403 - Acceso denegado</div>
  }

  // Rutas que no permiten 'guest': requieren autenticación
  if (!state.isAuthenticated) return <Navigate to="/login" replace />
  if (roles && !roles.includes(state.role)) return <div className="panel p-4">403 - Acceso denegado</div>
  return children
}
