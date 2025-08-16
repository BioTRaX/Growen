const base = import.meta.env.VITE_API_URL as string

export async function uploadPriceList(supplierId: number, file: File): Promise<{ job_id: number; summary: any; kpis: any }> {
  const fd = new FormData()
  fd.append('file', file)
  const res = await fetch(`${base}/suppliers/${supplierId}/price-list/upload?dry_run=true`, {
    method: 'POST',
    body: fd,
    credentials: 'include',
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function getImport(jobId: number, page = 1, pageSize = 50): Promise<any> {
  const res = await fetch(`${base}/imports/${jobId}?page=${page}&page_size=${pageSize}`, {
    credentials: 'include',
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function getImportPreview(jobId: number, page = 1, pageSize = 50): Promise<any> {
  const res = await fetch(`${base}/imports/${jobId}/preview?page=${page}&page_size=${pageSize}`, {
    credentials: 'include',
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function commitImport(jobId: number): Promise<any> {
  const res = await fetch(`${base}/imports/${jobId}/commit`, {
    method: 'POST',
    credentials: 'include',
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}
