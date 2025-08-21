import http from './http'

const base = import.meta.env.VITE_API_URL as string

export async function uploadPriceList(
  supplierId: number,
  file: File
): Promise<{ job_id: number; summary: any; kpis: any }> {
  const fd = new FormData()
  fd.append('file', file)
  const res = await http.post(
    `/suppliers/${supplierId}/price-list/upload?dry_run=true`,
    fd
  )
  return res.data
}

export async function getImportPreview(
  jobId: number,
  status: string,
  page = 1,
  pageSize = 50
): Promise<any> {
  const url = `${base}/imports/${jobId}/preview?status=${encodeURIComponent(
    status
  )}&page=${page}&page_size=${pageSize}`
  const res = await fetch(url, { credentials: 'include' })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function downloadTemplate(supplierId: number): Promise<void> {
  const url = `${base}/suppliers/${supplierId}/price-list/template`
  const res = await fetch(url, { credentials: 'include' })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const blob = await res.blob()
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `plantilla-${supplierId}.xlsx`
  document.body.appendChild(a)
  a.click()
  a.remove()
}

export async function commitImport(jobId: number): Promise<any> {
  const res = await http.post(`/imports/${jobId}/commit`)
  return res.data
}
