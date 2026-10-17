import { afterEach, describe, expect, it, vi } from 'vitest'

import { api, ApiError, setUnauthorizedHandler } from '../api/client'
import { effectiveRoles, landingPath } from '../auth/roles'
import { jsonResponse, profile, role } from './fixtures'

afterEach(() => {
  vi.restoreAllMocks()
  setUnauthorizedHandler(undefined)
})

describe('API error handling', () => {
  it('surfaces structured authorization explanations and reason codes', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(jsonResponse({
      detail: {
        explanation: 'Your Checker grant is limited to another client.',
        reason_code: 'scope_mismatch',
      },
    }, 403))

    const result = api.profile('token')
    await expect(result).rejects.toMatchObject({
      name: 'ApiError',
      message: 'Your Checker grant is limited to another client.',
      status: 403,
      reasonCode: 'scope_mismatch',
    })
  })

  it('uses a safe network error and clears auth on protected 401 responses', async () => {
    const unauthorized = vi.fn()
    setUnauthorizedHandler(unauthorized)
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      jsonResponse({ detail: 'Session expired' }, 401),
    )

    await expect(api.profile('token')).rejects.toBeInstanceOf(ApiError)
    expect(unauthorized).toHaveBeenCalledOnce()

    vi.mocked(globalThis.fetch).mockRejectedValueOnce(new TypeError('private network detail'))
    await expect(api.login({ email: 'a@b.example', password: 'secret' })).rejects.toThrow(
      'The NFPL service could not be reached.',
    )
  })
})

describe('effective roles and landing routes', () => {
  it('excludes expired and revoked assignments using half-open time boundaries', () => {
    const at = new Date('2026-06-01T10:00:00Z')
    const employee = profile([], {
      roles: [
        role('maker', { valid_until: '2026-06-01T10:00:00Z' }),
        role('checker', { revoked_at: '2026-06-01T10:00:00Z' }),
        role('filing-officer', { valid_from: '2026-06-01T10:00:00Z' }),
      ],
    })

    expect([...effectiveRoles(employee, at)]).toEqual(['filing-officer'])
  })

  it('uses deterministic role precedence and client identity checks', () => {
    expect(landingPath(profile(['maker', 'admin']))).toBe('/admin')
    expect(landingPath(profile(['client-viewer'], { kind: 'client' }))).toBe('/client/shipments')
    expect(landingPath(profile(['client-viewer'], { kind: 'staff' }))).toBe('/client/shipments')
    expect(landingPath(profile([]))).toBe('/unauthorized')
  })
})
