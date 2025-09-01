import { useCallback, useEffect, useRef, useState } from 'react'
import { getProductsTablePrefs, putProductsTablePrefs, ProductsTablePrefs } from '../services/productsEx'

export function useProductsTablePrefs() {
  const [prefs, setPrefs] = useState<ProductsTablePrefs | null>(null)
  const [loading, setLoading] = useState(true)
  const saveTimer = useRef<number | null>(null)

  useEffect(() => {
    let alive = true
    getProductsTablePrefs()
      .then((p) => alive && setPrefs(p))
      .finally(() => alive && setLoading(false))
    return () => {
      alive = false
      if (saveTimer.current) window.clearTimeout(saveTimer.current)
    }
  }, [])

  const save = useCallback((next: ProductsTablePrefs) => {
    setPrefs(next)
    if (saveTimer.current) window.clearTimeout(saveTimer.current)
    saveTimer.current = window.setTimeout(() => {
      putProductsTablePrefs(next).catch(() => {})
    }, 400)
  }, [])

  const reset = useCallback(async () => {
    await putProductsTablePrefs({})
    setPrefs({})
  }, [])

  return { prefs, setPrefs: save, reset, loading }
}
