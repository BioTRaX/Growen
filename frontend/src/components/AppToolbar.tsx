export default function AppToolbar() {
  return (
    <div
      style={{
        position: 'sticky',
        top: 0,
        background: '#fff',
        padding: 8,
        display: 'flex',
        gap: 8,
        boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
        zIndex: 10,
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
    </div>
  )
}
