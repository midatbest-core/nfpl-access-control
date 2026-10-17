import { BrowserRouter, Route, Routes } from 'react-router-dom'

import { AuthProvider } from './auth/AuthContext'
import { ROLE } from './auth/roles'
import { AppShell } from './components/AppShell'
import { AccountStatusPage, LoginPage, RegisterPage } from './pages/AuthPages'
import { NotFoundPage, UnauthorizedPage } from './pages/WorkspacePages'
import { AdminAuditPage, AdminJobsPage, AdminOverviewPage, EmployeesPage } from './pages/AdminPages'
import { JobDetailsPage, RequestsPage } from './pages/AdminRemaining'
import { CreateJobWithSelectionsPage } from './pages/AdminCompletion'
import { ClientShipmentDetailPage, ClientShipmentsPage, ClientUpdatesPage } from './pages/ClientPages'
import { MyWorkPage, NotificationsPage, OperationalJobPage } from './pages/OperationsPages'
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
        <Route path="admin/jobs" element={<ProtectedRoute allowedRoles={[ROLE.admin]}><AdminJobsPage /></ProtectedRoute>} />
        <Route path="admin/jobs/new" element={<ProtectedRoute allowedRoles={[ROLE.admin]}><CreateJobWithSelectionsPage /></ProtectedRoute>} />
        <Route path="admin/jobs/:jobId" element={<ProtectedRoute allowedRoles={[ROLE.admin]}><JobDetailsPage /></ProtectedRoute>} />
        <Route path="admin/employees" element={<ProtectedRoute allowedRoles={[ROLE.admin]}><EmployeesPage /></ProtectedRoute>} />
        <Route path="admin/requests" element={<ProtectedRoute allowedRoles={[ROLE.admin]}><RequestsPage /></ProtectedRoute>} />
        <Route path="admin/audit" element={<ProtectedRoute allowedRoles={[ROLE.admin]}><AdminAuditPage /></ProtectedRoute>} />
        <Route path="work" element={<ProtectedRoute allowedRoles={operationalRoles}><MyWorkPage /></ProtectedRoute>} />
        <Route path="work/jobs/:jobId" element={<ProtectedRoute allowedRoles={operationalRoles}><OperationalJobPage /></ProtectedRoute>} />
        <Route path="notifications" element={<ProtectedRoute allowedRoles={[ROLE.admin, ...operationalRoles, ROLE.clientViewer]}><NotificationsPage /></ProtectedRoute>} />
        <Route path="client/shipments" element={<ProtectedRoute allowedRoles={[ROLE.clientViewer]}><ClientShipmentsPage /></ProtectedRoute>} />
        <Route path="client/shipments/:jobId" element={<ProtectedRoute allowedRoles={[ROLE.clientViewer]}><ClientShipmentDetailPage /></ProtectedRoute>} />
        <Route path="client/updates" element={<ProtectedRoute allowedRoles={[ROLE.clientViewer]}><ClientUpdatesPage /></ProtectedRoute>} />
      </Route>
      <Route path="*" element={<NotFoundPage />} />
    </Routes></AuthProvider></BrowserRouter>
  )
}
