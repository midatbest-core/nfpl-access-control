import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './auth/AuthContext'
import { ROLE } from './auth/roles'
import { ToastProvider } from './components/feedback/ToastContext'
import { AppShell } from './components/shell/AppShell'
import { AdminAttentionPage } from './pages/admin/AdminAttentionPage'
import { AdminAuditDetailPage } from './pages/admin/AdminAuditDetailPage'
import { AdminAuditPage } from './pages/admin/AdminAuditPage'
import { AdminCreateJobPage } from './pages/admin/AdminCreateJobPage'
import { AdminEmployeesPage } from './pages/admin/AdminEmployeesPage'
import { AdminJobDetailPage } from './pages/admin/AdminJobDetailPage'
import { AdminJobsPage } from './pages/admin/AdminJobsPage'
import { AdminOverviewPage } from './pages/admin/AdminOverviewPage'
import { AdminRequestsPage } from './pages/admin/AdminRequestsPage'
import { AccountStatusPage } from './pages/auth/AccountStatusPage'
import { DemoAccountsPage } from './pages/auth/DemoAccountsPage'
import { LoginPage } from './pages/auth/LoginPage'
import { RegisterPage } from './pages/auth/RegisterPage'
import { ClientShipmentDetailPage } from './pages/client/ClientShipmentDetailPage'
import { ClientShipmentsPage } from './pages/client/ClientShipmentsPage'
import { ClientUpdatesPage } from './pages/client/ClientUpdatesPage'
import { NotFoundPage } from './pages/common/NotFoundPage'
import { UnauthorizedPage } from './pages/common/UnauthorizedPage'
import { AbsencePage } from './pages/operations/AbsencePage'
import { MyWorkPage } from './pages/operations/MyWorkPage'
import { NotificationsPage } from './pages/operations/NotificationsPage'
import { OperationalJobPage } from './pages/operations/OperationalJobPage'
import { ProtectedRoute, PublicOnlyRoute, RoleLanding } from './routes/RouteGuards'

const operationalRoles = [ROLE.maker, ROLE.checker, ROLE.filingOfficer]
const allAppRoles = [ROLE.admin, ...operationalRoles, ROLE.clientViewer]

function SecuredShell() {
  return (
    <ProtectedRoute>
      <AppShell />
    </ProtectedRoute>
  )
}

export function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <Routes>
            {/* Public Entry Routes */}
            <Route
              path="/login"
              element={
                <PublicOnlyRoute>
                  <LoginPage />
                </PublicOnlyRoute>
              }
            />
            <Route
              path="/register"
              element={
                <PublicOnlyRoute>
                  <RegisterPage />
                </PublicOnlyRoute>
              }
            />
            <Route
              path="/demo-accounts"
              element={
                <PublicOnlyRoute>
                  <DemoAccountsPage />
                </PublicOnlyRoute>
              }
            />

            {/* Special System States */}
            <Route path="/account-status" element={<AccountStatusPage />} />
            <Route path="/unauthorized" element={<UnauthorizedPage />} />
            <Route path="/" element={<RoleLanding />} />

            {/* Protected Workspace Layout */}
            <Route element={<SecuredShell />}>
              {/* Admin Operations Command */}
              <Route
                path="admin"
                element={
                  <ProtectedRoute allowedRoles={[ROLE.admin]}>
                    <AdminOverviewPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="admin/jobs"
                element={
                  <ProtectedRoute allowedRoles={[ROLE.admin]}>
                    <AdminJobsPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="admin/jobs/new"
                element={
                  <ProtectedRoute allowedRoles={[ROLE.admin]}>
                    <AdminCreateJobPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="admin/jobs/:jobId"
                element={
                  <ProtectedRoute allowedRoles={[ROLE.admin]}>
                    <AdminJobDetailPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="admin/employees"
                element={
                  <ProtectedRoute allowedRoles={[ROLE.admin]}>
                    <AdminEmployeesPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="admin/requests"
                element={
                  <ProtectedRoute allowedRoles={[ROLE.admin]}>
                    <AdminRequestsPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="admin/attention"
                element={
                  <ProtectedRoute allowedRoles={[ROLE.admin]}>
                    <AdminAttentionPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="admin/audit"
                element={
                  <ProtectedRoute allowedRoles={[ROLE.admin]}>
                    <AdminAuditPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="admin/audit/:jobId"
                element={
                  <ProtectedRoute allowedRoles={[ROLE.admin]}>
                    <AdminAuditDetailPage />
                  </ProtectedRoute>
                }
              />

              {/* Operational Workspace */}
              <Route
                path="work"
                element={
                  <ProtectedRoute allowedRoles={operationalRoles}>
                    <MyWorkPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="work/jobs/:jobId"
                element={
                  <ProtectedRoute allowedRoles={operationalRoles}>
                    <OperationalJobPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="absence"
                element={
                  <ProtectedRoute allowedRoles={operationalRoles}>
                    <AbsencePage />
                  </ProtectedRoute>
                }
              />

              {/* Shared Notifications Center */}
              <Route
                path="notifications"
                element={
                  <ProtectedRoute allowedRoles={allAppRoles}>
                    <NotificationsPage />
                  </ProtectedRoute>
                }
              />

              {/* Client Viewer Portal */}
              <Route
                path="client/shipments"
                element={
                  <ProtectedRoute allowedRoles={[ROLE.clientViewer]}>
                    <ClientShipmentsPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="client/shipments/:jobId"
                element={
                  <ProtectedRoute allowedRoles={[ROLE.clientViewer]}>
                    <ClientShipmentDetailPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="client/updates"
                element={
                  <ProtectedRoute allowedRoles={[ROLE.clientViewer]}>
                    <ClientUpdatesPage />
                  </ProtectedRoute>
                }
              />
            </Route>

            {/* 404 Catch-All */}
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  )
}
