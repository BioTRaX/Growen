import { Navigate } from 'react-router-dom'
import { Role, useAuth } from './AuthContext'

interface Props {
  roles?: Role[]
  children: React.ReactElement
}

export default function ProtectedRoute({ roles, children }: Props) {
  const { state } = useAuth()
  if (!state.isAuthenticated) {
    return <Navigate to="/login" replace />
  }
  if (roles && !roles.includes(state.role)) {
    return <div className="panel p-4">403 - Acceso denegado</div>
  }
  return children
}
