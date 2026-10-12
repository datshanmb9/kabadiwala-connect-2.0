import type { ReactNode } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { LoadingView } from './components/StateViews'
import { AuthProvider, useAuth } from './features/auth/AuthContext'
import { AuditLogsPage } from './pages/AuditLogsPage'
import { CollectorsPage } from './pages/CollectorsPage'
import { ComplaintsPage } from './pages/ComplaintsPage'
import { DashboardPage } from './pages/DashboardPage'
import { LoginPage } from './pages/LoginPage'
import { LotsBidsPage } from './pages/LotsBidsPage'
import { OperationsPage } from './pages/OperationsPage'
import { RecyclersPage } from './pages/RecyclersPage'
import { RewardsPage } from './pages/RewardsPage'
import { RrrCentresPage } from './pages/RrrCentresPage'
import { WardsPage } from './pages/WardsPage'

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

function wrapped(element: ReactNode) {
  return <RequireAuth>{element}</RequireAuth>
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={wrapped(<DashboardPage />)} />
      <Route path="/rrr-centres" element={wrapped(<RrrCentresPage />)} />
      <Route path="/recyclers" element={wrapped(<RecyclersPage />)} />
      <Route path="/collectors" element={wrapped(<CollectorsPage />)} />
      <Route path="/wards" element={wrapped(<WardsPage />)} />
      <Route path="/operations" element={wrapped(<OperationsPage />)} />
      <Route path="/lots-bids" element={wrapped(<LotsBidsPage />)} />
      <Route path="/rewards" element={wrapped(<RewardsPage />)} />
      <Route path="/complaints" element={wrapped(<ComplaintsPage />)} />
      <Route path="/audit-logs" element={wrapped(<AuditLogsPage />)} />
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
