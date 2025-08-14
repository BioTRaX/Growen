import Chat from './components/Chat'
import Sidebar from './components/Sidebar'

export default function App() {
  return (
    <div style={{ display: 'flex' }}>
      <Sidebar />
      <Chat />
    </div>
  )
}
