export default function AppToolbar() {
  function toggleTheme() {
    const el = document.documentElement
    el.dataset.theme = el.dataset.theme === 'dark' ? 'light' : 'dark'
  }

  return (
    <div
      style={{
        position: 'sticky',
        top: 0,
        background: 'var(--panel-bg)',
        padding: 8,
        display: 'flex',
        gap: 8,
        boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
        zIndex: 10,
        color: 'var(--text-color)',
      }}
    >
      <button onClick={() => window.dispatchEvent(new Event('open-upload'))}>
        Adjuntar Excel
      </button>
      <button onClick={() => window.dispatchEvent(new Event('open-suppliers'))}>
        Proveedores
      </button>
      <button onClick={() => window.dispatchEvent(new Event('open-products'))}>
        Productos
      </button>
      <button onClick={toggleTheme}>Modo oscuro</button>
    </div>
  )
}
