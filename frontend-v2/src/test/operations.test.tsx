import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { App } from '../App'
import { jsonResponse, mockJob, profile } from './fixtures'

describe('Operations Workspace and Roles', () => {
  it('Maker views shipment and saves draft description', async () => {
    sessionStorage.setItem(
      'nfpl.auth.session',
      JSON.stringify({ token: 'test-token', expiresAt: new Date(Date.now() + 3600_000).toISOString() }),
    )

    const job = mockJob({ stage: 'confirmed', maker_edit_locked: false })

    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((url: string, init?: RequestInit) => {
        if (url.includes('/v1/identity/me')) {
          return Promise.resolve(jsonResponse(profile(['maker'])))
        }
        if (url.includes('/v1/notifications')) {
          return Promise.resolve(jsonResponse([]))
        }
        if (url.includes('/v1/jobs/job-101/responsibilities')) {
          return Promise.resolve(
            jsonResponse([
              { responsibility: 'maker', user_id: 'user-1', display_name: 'Morgan Lee', current_actor_responsible: true, via_delegation: false },
              { responsibility: 'checker', user_id: 'user-2', display_name: 'Alex Checker', current_actor_responsible: false, via_delegation: false },
              { responsibility: 'filing_officer', user_id: 'user-3', display_name: 'Jordan Filer', current_actor_responsible: false, via_delegation: false },
            ]),
          )
        }
        if (url.includes('/v1/jobs/job-101') && (!init?.method || init.method === 'GET')) {
          return Promise.resolve(jsonResponse(job))
        }
        if (url.includes('/v1/jobs/job-101') && (init?.method === 'PATCH' || init?.method === 'PUT')) {
          const body = JSON.parse(init.body as string)
          return Promise.resolve(jsonResponse({ ...job, ...body, version: 2 }))
        }
        return Promise.reject(new Error(`Unhandled URL: ${url}`))
      }),
    )

    window.history.replaceState({}, '', '/work/jobs/job-101')
    render(<App />)

    expect(await screen.findByDisplayValue('Electronic components and sensors')).toBeInTheDocument()

    const input = screen.getByDisplayValue('Electronic components and sensors')
    fireEvent.change(input, { target: { value: 'Updated robotics parts' } })

    const saveBtn = screen.getByRole('button', { name: /save draft/i })
    fireEvent.click(saveBtn)

    await waitFor(() => {
      expect(screen.getByDisplayValue('Updated robotics parts')).toBeInTheDocument()
    })
  })

  it('Checker sees checklist decisions and requires justification for N/A', async () => {
    sessionStorage.setItem(
      'nfpl.auth.session',
      JSON.stringify({ token: 'test-token', expiresAt: new Date(Date.now() + 3600_000).toISOString() }),
    )

    const job = mockJob({
      stage: 'prepared',
      maker_edit_locked: true,
      checklist_data: {
        items: [
          { key: 'origin_cert', label: 'Certificate of Origin Attached', required: false, status: null, justification: null },
        ],
      },
    })

    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((url: string) => {
        if (url.includes('/v1/identity/me')) {
          return Promise.resolve(jsonResponse(profile(['checker'])))
        }
        if (url.includes('/v1/notifications')) {
          return Promise.resolve(jsonResponse([]))
        }
        if (url.includes('/v1/jobs/job-101/responsibilities')) {
          return Promise.resolve(
            jsonResponse([
              { responsibility: 'maker', user_id: 'user-99', display_name: 'Maker Colleague', current_actor_responsible: false, via_delegation: false },
              { responsibility: 'checker', user_id: 'user-1', display_name: 'Morgan Lee', current_actor_responsible: true, via_delegation: false },
              { responsibility: 'filing_officer', user_id: 'user-3', display_name: 'Jordan Filer', current_actor_responsible: false, via_delegation: false },
            ]),
          )
        }
        if (url.includes('/v1/jobs/job-101')) {
          return Promise.resolve(jsonResponse(job))
        }
        return Promise.reject(new Error(`Unhandled URL: ${url}`))
      }),
    )

    window.history.replaceState({}, '', '/work/jobs/job-101')
    render(<App />)

    expect(await screen.findByText('Certificate of Origin Attached')).toBeInTheDocument()

    // Click N/A on the checklist item
    const naBtn = screen.getByText('N/A')
    fireEvent.click(naBtn)

    // Should prompt for justification input
    expect(await screen.findByPlaceholderText(/audited justification explaining why this item does not apply/i)).toBeInTheDocument()
  })

  it('Filing officer returns shipment with mandatory reason and category', async () => {
    sessionStorage.setItem(
      'nfpl.auth.session',
      JSON.stringify({ token: 'test-token', expiresAt: new Date(Date.now() + 3600_000).toISOString() }),
    )

    const job = mockJob({
      stage: 'checked',
      maker_edit_locked: true,
      checked_by_user_id: 'user-2',
      checklist_data: {
        items: [
          { key: 'invoice_check', label: 'Invoice Verified', required: true, status: 'complete', justification: null },
        ],
      },
    })

    let returnSubmitted = false

    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((url: string, init?: RequestInit) => {
        if (url.includes('/v1/identity/me')) {
          return Promise.resolve(jsonResponse(profile(['filing-officer'])))
        }
        if (url.includes('/v1/notifications')) {
          return Promise.resolve(jsonResponse([]))
        }
        if (url.includes('/v1/jobs/job-101/responsibilities')) {
          return Promise.resolve(
            jsonResponse([
              { responsibility: 'maker', user_id: 'user-99', display_name: 'Maker Colleague', current_actor_responsible: false, via_delegation: false },
              { responsibility: 'checker', user_id: 'user-2', display_name: 'Alex Checker', current_actor_responsible: false, via_delegation: false },
              { responsibility: 'filing_officer', user_id: 'user-1', display_name: 'Morgan Lee', current_actor_responsible: true, via_delegation: false },
            ]),
          )
        }
        if (url.includes('/v1/jobs/job-101/return') && init?.method === 'POST') {
          returnSubmitted = true
          return Promise.resolve(jsonResponse({ ...job, stage: 'returned_maker', version: 2 }))
        }
        if (url.includes('/v1/jobs/job-101/history/operational')) {
          return Promise.resolve(jsonResponse([]))
        }
        if (url.includes('/v1/jobs/job-101')) {
          return Promise.resolve(jsonResponse(job))
        }
        return Promise.reject(new Error(`Unhandled URL: ${url}`))
      }),
    )

    window.history.replaceState({}, '', '/work/jobs/job-101')
    render(<App />)

    expect(await screen.findByRole('button', { name: /return shipment for correction/i })).toBeInTheDocument()

    // Fill in return reason
    const reasonInput = screen.getByPlaceholderText(/provide detailed feedback on required corrections/i)
    fireEvent.change(reasonInput, { target: { value: 'Container seal number does not match BOL' } })

    // Click Return Shipment
    fireEvent.click(screen.getByRole('button', { name: /return shipment for correction/i }))

    // Confirm Return in modal
    const confirmBtn = await screen.findByRole('button', { name: /confirm return/i })
    fireEvent.click(confirmBtn)

    await waitFor(() => {
      expect(returnSubmitted).toBe(true)
    })
  })

  it('Absence nomination displays candidates and submits nomination', async () => {
    sessionStorage.setItem(
      'nfpl.auth.session',
      JSON.stringify({ token: 'test-token', expiresAt: new Date(Date.now() + 3600_000).toISOString() }),
    )

    let nominationCreated = false

    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((url: string, init?: RequestInit) => {
        if (url.includes('/v1/identity/me')) {
          return Promise.resolve(jsonResponse(profile(['maker'])))
        }
        if (url.includes('/v1/notifications')) {
          return Promise.resolve(jsonResponse([]))
        }
        if (url.includes('/v1/absence-nominations/candidates')) {
          return Promise.resolve(
            jsonResponse([
              {
                user_id: 'cand-1',
                display_name: 'Alex Turner',
                eligible_assignment_count: 5,
                total_assignment_count: 5,
              },
            ]),
          )
        }
        if (url.includes('/v1/absence-nominations') && (!init?.method || init.method === 'GET')) {
          return Promise.resolve(jsonResponse([]))
        }
        if (url.includes('/v1/absence-nominations') && init?.method === 'POST') {
          nominationCreated = true
          return Promise.resolve(
            jsonResponse({
              id: 'nom-1',
              requester_user_id: 'user-1',
              nominee_user_id: 'cand-1',
              valid_from: '2026-11-01T08:00:00Z',
              valid_until: '2026-11-05T17:00:00Z',
              reason: 'Annual medical leave',
              status: 'pending',
              requested_at: '2026-10-18T12:00:00Z',
              decided_by_user_id: null,
              decided_at: null,
              decision_reason: null,
              version: 1,
            }),
          )
        }
        return Promise.reject(new Error(`Unhandled URL: ${url}`))
      }),
    )

    window.history.replaceState({}, '', '/absence')
    render(<App />)

    expect(await screen.findByText(/Alex Turner/i)).toBeInTheDocument()

    // Fill nomination form
    const reasonInput = screen.getByPlaceholderText(/explain the planned leave/i)
    fireEvent.change(reasonInput, { target: { value: 'Annual medical leave' } })

    const fromInput = screen.getByLabelText(/absence start/i)
    fireEvent.change(fromInput, { target: { value: '2026-11-01T08:00' } })

    const untilInput = screen.getByLabelText(/absence end/i)
    fireEvent.change(untilInput, { target: { value: '2026-11-05T17:00' } })

    const submitBtn = screen.getByRole('button', { name: /submit absence request/i })
    fireEvent.click(submitBtn)

    await waitFor(() => {
      expect(nominationCreated).toBe(true)
    })
  })
})
