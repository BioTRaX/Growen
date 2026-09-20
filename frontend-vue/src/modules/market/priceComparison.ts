// NG-HEADER: Nombre de archivo: priceComparison.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/market/priceComparison.ts
// NG-HEADER: Descripción: Presentación accesible de las bandas venta contra promedio de Mercado.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import type { PricePosition } from './types'

export interface PricePositionPresentation { position: PricePosition; label: string; icon: string; color: string }
export const PRICE_PRESENTATION: Record<PricePosition, PricePositionPresentation> = {
  much_cheaper: { position: 'much_cheaper', label: 'Mucho más barato', icon: 'mdi-arrow-down-bold', color: 'marketMuchCheaper' },
  very_cheaper: { position: 'very_cheaper', label: 'Muy barato', icon: 'mdi-arrow-down-bold', color: 'marketVeryCheaper' },
  moderately_cheaper: { position: 'moderately_cheaper', label: 'Moderadamente barato', icon: 'mdi-arrow-down', color: 'marketModeratelyCheaper' },
  slightly_cheaper: { position: 'slightly_cheaper', label: 'Algo más barato', icon: 'mdi-arrow-down', color: 'marketSlightlyCheaper' },
  aligned: { position: 'aligned', label: 'Alineado al mercado', icon: 'mdi-swap-horizontal', color: 'marketAligned' },
  slightly_expensive: { position: 'slightly_expensive', label: 'Algo más caro', icon: 'mdi-arrow-up', color: 'marketSlightlyExpensive' },
  moderately_expensive: { position: 'moderately_expensive', label: 'Moderadamente caro', icon: 'mdi-arrow-up', color: 'marketModeratelyExpensive' },
  very_expensive: { position: 'very_expensive', label: 'Mucho más caro', icon: 'mdi-arrow-up-bold', color: 'marketVeryExpensive' },
  unavailable: { position: 'unavailable', label: 'Sin comparación', icon: 'mdi-help-circle-outline', color: 'grey' },
}

export function classifyPriceDelta(delta: number | null): PricePosition {
  if (delta === null || !Number.isFinite(delta)) return 'unavailable'
  if (delta <= -20) return 'much_cheaper'
  if (delta <= -15) return 'very_cheaper'
  if (delta <= -10) return 'moderately_cheaper'
  if (delta < -5) return 'slightly_cheaper'
  if (delta <= 5) return 'aligned'
  if (delta < 10) return 'slightly_expensive'
  if (delta < 15) return 'moderately_expensive'
  return 'very_expensive'
}
