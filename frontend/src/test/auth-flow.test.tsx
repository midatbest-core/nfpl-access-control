import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { App } from '../App'
import { jsonResponse, profile } from './fixtures'

const expiresAt = '2099-01-01T00:00:00Z'

function storedSession(): void {
  sessionStorage.setItem(
    'nfpl.auth.session',
    JSON.stringify({ token: 'session-token', expiresAt }),
  )
}

describe('authentication screens', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('validates the login form before calling the API', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch')
    window.history.replaceState({}, '', '/login')
    render(<App />)

    await userEvent.click(screen.getByRole('button', { name: /sign in securely/i }))

    expect(screen.getByText('Enter a valid email address.')).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('logs in, loads the profile, and routes an Admin to relevant navigation', async () => {
    const admin = profile(['admin'])
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(jsonResponse({
        access_token: 'session-token',
        token_type: 'bearer',
        expires_at: expiresAt,
      }))
      .mockResolvedValueOnce(jsonResponse(admin))
    window.history.replaceState({}, '', '/login')
    render(<App />)

    await userEvent.type(screen.getByLabelText(/email address/i), 'ADMIN@NFPL.EXAMPLE')
    await userEvent.type(screen.getByLabelText(/^password$/i), 'Correct Horse Battery 7')
    await userEvent.click(screen.getByRole('button', { name: /sign in securely/i }))

    expect(await screen.findByRole('heading', { name: 'Good day, Morgan' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Employees' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'My shipments' })).not.toBeInTheDocument()
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      expect.stringMatching(/\/v1\/auth\/login$/),
      expect.objectContaining({ method: 'POST' }),
    )
    expect(sessionStorage.getItem('nfpl.auth.session')).toContain('session-token')
  })

  it('routes pending or disabled login attempts to a privacy-safe status page', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      jsonResponse({ detail: 'Account is not active' }, 403),
    )
    window.history.replaceState({}, '', '/login')
    render(<App />)

    await userEvent.type(screen.getByLabelText(/email address/i), 'pending@nfpl.example')
    await userEvent.type(screen.getByLabelText(/^password$/i), 'Correct Horse Battery 7')
    await userEvent.click(screen.getByRole('button', { name: /sign in securely/i }))

    expect(await screen.findByRole('heading', { name: 'Account unavailable' })).toBeInTheDocument()
    expect(screen.getByText(/does not reveal private account-state details/i)).toBeInTheDocument()
  })

  it('validates registration and submits no role or privilege selection', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch')
    window.history.replaceState({}, '', '/register')
    render(<App />)

    await userEvent.click(screen.getByRole('button', { name: /submit for approval/i }))
    expect(screen.getByText('Enter your full name.')).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()

    await userEvent.type(screen.getByLabelText(/full name/i), 'Asha Rao')
    await userEvent.type(screen.getByLabelText(/work email/i), 'ASHA@NFPL.EXAMPLE')
    await userEvent.type(screen.getByLabelText(/branch id/i), 'branch-2')
    await userEvent.type(screen.getByLabelText(/^password/i), 'Strong Registration 9')
    await userEvent.type(screen.getByLabelText(/confirm password/i), 'Strong Registration 9')
    fetchMock.mockResolvedValueOnce(jsonResponse({
      id: 'user-2',
      email: 'asha@nfpl.example',
      display_name: 'Asha Rao',
      branch_id: 'branch-2',
      account_status: 'pending',
    }, 201))
    await userEvent.click(screen.getByRole('button', { name: /submit for approval/i }))

    expect(await screen.findByRole('heading', { name: 'Request received' })).toBeInTheDocument()
    const request = fetchMock.mock.calls[0][1] as RequestInit
    const body = JSON.parse(String(request.body)) as Record<string, unknown>
    expect(body).toEqual({
      name: 'Asha Rao',
      email: 'asha@nfpl.example',
      password: 'Strong Registration 9',
      branch_id: 'branch-2',
    })
    expect(body).not.toHaveProperty('roles')
  })

  it('logs out through the backend and clears local authentication state', async () => {
    storedSession()
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input)
      if (url.endsWith('/v1/identity/me')) return jsonResponse(profile(['maker']))
      if (url.includes('/v1/my-work?')) {
        return jsonResponse({ items: [], count: 0, limit: 20, next_cursor: null })
      }
      if (url.endsWith('/v1/auth/logout')) return new Response(null, { status: 204 })
      throw new Error(`Unexpected request: ${url}`)
    })
    window.history.replaceState({}, '', '/work')
    render(<App />)

    await screen.findByRole('heading', { name: 'My work' })
    await userEvent.click(screen.getByRole('button', { name: 'Sign out' }))
    const dialog = screen.getByRole('dialog', { name: 'Sign out of NFPL?' })
    await userEvent.click(within(dialog).getByRole('button', { name: 'Sign out' }))

    expect(await screen.findByRole('heading', { name: 'Welcome back' })).toBeInTheDocument()
    expect(sessionStorage.getItem('nfpl.auth.session')).toBeNull()
    expect(fetchMock).toHaveBeenLastCalledWith(
      expect.stringMatching(/\/v1\/auth\/logout$/),
      expect.objectContaining({
        method: 'POST',
        headers: expect.any(Headers),
      }),
    )
  })
})

describe('protected and role-aware routes', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('rejects an operational employee from an Admin route without disclosing data', async () => {
    storedSession()
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(jsonResponse(profile(['maker'])))
    window.history.replaceState({}, '', '/admin')
    render(<App />)

    expect(await screen.findByRole('heading', { name: /workspace is not assigned/i })).toBeInTheDocument()
    expect(screen.getByText(/no shipment details were disclosed/i)).toBeInTheDocument()
  })

  it('shows all relevant navigation for overlapping effective roles', async () => {
    storedSession()
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input)
      if (url.endsWith('/v1/identity/me')) {
        return jsonResponse(profile(['maker', 'checker', 'filing-officer']))
      }
      if (url.includes('/v1/my-work?')) {
        return jsonResponse({ items: [], count: 0, limit: 20, next_cursor: null })
      }
      throw new Error(`Unexpected request: ${url}`)
    })
    window.history.replaceState({}, '', '/work')
    render(<App />)

    expect(await screen.findByRole('heading', { name: 'My work' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'My work' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Notifications' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Employees' })).not.toBeInTheDocument()
  })

  it('clears an expired stored session and returns to login', async () => {
    sessionStorage.setItem(
      'nfpl.auth.session',
      JSON.stringify({ token: 'expired', expiresAt: '2020-01-01T00:00:00Z' }),
    )
    const fetchMock = vi.spyOn(globalThis, 'fetch')
    window.history.replaceState({}, '', '/work')
    render(<App />)

    expect(await screen.findByRole('heading', { name: 'Welcome back' })).toBeInTheDocument()
    expect(screen.getByText(/session ended/i)).toBeInTheDocument()
    expect(sessionStorage.getItem('nfpl.auth.session')).toBeNull()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('drops a revoked session when profile loading receives 401', async () => {
    storedSession()
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      jsonResponse({ detail: 'Session revoked' }, 401),
    )
    window.history.replaceState({}, '', '/work')
    render(<App />)

    await waitFor(() => expect(sessionStorage.getItem('nfpl.auth.session')).toBeNull())
    expect(await screen.findByRole('heading', { name: 'Welcome back' })).toBeInTheDocument()
  })
})
