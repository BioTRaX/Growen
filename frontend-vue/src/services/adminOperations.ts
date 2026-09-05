// NG-HEADER: Nombre de archivo: adminOperations.ts
// NG-HEADER: Ubicación: frontend-vue/src/services/adminOperations.ts
// NG-HEADER: Descripción: Contratos tipados para los módulos administrativos migrados a Vue.
// NG-HEADER: Lineamientos: Ver AGENTS.md

import { http } from './http'
import { downloadBlob, openEventStream, openWebSocket } from './transports'

export interface Page<T> { items: T[]; total: number; page: number; page_size: number }
export interface DriveItem { id: number; position: number; filename: string; sku?: string | null; status: string; error_message?: string | null }
export interface DriveRun {
  id: string; parent_run_id?: string | null; status: string; total_items: number; processed_items: number
  success_count: number; error_count: number; skipped_count: number; current_filename?: string | null
  error_message?: string | null; created_at?: string | null; completed_at?: string | null; items?: DriveItem[]
}
export interface SchedulerStatus {
  running: boolean; enabled: boolean; working: boolean; start_hour: string; interval_hours: number
  next_run_time?: string | null; update_frequency_days: number; max_products_per_run: number
  prioritize_mandatory: boolean; timezone?: string; stats: Record<string, number>
}
export interface SchedulerRun { id: string; trigger: string; status: string; products_enqueued: number; sources_total: number; duration_seconds?: number | null; created_at?: string; completed_at?: string; error_message?: string | null }
export interface KnowledgeFile { filename: string; path: string; size_bytes: number; extension: string; indexed: boolean; source_id?: number | null; needs_reindex?: boolean; chunks_count?: number }
export interface KnowledgeTask { id: string; type: string; target: string; status: string; progress: number; error?: string | null; started_at?: string | null; completed_at?: string | null }
export interface KnowledgeStatus { total_sources: number; total_chunks: number; total_tokens_estimated: number; files_in_folder: number; files_pending: number; files_need_reindex: number; tasks_running: number }
export interface KnowledgeSource { id: number; filename: string; chunks_count: number; role_scope: string[]; channel_scope: string[]; visibility: 'public'|'supplier'|'internal'; status: 'active'|'stale'|'disabled'; content_version: number; expires_at?: string|null }
export interface RagResult { content: string; source: string; similarity: number; chunk_index: number; source_id: number }
export interface CatalogSummary { run_id: string; generated_at: string; file: string; size: number; count: number; duration_ms: number; status?: string; error?: string | null }
export interface CatalogLog { ts?: string; step?: string; [key: string]: unknown }
export interface ChatSession {
  session_id: string; user_identifier: string; status: string; channel: string; tags?: Record<string, unknown> | null
  admin_notes?: string | null; assigned_user_id?: number | null; detected_intent?: string | null; sentiment?: string | null
  classification_confidence?: number | null; last_message_at?: string | null; message_count?: number
  classification_model?: string | null; problem_signals?: string[] | null
}
export interface ChatMessage { id: number; role: string; content: string; created_at: string; meta?: Record<string, unknown> | null }
export interface ChatTrace { correlation_id: string; account_role: string; effective_role: string; channel: string; latency_ms?: number | null; citation_count: number; tools: Array<{ name: string; status: string; duration_ms?: number | null }> }
export interface ChatDetail { session: ChatSession; messages: ChatMessage[]; trace?: ChatTrace | null }
export interface ChatStats { total_sessions: number; total_messages: number; sessions_last_7_days: number; sessions_last_30_days: number; avg_messages_per_session: number; sessions_by_status: Record<string, number> }
export interface TelegramWorkerHealth { enabled: boolean; public_bot_enabled: boolean; role_linking_enabled: boolean; transport: string; status: string; last_poll_at?: string | null; last_success_at?: string | null; backlog: number; consecutive_errors: number; duplicates: number; processed: number }
export interface ChatMetrics { runs: number; succeeded: number; failed: number; latency_ms: { p50?: number | null; p95?: number | null; p99?: number | null }; tokens: { input: number; output: number }; estimated_cost: number; rag: { used: number; with_citations: number; cache_hits: number }; tools: Record<string, number>; telegram_updates: Record<string, number>; telegram_worker: TelegramWorkerHealth; feedback: Record<string, number> }
export interface HealthSummary { status: string; details: Record<string, unknown> }
export interface ImageReview { image_id: number; product_id: number; title?: string; url?: string; status: string }
export interface ImageVersion { path: string | null; width: number | null; height: number | null; size_bytes: number | null; size_human: string; mime: string | null }
export interface ProductImage { id: number; display_url?: string | null; url?: string | null; path?: string; mime?: string | null; width?: number | null; height?: number | null; bytes?: number | null; size_human?: string; is_primary: boolean; locked: boolean; alt_text?: string | null; title_text?: string | null; checksum_sha256?: string | null; created_at?: string | null; updated_at?: string | null; versions?: Record<string, ImageVersion>; has_webp: boolean }
export interface ProductImages { product_id: number; product_name: string; canonical_sku?: string | null; images: ProductImage[]; total: number }
export interface ChatQualityMetrics { feedback: Record<string, number>; intents: Record<string, number>; sentiments: Record<string, number>; total_feedback: number }
export interface PromptVersion { id: number; prompt_key: string; version: number; status: string; content: string; reason?: string | null; metrics?: Record<string, unknown> | null; created_at?: string | null }
export interface StaffUser { id: number; name: string; role: string }

export const getDriveStatus = async () => (await http.get<{ status: string; sync_id?: string | null }>('/admin/drive-sync/status')).data
export const listDriveRuns = async (page = 1) => (await http.get<Page<DriveRun>>('/admin/drive-sync/runs', { params: { page } })).data
export const getDriveRun = async (id: string) => (await http.get<DriveRun>(`/admin/drive-sync/runs/${id}`)).data
export const startDriveRun = async (sourceFolderId?: string) => (await http.post('/admin/drive-sync/start', null, { params: { source_folder_id: sourceFolderId } })).data
export const cancelDriveRun = async (id: string) => (await http.post(`/admin/drive-sync/runs/${id}/cancel`)).data
export const retryDriveRun = async (id: string, itemIds: number[]) => (await http.post(`/admin/drive-sync/runs/${id}/retry`, { item_ids: itemIds })).data
export const openDriveEvents = (runId?: string) => openWebSocket(`/admin/drive-sync/ws${runId ? `?run_id=${encodeURIComponent(runId)}` : ''}`)

export const getSchedulerStatus = async () => (await http.get<SchedulerStatus>('/admin/scheduler/status')).data
export const listSchedulerRuns = async () => (await http.get<Page<SchedulerRun>>('/admin/scheduler/runs')).data
export const startScheduler = async () => (await http.post('/admin/scheduler/start')).data
export const stopScheduler = async () => (await http.post('/admin/scheduler/stop')).data
export const runScheduler = async (max_products: number, days_threshold: number) => (await http.post('/admin/scheduler/run-now', { max_products, days_threshold })).data
export const saveScheduler = async (payload: { start_hour: string; interval_hours: number; timezone: string; update_frequency_days: number; max_products_per_run: number; prioritize_mandatory: boolean }) => (await http.post('/admin/scheduler/config', payload)).data

export const getKnowledgeFiles = async () => (await http.get<{ files: KnowledgeFile[] }>('/admin/knowledge/files')).data.files
export const getKnowledgeStatus = async () => (await http.get<KnowledgeStatus>('/admin/knowledge/status')).data
export const getKnowledgeSources = async () => (await http.get<{ sources: KnowledgeSource[] }>('/admin/knowledge/sources')).data.sources
export const updateKnowledgeSourcePolicy = async (id: number, payload: Pick<KnowledgeSource, 'role_scope'|'channel_scope'|'visibility'|'status'|'expires_at'>) => (await http.patch(`/admin/knowledge/sources/${id}/policy`, payload)).data
export const listKnowledgeTasks = async () => (await http.get<{ tasks: KnowledgeTask[] }>('/admin/knowledge/tasks')).data.tasks
export const uploadKnowledge = async (file: File) => { const body = new FormData(); body.append('file', file); return (await http.post('/admin/knowledge/upload', body)).data }
export const indexKnowledge = async (target: string, force_reindex = false) => (await http.post('/admin/knowledge/index', { target, force_reindex })).data
export const deleteKnowledgeSource = async (id: number) => (await http.delete(`/admin/knowledge/sources/${id}`)).data
export const deleteKnowledgeFile = async (path: string) => (await http.delete(`/admin/knowledge/files/${encodeURIComponent(path)}`)).data
export const testRag = async (query: string) => (await http.post<{ results: RagResult[] }>('/api/v1/rag/search', { query, top_k: 5, min_similarity: 0.5 })).data.results

export const getImageJobStatus = async () => (await http.get<Record<string, unknown>>('/admin/image-jobs/status')).data
export const saveImageJobSettings = async (payload: Record<string, unknown>) => (await http.put('/admin/image-jobs/settings', payload)).data
export const triggerImageCrawl = async (scope: string) => (await http.post('/admin/image-jobs/trigger/crawl-missing', null, { params: { scope } })).data
export const triggerImagePurge = async () => (await http.post('/admin/image-jobs/trigger/purge')).data
export const cleanImageLogs = async () => (await http.post('/admin/image-jobs/clean-logs')).data
export const probeImageCrawler = async (title: string) => (await http.post('/admin/image-jobs/probe', null, { params: { title } })).data
export const downloadImageLogs = async () => downloadBlob('/admin/image-jobs/logs.ndjson', 'image-crawler.ndjson')
export const listImageSnapshots = async (correlationId: string) => (await http.get<{ snapshots: Array<{ name: string; size: number; mtime: number }> }>('/admin/image-jobs/snapshots', { params: { correlation_id: correlationId } })).data.snapshots
export const openImageJobEvents = () => openEventStream('/admin/image-jobs/logs/stream')
export const listImageReviews = async () => (await http.get<ImageReview[]>('/products/images/review', { params: { status: 'pending' } })).data
export const approveImage = async (id: number) => (await http.post(`/products/images/${id}/review/approve`)).data
export const rejectImage = async (id: number, note: string) => (await http.post(`/products/images/${id}/review/reject`, { note })).data
export const getProductImages = async (productId: number) => (await http.get<ProductImages>(`/products/${productId}/images`)).data
export const setPrimaryProductImage = async (productId: number, imageId: number) => (await http.post(`/products/${productId}/images/${imageId}/set-primary`)).data
export const rotateProductImage = async (productId: number, imageId: number, degrees: number) => (await http.post(`/products/${productId}/images/${imageId}/rotate`, { degrees })).data
export const cropProductImageSquare = async (productId: number, imageId: number, margin_percent: number) => (await http.post(`/products/${productId}/images/${imageId}/crop-square`, null, { params: { margin_percent } })).data
export const cropProductImageCustom = async (productId: number, imageId: number, cropData: { x: number; y: number; width: number; height: number }) => (await http.post(`/products/${productId}/images/${imageId}/crop-custom`, cropData)).data
export const deleteProductImage = async (productId: number, imageId: number) => (await http.delete(`/products/${productId}/images/${imageId}`)).data
export const getGlobalLogo = async () => (await http.get<{ exists: boolean; url: string | null; width: number | null; height: number | null }>('/admin/images/logo')).data
export const uploadGlobalLogo = async (file: File) => { const body = new FormData(); body.append('file', file); return (await http.post('/admin/images/logo/upload', body)).data }
export const processProductImage = async (productId: number, imageId: number, action: 'remove-bg' | 'watermark' | 'logo' | 'webp') => {
  const suffix = action === 'webp' ? 'generate-webp' : `process/${action}`
  const payload = action === 'watermark' ? { position: 'br', opacity: 0.18 } : action === 'logo' ? { position: 'br', scale: 20, opacity: 0.9 } : undefined
  return (await http.post(`/products/${productId}/images/${imageId}/${suffix}`, payload)).data
}

export const getCatalogStatus = async () => (await http.get<Record<string, unknown>>('/catalogs/diagnostics/status')).data
export const getCatalogSummaries = async () => (await http.get<{ items: CatalogSummary[] }>('/catalogs/diagnostics/summaries', { params: { limit: 50 } })).data.items
export const getCatalogLog = async (id: string) => (await http.get<{ items: CatalogLog[] }>(`/catalogs/diagnostics/log/${id}`)).data.items
export const unlockCatalog = async () => (await http.post('/catalogs/diagnostics/unlock')).data
export const downloadCatalogLog = async (id: string, format: 'ndjson' | 'csv') => downloadBlob(`/catalogs/diagnostics/runs/${id}/download?format=${format}`, `catalog-${id}.${format}`)

export const getTechnicalHealth = async () => (await http.get<HealthSummary>('/health/summary')).data
export const getChatStats = async () => (await http.get<ChatStats>('/admin/chats/stats')).data
export const getChatMetrics = async () => (await http.get<ChatMetrics>('/admin/chats/metrics')).data
export const listChats = async (params: Record<string, string | number | undefined>) => (await http.get<Page<ChatSession>>('/admin/chats', { params })).data
export const getChat = async (id: string) => (await http.get<ChatDetail>(`/admin/chats/${encodeURIComponent(id)}`)).data
export const updateChat = async (id: string, payload: Record<string, unknown>) => (await http.patch(`/admin/chats/${encodeURIComponent(id)}`, payload)).data
export const saveChatFeedback = async (messageId: number, payload: { rating: 'positive' | 'negative'; categories: string[]; comment?: string }) => (await http.post(`/admin/chat-quality/messages/${messageId}/feedback`, payload)).data
export const classifyChat = async (id: string) => (await http.post(`/admin/chat-quality/sessions/${encodeURIComponent(id)}/classify`)).data
export const getChatQualityMetrics = async () => (await http.get<ChatQualityMetrics>('/admin/chat-quality/metrics')).data
export const listChatStaff = async () => (await http.get<{ items: StaffUser[] }>('/admin/chat-quality/staff')).data.items
export const bulkUpdateChats = async (session_ids: string[], payload: { status?: string; assigned_user_id?: number; tags?: Record<string, boolean> }) => (await http.post('/admin/chat-quality/sessions/bulk', { session_ids, ...payload })).data
export const listPromptVersions = async () => (await http.get<{ items: PromptVersion[] }>('/admin/chat-quality/prompts')).data.items
export const createPromptCandidate = async (payload: { prompt_key: string; content?: string; reason?: string; manual: boolean }) => (await http.post<PromptVersion>('/admin/chat-quality/prompts/candidates', payload)).data
export const evaluatePrompt = async (id: number, payload: { dataset_version: string; sample_count: number; composite_score: number; safety_passed: boolean; details: Record<string, unknown> }) => (await http.post(`/admin/chat-quality/prompts/${id}/evaluate`, payload)).data
export const approvePrompt = async (id: number) => (await http.post(`/admin/chat-quality/prompts/${id}/approve`)).data
export const activatePrompt = async (id: number) => (await http.post(`/admin/chat-quality/prompts/${id}/activate`)).data
