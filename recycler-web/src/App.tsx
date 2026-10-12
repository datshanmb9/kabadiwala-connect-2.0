import type { ReactNode } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { LoadingView } from './components/StateViews'
import { AuthProvider, useAuth } from './features/auth/AuthContext'
import { BrowseLotsPage } from './pages/BrowseLotsPage'
import { DashboardPage } from './pages/DashboardPage'
import { LoginPage } from './pages/LoginPage'
import { LotDetailPage } from './pages/LotDetailPage'
import { MyBidsPage } from './pages/MyBidsPage'
import { RegisterPage } from './pages/RegisterPage'

function RequireAuth({ children }: { children: ReactNode }) {
  const { status } = useAuth()
  if (status === 'unknown' || status === 'working') {
    return <LoadingView message="Loading…" />
  }
  if (status === 'unauthenticated') {
    return <Navigate to="/login" replace />
  }
  return <>{children}</>
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route
        path="/"
        element={
          <RequireAuth>
            <DashboardPage />
          </RequireAuth>
        }
      />
      <Route
        path="/lots"
        element={
          <RequireAuth>
            <BrowseLotsPage />
          </RequireAuth>
        }
      />
      <Route
        path="/lots/:lotId"
        element={
          <RequireAuth>
            <LotDetailPage />
          </RequireAuth>
        }
      />
      <Route
        path="/my-bids"
        element={
          <RequireAuth>
            <MyBidsPage />
          </RequireAuth>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  )
}
