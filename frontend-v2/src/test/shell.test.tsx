import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { AuthProvider } from '../auth/AuthContext'
import { ToastProvider, useToast } from '../components/feedback/ToastContext'
import { AppShell } from '../components/shell/AppShell'
import { jsonResponse, profile } from './fixtures'

function TestToastTrigger() {
  const toast = useToast()
  return (
    <button
      type="button"
      onClick={() => toast.success('Shipment marked ready', 'Operation Successful')}
    >
      Trigger Toast
    </button>
  )
}

describe('Application Shell & Toast Feedback', () => {
  it('renders top-right toast notification when triggered', async () => {
    render(
      <ToastProvider>
        <TestToastTrigger />
      </ToastProvider>,
    )

    const triggerBtn = screen.getByRole('button', { name: 'Trigger Toast' })
    triggerBtn.click()

    expect(await screen.findByText('Operation Successful')).toBeInTheDocument()
    expect(screen.getByText('Shipment marked ready')).toBeInTheDocument()
  })

  it('renders AppShell with sidebar brand and navigation links', async () => {
    sessionStorage.setItem(
      'nfpl.auth.session',
      JSON.stringify({ token: 'test-token', expiresAt: new Date(Date.now() + 3600_000).toISOString() }),
    )

    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((url: string) => {
        if (url.includes('/v1/identity/me')) {
          return Promise.resolve(jsonResponse(profile(['admin'], { display_name: 'Nadia Admin' })))
        }
        if (url.includes('/v1/notifications')) {
          return Promise.resolve(jsonResponse([]))
        }
        return Promise.reject(new Error(`Unhandled URL: ${url}`))
      }),
    )

    render(
      <MemoryRouter initialEntries={['/admin']}>
        <AuthProvider>
          <ToastProvider>
            <AppShell />
          </ToastProvider>
        </AuthProvider>
      </MemoryRouter>,
    )

    expect(await screen.findByText('NFPL')).toBeInTheDocument()
    expect(screen.getAllByText('Operations Command').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('Shipments')).toBeInTheDocument()
    expect(screen.getByText('Workforce & Roles')).toBeInTheDocument()
  })

  it('opens dynamic notifications pop-up when bell icon is clicked', async () => {
    sessionStorage.setItem(
      'nfpl.auth.session',
      JSON.stringify({ token: 'test-token', expiresAt: new Date(Date.now() + 3600_000).toISOString() }),
    )

    const mockNotifications = [
      {
        id: 'notif-1',
        job_id: 'job-101',
        job_reference: 'EXP-2026-0042',
        event_type: 'submission_ready',
        message: 'Maker completed draft and submitted version 1 for review',
        target_path: '/v1/jobs/job-101',
        created_at: new Date().toISOString(),
        read_at: null,
      },
    ]

    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((url: string) => {
        if (url.includes('/v1/identity/me')) {
          return Promise.resolve(jsonResponse(profile(['admin'], { display_name: 'Nadia Admin' })))
        }
        if (url.includes('/v1/notifications')) {
          return Promise.resolve(jsonResponse(mockNotifications))
        }
        return Promise.reject(new Error(`Unhandled URL: ${url}`))
      }),
    )

    render(
      <MemoryRouter initialEntries={['/admin']}>
        <AuthProvider>
          <ToastProvider>
            <AppShell />
          </ToastProvider>
        </AuthProvider>
      </MemoryRouter>,
    )

    // Wait for the bell trigger with unread badge to appear
    const bellBtn = await screen.findByRole('button', { name: 'View notifications' })
    expect(bellBtn).toBeInTheDocument()

    // Click the bell to open the floating popover
    bellBtn.click()

    // Verify pop-up elements are displayed
    expect(await screen.findByRole('dialog', { name: 'Notifications pop-up' })).toBeInTheDocument()
    expect(await screen.findByText('Maker completed draft and submitted version 1 for review')).toBeInTheDocument()
    expect(screen.getByText('EXP-2026-0042')).toBeInTheDocument()
    expect(screen.getByText('Open Full Notifications Center')).toBeInTheDocument()
  })
})

