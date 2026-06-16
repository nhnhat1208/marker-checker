import { useEffect, useState } from 'react'
import { ThemeProvider } from './contexts/theme'
import ChatPage from './pages/ChatPage'
import LoginPage from './pages/LoginPage'

export type User = { email: string; name: string; avatar_url: string }

export default function App() {
  const [user, setUser] = useState<User | null | undefined>(undefined)

  useEffect(() => {
    fetch('/api/me')
      .then(r => (r.status === 401 ? null : r.json()))
      .then((data: User | null) => setUser(data))
      .catch(() => setUser(null))
  }, [])

  if (user === undefined) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <div className="w-8 h-8 rounded-lg bg-primary animate-pulse" />
      </div>
    )
  }

  if (user === null) {
    return (
      <ThemeProvider>
        <LoginPage />
      </ThemeProvider>
    )
  }

  return (
    <ThemeProvider>
      <ChatPage user={user} />
    </ThemeProvider>
  )
}
