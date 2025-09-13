// NG-HEADER: Nombre de archivo: CatalogDiagnosticsPage.tsx
// NG-HEADER: Ubicación: frontend/src/pages/CatalogDiagnosticsPage.tsx
// NG-HEADER: Descripción: UI de diagnóstico para generación de catálogos PDF.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { useEffect, useState, useMemo } from 'react'
import { getCatalogStatus, getCatalogSummaries, getCatalogDetailLog, CatalogSummaryItem, CatalogDetailLogLine } from '../services/catalogDiagnostics'

interface Durations { [step: string]: number }

function computeDurations(lines: CatalogDetailLogLine[]): Durations {
  const ordered = lines.filter(l => l.ts && l.step).sort((a,b)=> (a.ts! < b.ts! ? -1 : 1))
  const durs: Durations = {}
  for (let i=1;i<ordered.length;i++) {
    try {
      const prev = new Date(ordered[i-1].ts as string).getTime()
      const cur = new Date(ordered[i].ts as string).getTime()
      const delta = cur - prev
      durs[ordered[i].step as string] = (durs[ordered[i].step as string] || 0) + delta
    } catch {}
  }
  return durs
}

export default function CatalogDiagnosticsPage() {
  const [loading, setLoading] = useState(true)
  const [status, setStatus] = useState<any>(null)
  const [summaries, setSummaries] = useState<CatalogSummaryItem[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [logLines, setLogLines] = useState<CatalogDetailLogLine[] | null>(null)
  const [logLoading, setLogLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function loadAll() {
    setLoading(true)
    setError(null)
    try {
      const [st, sum] = await Promise.all([
        getCatalogStatus(),
        getCatalogSummaries(50),
      ])
      setStatus(st)
      setSummaries(sum.items)
    } catch (e:any) {
      setError(e.message || 'Error cargando diagnósticos')
    } finally {
      setLoading(false)
    }
  }

  useEffect(()=>{ loadAll() }, [])

  async function loadLog(id: string) {
    setSelectedId(id)
    setLogLoading(true)
    setError(null)
    try {
      const resp = await getCatalogDetailLog(id)
      setLogLines(resp.items)
    } catch (e:any) {
      setError(e.message || 'Error cargando log')
      setLogLines(null)
    } finally {
      setLogLoading(false)
    }
  }

  const durations = useMemo(()=> logLines ? computeDurations(logLines) : {}, [logLines])

  return (
    <div style={{padding: '16px 20px'}}>
      <h1 style={{marginTop:0}}>Diagnóstico de Catálogos</h1>
      <div style={{display:'flex', gap:24, flexWrap:'wrap'}}>
        <div style={{flex:'1 1 280px', minWidth:280, background:'#1e1e1e', border:'1px solid #333', borderRadius:8, padding:16}}>
          <h2 style={{marginTop:0,fontSize:18}}>Estado actual</h2>
          {loading ? <div>Cargando…</div> : (
            status ? (
              <ul style={{listStyle:'none', padding:0, margin:0, fontSize:14}}>
                <li><strong>Generación activa:</strong> {status.active_generation.running ? 'Sí' : 'No'}</li>
                <li><strong>Inició:</strong> {status.active_generation.started_at || '-'}</li>
                <li><strong>IDs enviados:</strong> {status.active_generation.ids}</li>
                <li><strong>Logs detallados:</strong> {status.detail_logs}</li>
                <li><strong>Resúmenes:</strong> {status.summaries}</li>
              </ul>
            ) : <div>Sin datos</div>
          )}
          <button onClick={loadAll} style={{marginTop:12}}>Refrescar</button>
          {error && <div style={{color:'#f66', marginTop:8}}>{error}</div>}
        </div>
        <div style={{flex:'2 1 420px', minWidth:360, background:'#1e1e1e', border:'1px solid #333', borderRadius:8, padding:16}}>
          <h2 style={{marginTop:0,fontSize:18}}>Últimos resúmenes</h2>
          {loading ? <div>Cargando…</div> : summaries.length === 0 ? <div>No hay resúmenes</div> : (
            <div style={{maxHeight:260, overflow:'auto'}}>
              <table style={{width:'100%', borderCollapse:'collapse', fontSize:13}}>
                <thead>
                  <tr style={{textAlign:'left'}}>
                    <th style={{borderBottom:'1px solid #333', padding:'4px 6px'}}>Generado</th>
                    <th style={{borderBottom:'1px solid #333', padding:'4px 6px'}}>Archivo</th>
                    <th style={{borderBottom:'1px solid #333', padding:'4px 6px'}}>Productos</th>
                    <th style={{borderBottom:'1px solid #333', padding:'4px 6px'}}>Duración (ms)</th>
                    <th style={{borderBottom:'1px solid #333', padding:'4px 6px'}}>Ver</th>
                  </tr>
                </thead>
                <tbody>
                  {summaries.map(s => {
                    const id = s.file.replace('catalog_','').replace('.pdf','')
                    return (
                      <tr key={s.file} style={{borderBottom:'1px solid #222'}}>
                        <td style={{padding:'4px 6px', whiteSpace:'nowrap'}}>{s.generated_at}</td>
                        <td style={{padding:'4px 6px'}}>{s.file}</td>
                        <td style={{padding:'4px 6px'}}>{s.count}</td>
                        <td style={{padding:'4px 6px'}}>{s.duration_ms}</td>
                        <td style={{padding:'4px 6px'}}>
                          <button onClick={()=>loadLog(id)} disabled={logLoading && selectedId===id}>Log</button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
        <div style={{flex:'2 1 420px', minWidth:360, background:'#1e1e1e', border:'1px solid #333', borderRadius:8, padding:16}}>
          <h2 style={{marginTop:0,fontSize:18}}>Log detallado {selectedId ? `(${selectedId})` : ''}</h2>
          {logLoading && <div>Cargando log…</div>}
          {!logLoading && !logLines && <div>Seleccioná un resumen para ver su log.</div>}
          {!logLoading && logLines && (
            <div style={{display:'flex', flexDirection:'column', gap:12}}>
              <div style={{fontSize:12, display:'flex', flexWrap:'wrap', gap:8}}>
                {Object.entries(durations).map(([step, ms]) => (
                  <span key={step} style={{background:'#222', padding:'4px 6px', borderRadius:4}}>{step}: {ms} ms</span>
                ))}
              </div>
              <div style={{maxHeight:260, overflow:'auto', fontFamily:'monospace', fontSize:12, lineHeight:1.4, background:'#141414', border:'1px solid #222', padding:8}}>
                {logLines.map((l,i)=> (
                  <div key={i} style={{borderBottom:'1px solid #1f1f1f', padding:'2px 0'}}>
                    <span style={{color:'#888'}}>{l.ts}</span> <strong style={{color:'#f0f'}}>{l.step}</strong> {JSON.stringify(Object.fromEntries(Object.entries(l).filter(([k])=> !['ts','step'].includes(k))))}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
