// NG-HEADER: Nombre de archivo: setup.ts
// NG-HEADER: Ubicación: frontend-vue/src/test/setup.ts
// NG-HEADER: Descripción: Configuración global de entorno y stubs para pruebas en Vitest / jsdom.
// NG-HEADER: Lineamientos: Ver AGENTS.md

if (!globalThis.ResizeObserver) {
  class ResizeObserverMock {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  globalThis.ResizeObserver = ResizeObserverMock
}

if (!globalThis.visualViewport) {
  Object.defineProperty(globalThis, 'visualViewport', {
    configurable: true,
    value: {
      width: 1024,
      height: 768,
      offsetLeft: 0,
      offsetTop: 0,
      pageLeft: 0,
      pageTop: 0,
      scale: 1,
      addEventListener: () => {},
      removeEventListener: () => {},
    },
  })
}
