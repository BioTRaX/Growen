// NG-HEADER: Nombre de archivo: chat.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/chat/api/chat.ts
// NG-HEADER: Descripción: Transporte HTTP y feedback del módulo Chat.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { http } from '../../../services/http'

export interface ChatCitation {
  source_id: number
  title: string
  chunk_index: number
  page?: number | null
  score: number
  content_version: number
}

export interface ChatProduct {
  product_id?: number
  name?: string
  title?: string
  sale_price?: number
  availability?: string
  sku?: string
  stock?: number
  images?: Array<{ url?: string } | string>
}

export interface ChatResponse {
  text: string
  type: string
  intent?: string
  data?: { products?: ChatProduct[]; items?: ChatProduct[] } | null
  citations?: ChatCitation[]
  correlation_id?: string
}

export async function sendChat(
  text: string,
  imageUrl: string | undefined,
  signal: AbortSignal,
): Promise<{ data: ChatResponse; correlationId?: string }> {
  const response = await http.post<ChatResponse>('/chat', { text, image_url: imageUrl || null }, { signal })
  return { data: response.data, correlationId: response.data.correlation_id || response.headers['x-correlation-id'] }
}

export async function sendChatFeedback(correlationId: string, rating: 'positive' | 'negative'): Promise<void> {
  await http.post('/chat/feedback', { correlation_id: correlationId, rating })
}
