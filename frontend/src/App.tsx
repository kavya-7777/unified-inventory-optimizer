import { Route, Routes } from 'react-router-dom'
import { AppLayout } from '@/components/layout/AppLayout'
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

function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/network" element={<NetworkPage />} />
        <Route path="/inventory" element={<InventoryPage />} />
        <Route path="/demand" element={<DemandPage />} />
        <Route path="/optimization" element={<OptimizationPage />} />
        <Route path="/transportation" element={<TransportationPage />} />
        <Route path="/runs" element={<RunsPage />} />
        <Route path="/runs/:runId" element={<RunDetailPage />} />
        <Route path="/policies" element={<PoliciesPage />} />
        <Route path="/alerts" element={<AlertsPage />} />
      </Route>
    </Routes>
  )
}

export default App
