import { render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { App } from '../App'
import { jsonResponse, profile } from './fixtures'

describe('Role-Based Route Guards', () => {
  it('redirects unauthenticated users to /login', async () => {
    window.history.replaceState({}, '', '/admin')
    render(<App />)

    expect(await screen.findByRole('heading', { name: /sign in to your workspace/i })).toBeInTheDocument()
  })

  it('redirects pending users to /account-status', async () => {
    sessionStorage.setItem(
      'nfpl.auth.session',
      JSON.stringify({ token: 'test-token', expiresAt: new Date(Date.now() + 3600_000).toISOString() }),
    )

    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((url: string) => {
        if (url.includes('/v1/identity/me')) {
          return Promise.resolve(jsonResponse(profile([], { account_status: 'pending' })))
        }
        return Promise.reject(new Error(`Unhandled URL: ${url}`))
      }),
    )

    window.history.replaceState({}, '', '/admin')
    render(<App />)

    expect(await screen.findByRole('heading', { name: /pending administrator approval/i })).toBeInTheDocument()
  })

  it('redirects unauthorized staff to /unauthorized when accessing restricted routes', async () => {
    sessionStorage.setItem(
      'nfpl.auth.session',
      JSON.stringify({ token: 'test-token', expiresAt: new Date(Date.now() + 3600_000).toISOString() }),
    )

    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((url: string) => {
        if (url.includes('/v1/identity/me')) {
          // Maker role attempting to access admin route
          return Promise.resolve(jsonResponse(profile(['maker'])))
        }
        return Promise.reject(new Error(`Unhandled URL: ${url}`))
      }),
    )

    window.history.replaceState({}, '', '/admin')
    render(<App />)

    expect(await screen.findByRole('heading', { name: /workspace not assigned/i })).toBeInTheDocument()
  })

  it('allows maker into /work and shows their operational workspace', async () => {
    sessionStorage.setItem(
      'nfpl.auth.session',
      JSON.stringify({ token: 'test-token', expiresAt: new Date(Date.now() + 3600_000).toISOString() }),
    )

    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((url: string) => {
        if (url.includes('/v1/identity/me')) {
          return Promise.resolve(jsonResponse(profile(['maker'])))
        }
        if (url.includes('/v1/my-work')) {
          return Promise.resolve(
            jsonResponse({
              items: [],
              count: 0,
              limit: 25,
              next_cursor: null,
            }),
          )
        }
        if (url.includes('/v1/notifications')) {
          return Promise.resolve(jsonResponse([]))
        }
        return Promise.reject(new Error(`Unhandled URL: ${url}`))
      }),
    )

    window.history.replaceState({}, '', '/work')
    render(<App />)

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /my actionable work queue/i })).toBeInTheDocument()
    })
  })
})
