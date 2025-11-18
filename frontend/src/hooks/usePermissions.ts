// NG-HEADER: Nombre de archivo: usePermissions.ts
// NG-HEADER: Ubicación: frontend/src/hooks/usePermissions.ts
// NG-HEADER: Descripción: Hook para verificar permisos de usuario según roles
// NG-HEADER: Lineamientos: Ver AGENTS.md

import { useAuth } from '../auth/AuthContext'
import type { Role } from '../auth/AuthContext'

/**
 * Hook para verificar permisos del usuario actual
 * 
 * Proporciona funciones helper para verificar si el usuario tiene
 * permisos para realizar acciones específicas según su rol.
 */
export function usePermissions() {
  const { state } = useAuth()
  const { role } = state

  /**
   * Verifica si el usuario tiene uno de los roles permitidos
   * @param allowedRoles - Array de roles permitidos
   * @returns true si el usuario tiene alguno de los roles
   */
  const hasRole = (allowedRoles: Role[]): boolean => {
    return allowedRoles.includes(role)
  }

  /**
   * Verifica si el usuario es administrador
   */
  const isAdmin = (): boolean => {
    return role === 'admin'
  }

  /**
   * Verifica si el usuario es colaborador o admin
   */
  const isCollaboratorOrAdmin = (): boolean => {
    return role === 'admin' || role === 'colaborador'
  }

  /**
   * Verifica si el usuario puede editar precios del módulo Mercado
   */
  const canEditMarketPrices = (): boolean => {
    return isCollaboratorOrAdmin()
  }

  /**
   * Verifica si el usuario puede agregar/eliminar fuentes de mercado
   */
  const canManageMarketSources = (): boolean => {
    return isCollaboratorOrAdmin()
  }

  /**
   * Verifica si el usuario puede forzar scraping de precios
   */
  const canRefreshMarketPrices = (): boolean => {
    return isCollaboratorOrAdmin()
  }

  /**
   * Verifica si el usuario puede usar descubrimiento automático de fuentes
   */
  const canDiscoverMarketSources = (): boolean => {
    return isCollaboratorOrAdmin()
  }

  /**
   * Verifica si el usuario puede ver el módulo Mercado
   */
  const canViewMarket = (): boolean => {
    return isCollaboratorOrAdmin()
  }

  /**
   * Verifica si el usuario puede editar productos
   */
  const canEditProducts = (): boolean => {
    return isCollaboratorOrAdmin()
  }

  /**
   * Verifica si el usuario puede gestionar clientes
   */
  const canManageCustomers = (): boolean => {
    return isCollaboratorOrAdmin()
  }

  /**
   * Verifica si el usuario puede gestionar ventas
   */
  const canManageSales = (): boolean => {
    return isCollaboratorOrAdmin()
  }

  /**
   * Verifica si el usuario puede gestionar compras
   */
  const canManagePurchases = (): boolean => {
    return isCollaboratorOrAdmin()
  }

  return {
    role,
    hasRole,
    isAdmin,
    isCollaboratorOrAdmin,
    // Permisos específicos de Mercado
    canEditMarketPrices,
    canManageMarketSources,
    canRefreshMarketPrices,
    canDiscoverMarketSources,
    canViewMarket,
    // Permisos generales
    canEditProducts,
    canManageCustomers,
    canManageSales,
    canManagePurchases,
  }
}
