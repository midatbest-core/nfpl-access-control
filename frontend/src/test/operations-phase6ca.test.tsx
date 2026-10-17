import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { App } from '../App'
import type { Job } from '../api/contracts'
import { jsonResponse, profile } from './fixtures'

const expiresAt = '2099-01-01T00:00:00Z'
const maker = profile(['maker'])

function storedSession(): void {
  sessionStorage.setItem(
    'nfpl.auth.session',
    JSON.stringify({ token: 'maker-session', expiresAt }),
  )
}

function shipment(overrides: Partial<Job> = {}): Job {
  return {
    id: 'job-1',
    reference: 'NFPL-201',
    client_id: 'client-1',
    client_name: 'Acme Imports',
    branch_id: 'branch-1',
    branch_name: 'Head Office',
    direction: 'import',
    mode: 'air',
    stage: 'confirmed',
    goods_description: 'Original goods',
    container_reference: null,
    checklist_data: {},
    checklist_revision: 0,
    maker_edit_locked: false,
    maker_correction_required: false,
    checker_correction_required: false,
    last_return_category: null,
    last_return_reason: null,
    last_maker_justification: null,
    last_checker_justification: null,
    prepared_by_user_id: null,
    checked_by_user_id: null,
    filed_by_user_id: null,
    version: 1,
    ...overrides,
  }
}

const makerResponsibilities = [{
  responsibility: 'maker',
  user_id: maker.id,
  display_name: maker.display_name,
  current_actor_responsible: true,
  via_delegation: false,
}]

function requestMethod(options?: RequestInit): string {
  return options?.method ?? 'GET'
}

describe('Phase 6C-A My Work and Maker workflow', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    sessionStorage.clear()
    storedSession()
  })

  it('shows ordered work metadata, counts, delegation, and keyset pagination', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input)
      if (url.endsWith('/v1/identity/me')) return jsonResponse(maker)
      if (url.includes('/v1/my-work?') && url.includes('cursor=next-page')) {
        return jsonResponse({ items: [], count: 2, limit: 20, next_cursor: null })
      }
      if (url.includes('/v1/my-work?')) {
        return jsonResponse({
          items: [{
            job_id: 'job-1',
            reference: 'NFPL-201',
            client_id: 'client-1',
            client_name: 'Acme Imports',
            branch_id: 'branch-1',
            branch_name: 'Head Office',
            direction: 'import',
            mode: 'air',
            stage: 'confirmed',
            responsibility: 'maker',
            next_action: 'Prepare or correct shipment',
            feedback: 'Correct the container reference.',
            assigned_at: '2026-10-17T10:00:00Z',
            priority: 30,
            version: 1,
            is_delegated: true,
          }],
          count: 2,
          limit: 20,
          next_cursor: 'next-page',
        })
      }
      throw new Error(`Unexpected request: ${url}`)
    })
    window.history.replaceState({}, '', '/work')
    render(<App />)

    const pendingCount = await screen.findByText('2')
    expect(pendingCount.parentElement).toHaveTextContent('2 pending shipments')
    expect(screen.getByText('Acme Imports - Head Office')).toBeInTheDocument()
    expect(screen.getByText('Delegated')).toBeInTheDocument()
    expect(screen.getByText(/Correct the container reference/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Next' }))
    expect(await screen.findByText('No action required')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Previous' }))
    expect(await screen.findByText('NFPL-201')).toBeInTheDocument()
  })

  it('shows empty and revoked-access responses without leaking jobs', async () => {
    let denied = false
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input)
      if (url.endsWith('/v1/identity/me')) return jsonResponse(maker)
      if (url.includes('/v1/my-work?')) {
        if (denied) {
          return jsonResponse({ detail: { reason_code: 'access_revoked', explanation: 'Your access was revoked.' } }, 403)
        }
        denied = true
        return jsonResponse({ items: [], count: 0, limit: 20, next_cursor: 'retry' })
      }
      throw new Error(`Unexpected request: ${url}`)
    })
    window.history.replaceState({}, '', '/work')
    render(<App />)

    expect(await screen.findByText('No action required')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Next' }))
    expect(await screen.findByText('Your access was revoked.')).toBeInTheDocument()
    expect(screen.queryByText('NFPL-201')).not.toBeInTheDocument()
  })

  it('saves Maker edits and submits the refreshed version with confirmation', async () => {
    let current = shipment()
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, options) => {
      const url = String(input)
      if (url.endsWith('/v1/identity/me')) return jsonResponse(maker)
      if (url.endsWith('/v1/jobs/job-1/responsibilities')) return jsonResponse(makerResponsibilities)
      if (url.endsWith('/v1/jobs/job-1') && requestMethod(options) === 'GET') return jsonResponse(current)
      if (url.endsWith('/v1/jobs/job-1') && requestMethod(options) === 'PATCH') {
        current = shipment({ goods_description: 'Updated goods', version: 2 })
        return jsonResponse(current)
      }
      if (url.endsWith('/v1/jobs/job-1/prepare')) {
        current = shipment({ goods_description: 'Updated goods', version: 3, stage: 'prepared', maker_edit_locked: true, checklist_revision: 1 })
        return jsonResponse(current)
      }
      throw new Error(`Unexpected request: ${requestMethod(options)} ${url}`)
    })
    window.history.replaceState({}, '', '/work/jobs/job-1')
    render(<App />)

    const description = await screen.findByLabelText('Goods description')
    await userEvent.clear(description)
    await userEvent.type(description, 'Updated goods')
    await userEvent.click(screen.getByRole('button', { name: 'Save shipment details' }))
    expect(await screen.findByText('Shipment details saved.')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Submit for verification' }))
    const dialog = screen.getByRole('dialog', { name: 'Submit this shipment?' })
    await userEvent.click(within(dialog).getByRole('button', { name: 'Submit shipment' }))

    expect(await screen.findByText('Shipment submitted for independent verification.')).toBeInTheDocument()
    expect(screen.getByText(/submitted revision is locked/i)).toBeInTheDocument()
    const prepareCall = fetchMock.mock.calls.find(([url]) => String(url).endsWith('/prepare'))
    expect(JSON.parse(String(prepareCall?.[1]?.body))).toMatchObject({ expected_version: 2, justification: '' })
  })

  it('requires correction justification before resubmission', async () => {
    const corrected = shipment({
      checklist_revision: 1,
      maker_correction_required: true,
      last_return_reason: 'Container reference is incomplete.',
      last_return_category: 'maker',
      version: 4,
    })
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input)
      if (url.endsWith('/v1/identity/me')) return jsonResponse(maker)
      if (url.endsWith('/responsibilities')) return jsonResponse(makerResponsibilities)
      if (url.endsWith('/v1/jobs/job-1')) return jsonResponse(corrected)
      throw new Error(`Unexpected request: ${url}`)
    })
    window.history.replaceState({}, '', '/work/jobs/job-1')
    render(<App />)

    expect(await screen.findByText('Container reference is incomplete.')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Resubmit corrections' }))
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Resubmit corrections' }))
    expect(await screen.findByText('Explain what was corrected before resubmitting.')).toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/prepare'))).toBe(false)
  })

  it('submits a reasoned post-submission edit request', async () => {
    const locked = shipment({ stage: 'prepared', maker_edit_locked: true, checklist_revision: 1, version: 5 })
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, options) => {
      const url = String(input)
      if (url.endsWith('/v1/identity/me')) return jsonResponse(maker)
      if (url.endsWith('/responsibilities')) return jsonResponse(makerResponsibilities)
      if (url.endsWith('/v1/jobs/job-1') && requestMethod(options) === 'GET') return jsonResponse(locked)
      if (url.endsWith('/edit-requests')) return jsonResponse({ id: 'edit-1', status: 'pending' }, 201)
      throw new Error(`Unexpected request: ${requestMethod(options)} ${url}`)
    })
    window.history.replaceState({}, '', '/work/jobs/job-1')
    render(<App />)

    await userEvent.type(await screen.findByLabelText('Reason'), 'Correct consignee details')
    await userEvent.click(screen.getByRole('button', { name: 'Send edit request' }))
    expect(await screen.findByText('Edit request submitted. Current status: pending.')).toBeInTheDocument()
    const request = fetchMock.mock.calls.find(([url]) => String(url).endsWith('/edit-requests'))
    expect(JSON.parse(String(request?.[1]?.body))).toEqual({ reason: 'Correct consignee details' })
  })

  it('surfaces stale versions and keeps the current form available for review', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, options) => {
      const url = String(input)
      if (url.endsWith('/v1/identity/me')) return jsonResponse(maker)
      if (url.endsWith('/responsibilities')) return jsonResponse(makerResponsibilities)
      if (url.endsWith('/v1/jobs/job-1') && requestMethod(options) === 'GET') return jsonResponse(shipment())
      if (url.endsWith('/v1/jobs/job-1') && requestMethod(options) === 'PATCH') {
        return jsonResponse({ detail: { reason_code: 'stale_version', explanation: 'The shipment changed since you opened it.' } }, 409)
      }
      throw new Error(`Unexpected request: ${requestMethod(options)} ${url}`)
    })
    window.history.replaceState({}, '', '/work/jobs/job-1')
    render(<App />)

    await userEvent.click(await screen.findByRole('button', { name: 'Save shipment details' }))
    expect(await screen.findByText('The shipment changed since you opened it.')).toBeInTheDocument()
    expect(screen.getByLabelText('Goods description')).toBeEnabled()
  })

  it('lists unread notifications, marks them read, and opens the reauthorized job route', async () => {
    let read = false
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, options) => {
      const url = String(input)
      if (url.endsWith('/v1/identity/me')) return jsonResponse(maker)
      if (url.includes('/v1/notifications?')) {
        return jsonResponse([{
          id: 'notification-1',
          job_id: 'job-1',
          job_reference: 'NFPL-201',
          event_type: 'job_assigned',
          message: 'A shipment was assigned to you.',
          target_path: '/v1/jobs/job-1',
          created_at: '2026-10-17T10:00:00Z',
          read_at: read ? '2026-10-17T10:01:00Z' : null,
        }])
      }
      if (url.endsWith('/v1/notifications/unread-count')) return jsonResponse({ count: read ? 0 : 1 })
      if (url.endsWith('/v1/notifications/notification-1/read') && requestMethod(options) === 'POST') {
        read = true
        return jsonResponse({ id: 'notification-1', read_at: '2026-10-17T10:01:00Z' })
      }
      if (url.endsWith('/v1/jobs/job-1')) return jsonResponse(shipment())
      if (url.endsWith('/responsibilities')) return jsonResponse(makerResponsibilities)
      throw new Error(`Unexpected request: ${requestMethod(options)} ${url}`)
    })
    window.history.replaceState({}, '', '/notifications')
    render(<App />)

    expect(await screen.findByText('1 unread actionable notification.')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Open shipment' }))
    expect(await screen.findByRole('heading', { name: 'NFPL-201' })).toBeInTheDocument()
    await waitFor(() => expect(read).toBe(true))
  })
})
