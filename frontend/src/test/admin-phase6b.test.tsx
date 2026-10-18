import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { App } from '../App'
import { jsonResponse, profile, role } from './fixtures'

const expiresAt = '2099-01-01T00:00:00Z'
const admin = profile(['admin'])
const references = {
  clients: [{ id: 'client-1', code: 'ACME', name: 'Acme Imports' }],
  branches: [{ id: 'branch-1', code: 'MUM', name: 'Mumbai' }],
}
const job = {
  id: 'job-1',
  reference: 'NFPL-104',
  client_id: 'client-1',
  branch_id: 'branch-1',
  direction: 'import',
  mode: 'air',
  stage: 'confirmed',
  goods_description: 'Machine parts',
  container_reference: null,
  version: 1,
}

function storeAdminSession(): void {
  sessionStorage.setItem(
    'nfpl.auth.session',
    JSON.stringify({ token: 'admin-session', expiresAt }),
  )
}

function method(options?: RequestInit): string {
  return options?.method ?? 'GET'
}

describe('Phase 6B Admin workflows', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    sessionStorage.clear()
    storeAdminSession()
  })

  it('creates a job using human-readable client and branch selections', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, options) => {
      const url = String(input)
      if (url.endsWith('/v1/identity/me')) return jsonResponse(admin)
      if (url.endsWith('/v1/admin/reference-data')) return jsonResponse(references)
      if (url.endsWith('/v1/jobs') && method(options) === 'POST') return jsonResponse(job, 201)
      if (url.includes('/assignment-suggestions')) {
        return jsonResponse({ maker: [], checker: [], filing_officer: [] })
      }
      throw new Error(`Unexpected request: ${method(options)} ${url}`)
    })
    window.history.replaceState({}, '', '/admin/jobs/new')
    render(<App />)

    await userEvent.type(await screen.findByLabelText('Shipment reference'), 'NFPL-104')
    await userEvent.selectOptions(screen.getByLabelText('Client'), 'client-1')
    await userEvent.selectOptions(screen.getByLabelText('Branch'), 'branch-1')
    await userEvent.type(screen.getByLabelText('Goods description'), 'Machine parts')
    await userEvent.click(screen.getByRole('button', { name: 'Create and show assignments' }))

    expect(await screen.findByText('Assignment & reallocation')).toBeInTheDocument()
    const call = fetchMock.mock.calls.find(([url, options]) => String(url).endsWith('/v1/jobs') && method(options) === 'POST')
    expect(call).toBeDefined()
    expect(JSON.parse(String(call?.[1]?.body))).toMatchObject({
      client_id: 'client-1',
      branch_id: 'branch-1',
      reference: 'NFPL-104',
    })
  })

  it('submits scoped role grants and refreshes the employee directory', async () => {
    let employeeLoads = 0
    const employee = profile([], { id: 'employee-2', display_name: 'Asha Rao' })
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, options) => {
      const url = String(input)
      if (url.endsWith('/v1/identity/me')) return jsonResponse(admin)
      if (url.includes('/v1/admin/employees?')) {
        employeeLoads += 1
        return jsonResponse({ items: [employee], total: 1, page: 1, limit: 25 })
      }
      if (url.endsWith('/v1/admin/reference-data')) return jsonResponse(references)
      if (url.endsWith('/v1/admin/role-assignments') && method(options) === 'POST') {
        return jsonResponse({ id: 'grant-1' }, 201)
      }
      throw new Error(`Unexpected request: ${method(options)} ${url}`)
    })
    window.history.replaceState({}, '', '/admin/employees')
    render(<App />)

    await screen.findByText('Asha Rao')
    await userEvent.selectOptions(screen.getByLabelText('Role'), 'checker')
    await userEvent.selectOptions(screen.getByLabelText('Client scope'), 'client-1')
    await userEvent.selectOptions(screen.getByLabelText('Branch scope'), 'branch-1')
    await userEvent.selectOptions(screen.getByLabelText('Direction scope'), 'import')
    await userEvent.selectOptions(screen.getByLabelText('Mode scope'), 'air')
    await userEvent.type(screen.getByLabelText('Role grant reason'), 'Qualified for this lane')
    await userEvent.click(screen.getByRole('button', { name: 'Grant scoped role' }))

    expect(await screen.findByText('Scoped role granted.')).toBeInTheDocument()
    expect(employeeLoads).toBeGreaterThan(1)
    const call = fetchMock.mock.calls.find(([url, options]) => String(url).endsWith('/v1/admin/role-assignments') && method(options) === 'POST')
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({
      target_user_id: 'employee-2',
      role_slug: 'checker',
      reason: 'Qualified for this lane',
      scope: {
        all_clients: false,
        client_id: 'client-1',
        all_branches: false,
        branch_id: 'branch-1',
        all_directions: false,
        direction: 'import',
        all_modes: false,
        mode: 'air',
      },
    })
  })

  it('prevents an identical active role grant and guides the Admin', async () => {
    const employee = profile([], {
      id: 'employee-2',
      display_name: 'Asha Rao',
      roles: [role('maker', { id: 'existing-maker-grant' })],
    })
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input)
      if (url.endsWith('/v1/identity/me')) return jsonResponse(admin)
      if (url.includes('/v1/admin/employees?')) return jsonResponse({ items: [employee], total: 1, page: 1, limit: 25 })
      if (url.endsWith('/v1/admin/reference-data')) return jsonResponse(references)
      throw new Error(`Unexpected request: ${url}`)
    })
    window.history.replaceState({}, '', '/admin/employees')
    render(<App />)

    await screen.findByText('Asha Rao')
    await userEvent.type(screen.getByLabelText('Role grant reason'), 'Duplicate role')
    await userEvent.click(screen.getByRole('button', { name: 'Grant scoped role' }))

    expect(await screen.findByText(/already has the same active role and scope/i)).toBeInTheDocument()
    expect(screen.getByText(/different scope, or revoke the existing assignment/i)).toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/v1/admin/role-assignments'))).toBe(false)
  })

  it('reloads assignment suggestions after a conflict and preserves its explanation', async () => {
    let suggestionLoads = 0
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, options) => {
      const url = String(input)
      if (url.endsWith('/v1/identity/me')) return jsonResponse(admin)
      if (url.endsWith('/v1/admin/reference-data')) return jsonResponse(references)
      if (url.endsWith('/v1/jobs') && method(options) === 'POST') return jsonResponse(job, 201)
      if (url.includes('/assignment-suggestions')) {
        suggestionLoads += 1
        return jsonResponse({
          maker: [{ responsibility: 'maker', user_id: 'maker-1', display_name: 'Maya Maker', pending_workload: 1 }],
          checker: [],
          filing_officer: [],
        })
      }
      if (url.endsWith('/assignment') && method(options) === 'PUT') {
        return jsonResponse({ detail: 'The responsibility changed concurrently.' }, 409)
      }
      throw new Error(`Unexpected request: ${method(options)} ${url}`)
    })
    window.history.replaceState({}, '', '/admin/jobs/new')
    render(<App />)

    await userEvent.type(await screen.findByLabelText('Shipment reference'), 'NFPL-104')
    await userEvent.selectOptions(screen.getByLabelText('Client'), 'client-1')
    await userEvent.selectOptions(screen.getByLabelText('Branch'), 'branch-1')
    await userEvent.click(screen.getByRole('button', { name: 'Create and show assignments' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Maya Maker (1)' }))

    expect(await screen.findByText(/responsibility changed concurrently/i)).toBeInTheDocument()
    expect(screen.getByText(/reloaded suggestions are shown/i)).toBeInTheDocument()
    await waitFor(() => expect(suggestionLoads).toBeGreaterThan(1))
  })

  it('lists searchable paginated jobs and opens selected audit history', async () => {
    const jobs = Array.from({ length: 25 }, (_, index) => ({
      ...job,
      id: `job-${index + 1}`,
      reference: `NFPL-${String(index + 1).padStart(3, '0')}`,
      maker_user_id: null,
      checker_user_id: null,
      filing_officer_user_id: null,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-02T00:00:00Z',
      archived_at: null,
    }))
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input)
      if (url.endsWith('/v1/identity/me')) return jsonResponse(admin)
      if (url.includes('/v1/admin/jobs?')) return jsonResponse(jobs)
      if (url.endsWith('/v1/jobs/job-1')) return jsonResponse({ ...job, id: 'job-1', reference: 'NFPL-001' })
      if (url.endsWith('/v1/admin/jobs/job-1/audit')) {
        return jsonResponse([{
          id: 'audit-1', job_id: 'job-1', actor_user_id: 'admin-1',
          actor_display_name: 'Morgan Lee',
          action: 'job.created', occurred_at: '2026-01-01T00:00:00Z',
          reason: 'Shipment created.', before_state: null, after_state: { stage: 'confirmed' },
          authorization_context: {}, affected_job_version: 1, denied: false,
        }])
      }
      throw new Error(`Unexpected request: ${url}`)
    })
    window.history.replaceState({}, '', '/admin/audit')
    render(<App />)

    expect(await screen.findByText('NFPL-001')).toBeInTheDocument()
    await userEvent.click(screen.getAllByRole('link', { name: 'View timeline' })[0])
    expect(await screen.findByText('Immutable audit timeline')).toBeInTheDocument()
    expect(screen.getByText('Shipment created.')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('link', { name: /back to audit history/i }))
    await userEvent.type(screen.getByLabelText('Search audit jobs'), '104')
    await waitFor(() => expect(fetchMock.mock.calls.some(([url]) => String(url).includes('search=104'))).toBe(true))
    await userEvent.click(screen.getByRole('button', { name: 'Next' }))
    await waitFor(() => expect(fetchMock.mock.calls.some(([url]) => String(url).includes('offset=25'))).toBe(true))
  })

  it('requires a reason and confirmation before revoking a role assignment', async () => {
    const assignment = role('maker', { id: 'grant-1' })
    const employee = profile([], { id: 'employee-2', roles: [assignment] })
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, options) => {
      const url = String(input)
      if (url.endsWith('/v1/identity/me')) return jsonResponse(admin)
      if (url.includes('/v1/admin/employees?')) return jsonResponse({ items: [employee], total: 1, page: 1, limit: 25 })
      if (url.endsWith('/v1/admin/reference-data')) return jsonResponse(references)
      if (url.endsWith('/v1/admin/role-assignments/grant-1/revoke')) return jsonResponse({ id: 'grant-1', revoked_at: '2026-01-01T00:00:00Z' })
      throw new Error(`Unexpected request: ${method(options)} ${url}`)
    })
    window.history.replaceState({}, '', '/admin/employees')
    render(<App />)

    await userEvent.click(await screen.findByRole('button', { name: 'Revoke' }))
    await userEvent.type(screen.getByLabelText('Revocation reason'), 'Scope no longer required')
    await userEvent.click(screen.getByRole('button', { name: 'Review revocation' }))
    const dialog = screen.getByRole('dialog', { name: 'Revoke this scoped role?' })
    await userEvent.click(within(dialog).getByRole('button', { name: 'Revoke role' }))

    expect(await screen.findByText('Role assignment revoked.')).toBeInTheDocument()
    const call = fetchMock.mock.calls.find(([url]) => String(url).endsWith('/grant-1/revoke'))
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({ reason: 'Scope no longer required' })
  })

  it('uses request versions and shows a stale-decision response', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, options) => {
      const url = String(input)
      if (url.endsWith('/v1/identity/me')) return jsonResponse(admin)
      if (url.endsWith('/v1/admin/dashboard/urgent-requests') && method(options) === 'GET') {
        return jsonResponse([{
          request_type: 'edit_request',
          request_id: 'request-1',
          requested_at: '2026-01-01T00:00:00Z',
          requester_user_id: 'employee-2',
          reason: 'Correct reference',
          job_id: 'job-1',
          version: 4,
        }])
      }
      if (url.endsWith('/v1/admin/edit-requests/request-1/decision')) {
        return jsonResponse({ detail: 'The operation conflicts with current state.' }, 409)
      }
      throw new Error(`Unexpected request: ${method(options)} ${url}`)
    })
    window.history.replaceState({}, '', '/admin/requests')
    render(<App />)

    await userEvent.click(await screen.findByRole('button', { name: 'Approve' }))
    await userEvent.type(screen.getByLabelText('Decision reason'), 'Independent review')
    await userEvent.click(screen.getByRole('button', { name: 'Confirm approval' }))
    expect(await screen.findByText('The operation conflicts with current state.')).toBeInTheDocument()
  })

  it('cancels a non-filed job using its optimistic version', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, options) => {
      const url = String(input)
      if (url.endsWith('/v1/identity/me')) return jsonResponse(admin)
      if (url.endsWith('/v1/jobs/job-1') && method(options) === 'GET') return jsonResponse(job)
      if (url.endsWith('/v1/jobs/job-1/cancel')) return jsonResponse({ ...job, stage: 'cancelled', version: 2 })
      throw new Error(`Unexpected request: ${method(options)} ${url}`)
    })
    window.history.replaceState({}, '', '/admin/jobs/job-1')
    render(<App />)

    await userEvent.type(await screen.findByLabelText('Required reason'), 'Duplicate shipment')
    await userEvent.click(await screen.findByRole('button', { name: 'Cancel shipment' }))
    await screen.findByText('Shipment cancelled and audited.')
    const call = fetchMock.mock.calls.find(([url]) => String(url).endsWith('/v1/jobs/job-1/cancel'))
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({ expected_version: 1, reason: 'Duplicate shipment' })
  })

  it('archives from All Jobs and preserves authorization failures', async () => {
    const listedJob = {
      ...job,
      maker_user_id: null,
      checker_user_id: null,
      filing_officer_user_id: null,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
      archived_at: null,
    }
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, options) => {
      const url = String(input)
      if (url.endsWith('/v1/identity/me')) return jsonResponse(admin)
      if (url.includes('/v1/admin/jobs?')) return jsonResponse([listedJob])
      if (url.endsWith('/v1/admin/jobs/job-1/archive')) {
        return jsonResponse({ detail: { reason_code: 'missing_permission', explanation: 'Admin scope does not include this shipment.' } }, 403)
      }
      throw new Error(`Unexpected request: ${method(options)} ${url}`)
    })
    const alert = vi.spyOn(window, 'alert').mockImplementation(() => undefined)
    window.history.replaceState({}, '', '/admin/jobs')
    render(<App />)

    await userEvent.click(await screen.findByRole('button', { name: 'Archive' }))
    await userEvent.type(screen.getByPlaceholderText('Required archive reason'), 'Retention complete')
    await userEvent.click(screen.getByRole('button', { name: 'Confirm archive' }))

    await waitFor(() => expect(alert).toHaveBeenCalledWith('Admin scope does not include this shipment.'))
  })
})
