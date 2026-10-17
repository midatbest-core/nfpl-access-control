import { BrowserRouter, Route, Routes } from 'react-router-dom'

import { AuthProvider } from './auth/AuthContext'
import { ROLE } from './auth/roles'
import { AppShell } from './components/AppShell'
import { AccountStatusPage, LoginPage, RegisterPage } from './pages/AuthPages'
import { AdminOverviewPage, NotFoundPage, PlaceholderPage, UnauthorizedPage } from './pages/WorkspacePages'
import { ProtectedRoute, PublicOnlyRoute, RoleLanding } from './routes/RouteGuards'

const operationalRoles = [ROLE.maker, ROLE.checker, ROLE.filingOfficer]

function SecuredShell() {
  return <ProtectedRoute><AppShell /></ProtectedRoute>
}

export function App() {
  return (
    <BrowserRouter><AuthProvider><Routes>
      <Route path="/login" element={<PublicOnlyRoute><LoginPage /></PublicOnlyRoute>} />
      <Route path="/register" element={<PublicOnlyRoute><RegisterPage /></PublicOnlyRoute>} />
      <Route path="/account-status" element={<AccountStatusPage />} />
      <Route path="/unauthorized" element={<UnauthorizedPage />} />
      <Route path="/" element={<RoleLanding />} />
      <Route element={<SecuredShell />}>
        <Route path="admin" element={<ProtectedRoute allowedRoles={[ROLE.admin]}><AdminOverviewPage /></ProtectedRoute>} />
        <Route path="admin/jobs" element={<ProtectedRoute allowedRoles={[ROLE.admin]}><PlaceholderPage page="jobs" /></ProtectedRoute>} />
        <Route path="admin/employees" element={<ProtectedRoute allowedRoles={[ROLE.admin]}><PlaceholderPage page="employees" /></ProtectedRoute>} />
        <Route path="admin/requests" element={<ProtectedRoute allowedRoles={[ROLE.admin]}><PlaceholderPage page="requests" /></ProtectedRoute>} />
        <Route path="admin/audit" element={<ProtectedRoute allowedRoles={[ROLE.admin]}><PlaceholderPage page="audit" /></ProtectedRoute>} />
        <Route path="work" element={<ProtectedRoute allowedRoles={operationalRoles}><PlaceholderPage page="work" /></ProtectedRoute>} />
        <Route path="work/jobs/:jobId" element={<ProtectedRoute allowedRoles={operationalRoles}><PlaceholderPage page="job" /></ProtectedRoute>} />
        <Route path="notifications" element={<ProtectedRoute allowedRoles={[ROLE.admin, ...operationalRoles, ROLE.clientViewer]}><PlaceholderPage page="notifications" /></ProtectedRoute>} />
        <Route path="client/shipments" element={<ProtectedRoute allowedRoles={[ROLE.clientViewer]}><PlaceholderPage page="shipments" /></ProtectedRoute>} />
        <Route path="client/shipments/:jobId" element={<ProtectedRoute allowedRoles={[ROLE.clientViewer]}><PlaceholderPage page="shipment" /></ProtectedRoute>} />
        <Route path="client/updates" element={<ProtectedRoute allowedRoles={[ROLE.clientViewer]}><PlaceholderPage page="updates" /></ProtectedRoute>} />
      </Route>
      <Route path="*" element={<NotFoundPage />} />
    </Routes></AuthProvider></BrowserRouter>
  )
}
