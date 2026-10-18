import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { App } from '../App'
import { jsonResponse, mockJob, mockReferenceData, profile } from './fixtures'

describe('Admin Workspace and Client Viewer', () => {
  it('Admin dashboard displays operational statistics and cards', async () => {
    sessionStorage.setItem(
      'nfpl.auth.session',
      JSON.stringify({ token: 'test-token', expiresAt: new Date(Date.now() + 3600_000).toISOString() }),
    )

    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((url: string) => {
        if (url.includes('/v1/identity/me')) {
          return Promise.resolve(jsonResponse(profile(['admin'])))
        }
        if (url.includes('/v1/notifications')) {
          return Promise.resolve(jsonResponse([]))
        }
        if (url.includes('/v1/admin/dashboard/overview')) {
          return Promise.resolve(
            jsonResponse({
              total_jobs: 142,
              jobs_by_stage: {
                draft: 12,
                under_check: 8,
                checked: 5,
                filed: 110,
                cancelled: 7,
              },
              total_employees: 18,
              employees_by_availability: {
                available: 15,
                busy: 2,
                absent: 1,
              },
              pending_requests: 3,
              reassignment_required_jobs: 4,
            }),
          )
        }
        return Promise.reject(new Error(`Unhandled URL: ${url}`))
      }),
    )

    window.history.replaceState({}, '', '/admin')
    render(<App />)

    expect(await screen.findByText('142')).toBeInTheDocument()
    expect(screen.getByText('18')).toBeInTheDocument()
    expect(screen.getByText('Total Shipments')).toBeInTheDocument()
    expect(screen.getByText('Needs Attention')).toBeInTheDocument()
  })

  it('Admin creates new shipment and opens assignment suggestions', async () => {
    sessionStorage.setItem(
      'nfpl.auth.session',
      JSON.stringify({ token: 'test-token', expiresAt: new Date(Date.now() + 3600_000).toISOString() }),
    )

    const created = mockJob({ id: 'job-999', reference: 'NFPL-2026-FCL-0042' })
    let createdSubmitted = false

    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((url: string, init?: RequestInit) => {
        if (url.includes('/v1/identity/me')) {
          return Promise.resolve(jsonResponse(profile(['admin'])))
        }
        if (url.includes('/v1/notifications')) {
          return Promise.resolve(jsonResponse([]))
        }
        if (url.includes('/v1/admin/reference-data')) {
          return Promise.resolve(jsonResponse(mockReferenceData()))
        }
        if (url.includes('/v1/admin/jobs/job-999/assignment-suggestions')) {
          return Promise.resolve(
            jsonResponse({
              maker: [],
              checker: [],
              filing_officer: [],
            }),
          )
        }
        if (url.includes('/v1/jobs/job-999/responsibilities')) {
          return Promise.resolve(
            jsonResponse([
              { responsibility: 'maker', user_id: null, display_name: null, current_actor_responsible: false, via_delegation: false },
              { responsibility: 'checker', user_id: null, display_name: null, current_actor_responsible: false, via_delegation: false },
              { responsibility: 'filing_officer', user_id: null, display_name: null, current_actor_responsible: false, via_delegation: false },
            ]),
          )
        }
        if (url.includes('/v1/jobs') && init?.method === 'POST') {
          createdSubmitted = true
          return Promise.resolve(jsonResponse(created))
        }
        return Promise.reject(new Error(`Unhandled URL: ${url}`))
      }),
    )

    window.history.replaceState({}, '', '/admin/jobs/new')
    render(<App />)

    expect(await screen.findByLabelText(/shipment reference number/i)).toBeInTheDocument()

    const refInput = screen.getByLabelText(/shipment reference number/i)
    fireEvent.change(refInput, { target: { value: 'NFPL-2026-FCL-0042' } })

    const goodsInput = screen.getByLabelText(/goods description/i)
    fireEvent.change(goodsInput, { target: { value: 'Automotive lithium battery packs' } })

    const submitBtn = screen.getByRole('button', { name: /create shipment/i })
    fireEvent.click(submitBtn)

    await waitFor(() => {
      expect(createdSubmitted).toBe(true)
      expect(screen.getByText(/Shipment Created/i)).toBeInTheDocument()
    })
  })

  it('Client Viewer views sanitized status and submits query', async () => {
    sessionStorage.setItem(
      'nfpl.auth.session',
      JSON.stringify({ token: 'test-token', expiresAt: new Date(Date.now() + 3600_000).toISOString() }),
    )

    let querySent = false

    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((url: string, init?: RequestInit) => {
        if (url.includes('/v1/identity/me')) {
          return Promise.resolve(jsonResponse(profile(['client-viewer'])))
        }
        if (url.includes('/v1/notifications')) {
          return Promise.resolve(jsonResponse([]))
        }
        if (url.includes('/v1/client/jobs/job-101/status')) {
          return Promise.resolve(
            jsonResponse({
              job_id: 'job-101',
              reference: 'NFPL-2026-AIR-001',
              stage: 'under_check',
              progress_percent: 50,
              updated_at: '2026-10-18T10:00:00Z',
              version: 1,
            }),
          )
        }
        if (url.includes('/v1/client/jobs/job-101/history')) {
          return Promise.resolve(jsonResponse([]))
        }
        if (url.includes('/v1/jobs/job-101') && (!init?.method || init.method === 'GET')) {
          return Promise.resolve(
            jsonResponse({
              id: 'job-101',
              reference: 'NFPL-2026-AIR-001',
              client_id: 'client-1',
              direction: 'import',
              mode: 'air',
              stage: 'under_check',
              version: 1,
            }),
          )
        }
        if (url.includes('/v1/client/jobs/job-101/queries') && init?.method === 'POST') {
          querySent = true
          return Promise.resolve(
            jsonResponse({
              job_id: 'job-101',
              recipient_user_id: 'admin-1',
              notification_id: 'notif-1',
              category: 'general_inquiry',
              dispatched_at: '2026-10-18T12:00:00Z',
            }),
          )
        }
        return Promise.reject(new Error(`Unhandled URL: ${url}`))
      }),
    )

    window.history.replaceState({}, '', '/client/shipments/job-101')
    render(<App />)

    const refs = await screen.findAllByText('NFPL-2026-AIR-001')
    expect(refs.length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText(/50% Complete/i)).toBeInTheDocument()

    // Send an inquiry
    const queryInput = screen.getByPlaceholderText(/explain your shipment inquiry/i)
    fireEvent.change(queryInput, { target: { value: 'When is customs clearance expected to conclude?' } })

    const sendBtn = screen.getByRole('button', { name: /send inquiry to admin/i })
    fireEvent.click(sendBtn)

    await waitFor(() => {
      expect(querySent).toBe(true)
    })
  })
})
