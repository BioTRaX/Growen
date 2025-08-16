import ChatWindow from './components/ChatWindow'
import AppToolbar from './components/AppToolbar'
import ToastContainer from './components/Toast'
import Login from './components/Login'
import { AuthProvider, useAuth } from './auth/AuthContext'

function InnerApp() {
  const { state } = useAuth()
  if (!state.isAuthenticated) {
    return <Login />
  }
  return (
    <>
      <AppToolbar />
      <ChatWindow />
      <ToastContainer />
    </>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <InnerApp />
    </AuthProvider>
  )
}
