import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { App } from '../App'
import { jsonResponse, profile } from './fixtures'

const expiresAt = '2099-01-01T00:00:00Z'

function storedSession(token = 'test-session'): void {
  sessionStorage.setItem(
    'nfpl.auth.session',
    JSON.stringify({ token, expiresAt }),
  )
}

function method(options?: RequestInit): string {
  return options?.method ?? 'GET'
}

describe('final evaluator workflow refinements', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    sessionStorage.clear()
  })

  it('sends My Work search terms to the protected server query', async () => {
    storedSession()
    const urls: string[] = []
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input)
      urls.push(url)
      if (url.endsWith('/v1/identity/me')) return jsonResponse(profile(['maker']))
      if (url.includes('/v1/my-work?')) {
        return jsonResponse({ items: [], count: 0, limit: 20, next_cursor: null })
      }
      throw new Error('Unexpected My Work request: ' + url)
    })
    window.history.replaceState({}, '', '/work')
    render(<App />)

    const search = await screen.findByLabelText('Search assigned jobs')
    await userEvent.type(search, 'Oriana textiles')
    await waitFor(() => {
      expect(urls.some((url) => url.includes('search=Oriana+textiles'))).toBe(true)
    }, { timeout: 1500 })
  })

  it('marks every visible notification read and clears only the local view', async () => {
    storedSession()
    let markedAll = 0
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, options) => {
      const url = String(input)
      if (url.endsWith('/v1/identity/me')) return jsonResponse(profile(['maker']))
      if (url.includes('/v1/notifications?')) {
        return jsonResponse([{
          id: 'notice-1', job_id: null, job_reference: null,
          event_type: 'assignment', message: 'New assignment available.',
          target_path: '/v1/my-work', created_at: '2026-10-18T08:00:00Z', read_at: null,
        }])
      }
      if (url.endsWith('/v1/notifications/unread-count')) return jsonResponse({ count: 1 })
      if (url.endsWith('/v1/notifications/read-all') && method(options) === 'POST') {
        markedAll += 1
        return jsonResponse({ updated: 1 })
      }
      throw new Error('Unexpected notifications request: ' + method(options) + ' ' + url)
    })
    window.history.replaceState({}, '', '/notifications')
    render(<App />)

    expect(await screen.findByText('New assignment available.')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Clear all' }))
    expect(await screen.findByText(/records were preserved/i)).toBeInTheDocument()
    expect(screen.queryByText('New assignment available.')).not.toBeInTheDocument()
    expect(markedAll).toBe(1)
  })

  it('submits bounded absence cover with an eligible replacement', async () => {
    storedSession()
    let submitted: Record<string, unknown> | undefined
    let nominations: unknown[] = []
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, options) => {
      const url = String(input)
      if (url.endsWith('/v1/identity/me')) return jsonResponse(profile(['maker']))
      if (url.endsWith('/v1/absence-nominations/candidates')) {
        return jsonResponse([{ user_id: 'cover-1', display_name: 'Diya Nair', eligible_assignment_count: 2, total_assignment_count: 2 }])
      }
      if (url.endsWith('/v1/absence-nominations') && method(options) === 'GET') return jsonResponse(nominations)
      if (url.endsWith('/v1/absence-nominations') && method(options) === 'POST') {
        submitted = JSON.parse(String(options?.body)) as Record<string, unknown>
        const nomination = {
          id: 'absence-1', requester_user_id: 'user-1', nominee_user_id: 'cover-1',
          valid_from: submitted.valid_from, valid_until: submitted.valid_until,
          reason: submitted.reason, status: 'pending', requested_at: '2026-10-18T08:00:00Z',
          decided_by_user_id: null, decided_at: null, decision_reason: null, version: 1,
        }
        nominations = [nomination]
        return jsonResponse(nomination, 201)
      }
      throw new Error('Unexpected absence request: ' + method(options) + ' ' + url)
    })
    window.history.replaceState({}, '', '/absence')
    render(<App />)

    expect(await screen.findByText(/Diya Nair/)).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText('From'), '2026-10-20T09:00')
    await userEvent.type(screen.getByLabelText('Until'), '2026-10-21T18:00')
    await userEvent.type(screen.getByLabelText('Reason'), 'Planned leave with handoff complete')
    await userEvent.click(screen.getByRole('button', { name: 'Submit absence request' }))

    expect(await screen.findByText('Absence request submitted for Admin review.')).toBeInTheDocument()
    expect(submitted).toMatchObject({ nominee_user_id: 'cover-1', reason: 'Planned leave with handoff complete' })
  })

  it('lets a client raise a sanitized shipment-specific query', async () => {
    storedSession('client-session')
    const client = profile(['client-viewer'], {
      kind: 'client', client_id: 'client-1', client_name: 'Oriana Textiles',
    } as any)
    let queryBody: Record<string, unknown> | undefined
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, options) => {
      const url = String(input)
      if (url.endsWith('/v1/identity/me')) return jsonResponse(client)
      if (url.endsWith('/v1/jobs/job-client') || url.endsWith('/v1/client/jobs/job-client')) {
        return jsonResponse({ id: 'job-client', reference: 'NFPL-501', client_id: 'client-1', direction: 'import', mode: 'air', stage: 'confirmed', version: 2 })
      }
      if (url.endsWith('/v1/client/jobs/job-client/status')) {
        return jsonResponse({ job_id: 'job-client', reference: 'NFPL-501', stage: 'confirmed', progress_percent: 20, updated_at: '2026-10-18T08:00:00Z', version: 2 })
      }
      if (url.includes('/v1/client/jobs/job-client/history?')) return jsonResponse([])
      if (url.includes('/v1/notifications')) return jsonResponse([])
      if (url.endsWith('/v1/notifications/unread-count')) return jsonResponse({ count: 0 })
      if (url.endsWith('/v1/client/jobs/job-client/queries') && method(options) === 'POST') {
        queryBody = JSON.parse(String(options?.body)) as Record<string, unknown>
        return jsonResponse({ audit_event_id: 'audit-1', delivered: 1 }, 201)
      }
      throw new Error('Unexpected client request: ' + method(options) + ' ' + url)
    })
    window.history.replaceState({}, '', '/client/shipments/job-client')
    render(<App />)

    await userEvent.selectOptions(await screen.findByLabelText('Concern'), 'delay')
    await userEvent.type(screen.getByLabelText('Explanation'), 'Please confirm the expected handoff date.')
    await userEvent.click(screen.getByRole('button', { name: 'Send query to Admin' }))

    expect(await screen.findByText(/sent to 1 authorized Admin/i)).toBeInTheDocument()
    expect(queryBody).toEqual({ category: 'delay', explanation: 'Please confirm the expected handoff date.' })
  })
})
