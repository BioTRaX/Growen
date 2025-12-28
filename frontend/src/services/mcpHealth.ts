// NG-HEADER: Nombre de archivo: mcpHealth.ts
// NG-HEADER: Ubicación: frontend/src/services/mcpHealth.ts
// NG-HEADER: Descripción: Servicios para monitoreo de servidores MCP (Model Context Protocol)
// NG-HEADER: Lineamientos: Ver AGENTS.md

import http from './http'

export interface MCPServerStatus {
    name: string
    label: string
    url: string
    port: number
    status: 'running' | 'stopped' | 'error'
    healthy: boolean
    lastCheck?: string
    error?: string
}

export interface MCPHealthResponse {
    servers: MCPServerStatus[]
}

/**
 * Obtiene el estado de salud de todos los servidores MCP
 */
export async function checkMCPHealth(): Promise<MCPHealthResponse> {
    const r = await http.get<MCPHealthResponse>('/admin/mcp/health')
    return r.data
}

/**
 * Inicia un contenedor MCP específico
 */
export async function startMCPServer(name: string): Promise<{ ok: boolean; message: string }> {
    const r = await http.post<{ ok: boolean; message: string }>(`/admin/mcp/${name}/start`)
    return r.data
}

/**
 * Detiene un contenedor MCP específico
 */
export async function stopMCPServer(name: string): Promise<{ ok: boolean; message: string }> {
    const r = await http.post<{ ok: boolean; message: string }>(`/admin/mcp/${name}/stop`)
    return r.data
}
