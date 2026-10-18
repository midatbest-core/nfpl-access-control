import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { App } from '../App'
import { jsonResponse, profile } from './fixtures'

describe('Authentication Flow', () => {
  beforeEach(() => {
    window.history.replaceState({}, '', '/login')
  })

  it('renders login form and rejects empty submissions', async () => {
    const user = userEvent.setup()
    render(<App />)

    expect(await screen.findByRole('heading', { name: /sign in to your workspace/i })).toBeInTheDocument()

    const submitBtn = screen.getByRole('button', { name: /sign in to workspace/i })
    await user.click(submitBtn)

    expect(await screen.findByText(/please enter both your work email and password/i)).toBeInTheDocument()
  })

  it('signs in successfully and navigates to the role landing workspace', async () => {
    const user = userEvent.setup()
    vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/v1/auth/login')) {
        return Promise.resolve(
          jsonResponse({
            access_token: 'fake-jwt-token',
            token_type: 'bearer',
            expires_at: new Date(Date.now() + 3600_000).toISOString(),
          }),
        )
      }
      if (url.includes('/v1/identity/me')) {
        return Promise.resolve(jsonResponse(profile(['admin'], { display_name: 'Nadia Admin' })))
      }
      if (url.includes('/v1/admin/dashboard/overview')) {
        return Promise.resolve(
          jsonResponse({
            total_jobs: 120,
            jobs_by_stage: { confirmed: 20, prepared: 30, checked: 40, filed: 30 },
            total_employees: 25,
            employees_by_availability: { available: 20, busy: 3, absent: 2 },
            pending_requests: 2,
            reassignment_required_jobs: 1,
          }),
        )
      }
      if (url.includes('/v1/notifications')) {
        return Promise.resolve(jsonResponse([]))
      }
      return Promise.reject(new Error(`Unhandled URL: ${url}`))
    })

    render(<App />)

    const emailInput = await screen.findByLabelText(/email address/i)
    const passwordInput = screen.getByLabelText(/password/i)
    const submitBtn = screen.getByRole('button', { name: /sign in to workspace/i })

    await user.type(emailInput, 'admin@nfpl.test')
    await user.type(passwordInput, 'valid-secret-123')
    await user.click(submitBtn)

    await waitFor(() => {
      expect(screen.getByText(/welcome back, nadia/i)).toBeInTheDocument()
    })

    expect(sessionStorage.getItem('nfpl.auth.session')).toContain('fake-jwt-token')
  })

  it('displays API error message on invalid credentials', async () => {
    const user = userEvent.setup()
    vi.spyOn(globalThis, 'fetch').mockImplementation(() =>
      Promise.resolve(
        jsonResponse({ detail: 'Invalid corporate credentials. Account locked after 5 failed attempts.' }, 401),
      ),
    )

    render(<App />)

    const emailInput = await screen.findByLabelText(/email address/i)
    const passwordInput = screen.getByLabelText(/password/i)
    const submitBtn = screen.getByRole('button', { name: /sign in to workspace/i })

    await user.type(emailInput, 'wrong@nfpl.test')
    await user.type(passwordInput, 'wrong-password')
    await user.click(submitBtn)

    const alerts = await screen.findAllByText(/invalid corporate credentials/i)
    expect(alerts.length).toBeGreaterThanOrEqual(1)
  })
})
