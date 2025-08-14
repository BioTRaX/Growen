import { useState } from 'react'
import { examples } from '../lib/commands'

export default function Sidebar() {
  const [command, setCommand] = useState('')

  return (
    <div style={{ width: '200px', borderRight: '1px solid #ccc', padding: '1rem' }}>
      <h3>Acciones</h3>
      <ul>
        {examples.map((c) => (
          <li key={c} onClick={() => setCommand(c)} style={{ cursor: 'pointer' }}>
            {c}
          </li>
        ))}
      </ul>
    </div>
  )
}
