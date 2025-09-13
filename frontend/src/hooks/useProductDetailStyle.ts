// NG-HEADER: Nombre de archivo: useProductDetailStyle.ts
// NG-HEADER: Ubicación: frontend/src/hooks/useProductDetailStyle.ts
// NG-HEADER: Descripción: Hook para cargar y persistir preferencia de estilo de ficha de producto.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { useEffect, useState, useCallback } from 'react'
import { getProductDetailStylePref, putProductDetailStylePref, ProductDetailStyle } from '../services/productsEx'

interface UseProductDetailStyle {
  style: ProductDetailStyle
  loading: boolean
  setStyle: (s: ProductDetailStyle) => Promise<void>
}

const LOCAL_KEY = 'ng_product_detail_style'

export function useProductDetailStyle(): UseProductDetailStyle {
  const [style, setStyleState] = useState<ProductDetailStyle>('default')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let mounted = true
    ;(async () => {
      try {
        const pref = await getProductDetailStylePref()
        if (pref?.style) {
          if (mounted) setStyleState(pref.style)
          return
        }
      } catch {
        // ignore
      }
      try {
        const local = localStorage.getItem(LOCAL_KEY) as ProductDetailStyle | null
        if (local === 'default' || local === 'minimalDark') setStyleState(local)
      } catch {}
      if (mounted) setLoading(false)
    })()
    return () => { mounted = false }
  }, [])

  const setStyle = useCallback(async (s: ProductDetailStyle) => {
    setStyleState(s)
    try { await putProductDetailStylePref(s) } catch {}
    try { localStorage.setItem(LOCAL_KEY, s) } catch {}
  }, [])

  return { style, loading, setStyle }
}
