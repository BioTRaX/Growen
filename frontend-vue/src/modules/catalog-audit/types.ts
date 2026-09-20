// NG-HEADER: Nombre de archivo: types.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/catalog-audit/types.ts
// NG-HEADER: Descripción: Contratos tipados del auditor autónomo de catálogo.
// NG-HEADER: Lineamientos: Ver AGENTS.md
export type AuditRunStatus = 'queued' | 'running' | 'waiting_enrich' | 'completed' | 'completed_with_issues' | 'failed' | 'cancelled'
export type AuditItemStatus = 'pending' | 'skipped_unchanged' | 'canonical_required' | 'waiting_enrich' | 'auditing' | 'clean' | 'auto_fixed' | 'needs_review' | 'quarantined' | 'failed' | 'cancelled'

export interface CatalogAuditOptions {
  scope: 'all' | 'pending' | 'selected'
  canonical_product_ids?: number[]
  include_orphans: boolean
  mode: 'full' | 'deterministic_only'
  enrich_missing: boolean
  auto_fix: boolean
}

export interface CatalogAuditCreated { run_id: string; status: AuditRunStatus; status_url: string }
export type CatalogAuditResolutionAction = 'reaudit' | 'accept_exception' | 'classification' | 'apply_correction' | 'restore_version' | 'release_quarantine'
export interface CatalogAuditResolution {
  action: CatalogAuditResolutionAction
  note: string
  product_class?: string
  corrections?: Record<string, unknown>
  expected_content_revision?: number
  version_id?: number
}
export interface CatalogAuditItem {
  item_id: number
  canonical_product_id: number | null
  product_id: number | null
  canonical_name: string | null
  product_detail_id: number | null
  status: AuditItemStatus
  input_hash: string
  rules_version: string
  feedback_version: string
  product_class: string | null
  score: number | null
  passed: boolean | null
  findings?: { flags?: string[]; warnings?: string[]; field_issues?: Record<string, string[]> } | null
  semantic?: Record<string, unknown> | null
  corrections: Array<Record<string, unknown>>
  evidence: string[]
  enrichment_job_id?: string | null
  reused_item_id?: number | null
  resolution?: string | null
  content_revision?: number | null
  content_versions: Array<{ version_id: number; revision: number; origin: string; created_at?: string | null }>
  error?: { code: string; message?: string | null } | null
}
export interface CatalogAuditResolutionResult { item: CatalogAuditItem; new_run_id: string | null }
export interface CatalogAuditRun {
  run_id: string
  scope: CatalogAuditOptions['scope']
  mode: CatalogAuditOptions['mode']
  status: AuditRunStatus
  include_orphans: boolean
  enrich_missing: boolean
  auto_fix: boolean
  total_items: number
  processed_items: number
  clean_items: number
  issue_items: number
  cancel_requested: boolean
  items?: CatalogAuditItem[]
  created_at?: string | null
  started_at?: string | null
  completed_at?: string | null
  error?: { code: string; message?: string | null } | null
}
export interface CatalogAuditPreflight {
  ollama: { ok: boolean; code?: string | null; model: string }
  worker: { ok: boolean; code?: string | null }
  enrichment_worker: { ok: boolean; code?: string | null }
  queue: string
}
export interface CatalogAuditSummary {
  worker: {
    status: string
    ok: boolean
    pid?: number | null
    detail?: string | null
    broker_ok: boolean
    ready: number
    delayed: number
  }
  runs: {
    total: number
    active: number
    by_status: Record<string, number>
    recent: CatalogAuditRun[]
  }
  items: { by_status: Record<string, number> }
  catalog_coverage: {
    total_canonical: number
    audited: number
    pending: number
    quarantined: number
  }
}
