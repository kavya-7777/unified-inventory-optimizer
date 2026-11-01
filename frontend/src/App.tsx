import { Route, Routes } from 'react-router-dom'
import { AppLayout } from '@/components/layout/AppLayout'
import { RequireAuth, RequireRole } from '@/components/auth/Guards'
import { LoginPage } from '@/pages/LoginPage'
import { DashboardPage } from '@/pages/DashboardPage'
import { InventoryPage } from '@/pages/InventoryPage'
import { DemandPage } from '@/pages/DemandPage'
import { OptimizationPage } from '@/pages/OptimizationPage'
import { RunsPage } from '@/pages/RunsPage'
import { RunDetailPage } from '@/pages/RunDetailPage'
import { AlertsPage } from '@/pages/AlertsPage'
import { NetworkPage } from '@/pages/NetworkPage'
import { TransportationPage } from '@/pages/TransportationPage'
import { PoliciesPage } from '@/pages/PoliciesPage'
import { ImportPage } from '@/pages/ImportPage'
import { UsersPage } from '@/pages/UsersPage'
import { ActivityPage } from '@/pages/ActivityPage'
import { AccountPage } from '@/pages/AccountPage'
import { NotFoundPage } from '@/pages/NotFoundPage'

function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<RequireAuth />}>
        <Route element={<AppLayout />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/network" element={<NetworkPage />} />
          <Route path="/inventory" element={<InventoryPage />} />
          <Route path="/demand" element={<DemandPage />} />
          <Route path="/optimization" element={<RequireRole role="planner"><OptimizationPage /></RequireRole>} />
          <Route path="/transportation" element={<TransportationPage />} />
          <Route path="/runs" element={<RunsPage />} />
          <Route path="/runs/:runId" element={<RunDetailPage />} />
          <Route path="/policies" element={<PoliciesPage />} />
          <Route path="/alerts" element={<AlertsPage />} />
          <Route path="/import" element={<RequireRole role="planner"><ImportPage /></RequireRole>} />
          <Route path="/users" element={<RequireRole role="admin"><UsersPage /></RequireRole>} />
          <Route path="/activity" element={<RequireRole role="admin"><ActivityPage /></RequireRole>} />
          <Route path="/account" element={<AccountPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Route>
    </Routes>
  )
}

export default App
