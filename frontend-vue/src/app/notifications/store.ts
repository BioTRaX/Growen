// NG-HEADER: Nombre de archivo: store.ts
// NG-HEADER: Ubicación: frontend-vue/src/app/notifications/store.ts
// NG-HEADER: Descripción: Estado central de notificaciones transitorias del shell Vue.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { defineStore } from 'pinia'

export type ToastKind = 'success' | 'info' | 'warning' | 'error'

interface ToastMessage {
  id: number
  text: string
  kind: ToastKind
  timeout: number
}

let nextId = 1

export const useToastStore = defineStore('toasts', {
  state: () => ({ items: [] as ToastMessage[] }),
  actions: {
    show(text: string, kind: ToastKind = 'info', timeout = 5000) {
      this.items.push({ id: nextId++, text, kind, timeout })
    },
    dismiss(id: number) {
      this.items = this.items.filter((item) => item.id !== id)
    },
  },
})
