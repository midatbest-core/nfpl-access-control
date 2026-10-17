import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { App } from '../App'
import type { Job } from '../api/contracts'
import { jsonResponse, profile } from './fixtures'

const expiresAt = '2099-01-01T00:00:00Z'

function storedSession(): void {
  sessionStorage.setItem(
    'nfpl.auth.session',
    JSON.stringify({ token: 'phase6-session', expiresAt }),
  )
}

function requestMethod(options?: RequestInit): string {
  return options?.method ?? 'GET'
}

function job(overrides: Partial<Job> = {}): Job {
  return {
    id: 'job-6',
    reference: 'NFPL-600',
    client_id: 'client-1',
    client_name: 'Acme Imports',
    branch_id: 'branch-1',
    branch_name: 'Head Office',
    direction: 'export',
    mode: 'fcl',
    stage: 'prepared',
    goods_description: 'Machinery parts',
    container_reference: 'CONT-600',
    checklist_data: {
      revision: 1,
      mode: 'fcl',
      direction: 'export',
      items: [
        { key: 'commercial_invoice', label: 'Commercial invoice matches shipment details', required: true, status: null, justification: null },
        { key: 'packing_list', label: 'Packing list is present and consistent', required: true, status: null, justification: null },
        { key: 'bill_of_lading', label: 'Bill of lading details are verified', required: true, status: null, justification: null },
        { key: 'container_reference', label: 'Container and seal references are verified', required: true, status: null, justification: null },
        { key: 'export_requirements', label: 'Export permits and departure requirements are verified', required: true, status: null, justification: null },
      ],
    },
    checklist_revision: 1,
    maker_edit_locked: true,
    maker_correction_required: false,
    checker_correction_required: false,
    last_return_category: null,
    last_return_reason: null,
    last_maker_justification: null,
    last_checker_justification: null,
    prepared_by_user_id: 'maker-1',
    checked_by_user_id: null,
    filed_by_user_id: null,
    version: 3,
    ...overrides,
  }
}

const checkerResponsibilities = [{
  responsibility: 'checker',
  user_id: 'user-1',
  display_name: 'Morgan Lee',
  current_actor_responsible: true,
  via_delegation: false,
}]

const filingResponsibilities = [{
  responsibility: 'filing_officer',
  user_id: 'user-1',
  display_name: 'Morgan Lee',
  current_actor_responsible: true,
  via_delegation: false,
}]

function checkerMock(current: Job, checkResponse?: Response) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, options) => {
    const url = String(input)
    if (url.endsWith('/v1/identity/me')) return jsonResponse(profile(['checker']))
    if (url.endsWith('/responsibilities')) return jsonResponse(checkerResponsibilities)
    if (url.endsWith('/v1/jobs/job-6') && requestMethod(options) === 'GET') return jsonResponse(current)
    if (url.endsWith('/v1/jobs/job-6/check')) {
      return checkResponse ?? jsonResponse(job({
        stage: 'checked',
        checked_by_user_id: 'user-1',
        version: current.version + 1,
      }))
    }
    throw new Error(`Unexpected request: ${requestMethod(options)} ${url}`)
  })
}

async function completeAllItems() {
  const choices = await screen.findAllByLabelText('Complete')
  for (const choice of choices) await userEvent.click(choice)
}

describe('Phase 6 Checker workflow', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    sessionStorage.clear()
    storedSession()
    window.history.replaceState({}, '', '/work/jobs/job-6')
  })

  it('submits the generated mode/direction checklist with justified N/A', async () => {
    const fetchMock = checkerMock(job())
    render(<App />)

    await completeAllItems()
    const containerFieldset = screen.getByText('Container and seal references are verified').closest('fieldset')
    expect(containerFieldset).not.toBeNull()
    await userEvent.click(within(containerFieldset!).getByLabelText('Not Applicable'))
    await userEvent.type(within(containerFieldset!).getByLabelText('Not Applicable justification'), 'Seal is not issued for this booking.')
    await userEvent.click(screen.getByRole('button', { name: 'Approve verification' }))
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Approve verification' }))

    expect(await screen.findByText('Checklist independently verified and sent for filing.')).toBeInTheDocument()
    const call = fetchMock.mock.calls.find(([url]) => String(url).endsWith('/check'))
    const body = JSON.parse(String(call?.[1]?.body))
    expect(body.expected_version).toBe(3)
    expect(body.approved).toBe(true)
    expect(body.checklist_items).toHaveLength(5)
    expect(body.checklist_items).toContainEqual({
      key: 'container_reference',
      status: 'not_applicable',
      justification: 'Seal is not issued for this booking.',
    })
  })

  it('requires N/A justification and actionable feedback before returning work', async () => {
    const fetchMock = checkerMock(job())
    render(<App />)

    await completeAllItems()
    const invoiceFieldset = screen.getByText('Commercial invoice matches shipment details').closest('fieldset')
    await userEvent.click(within(invoiceFieldset!).getByLabelText('Not Applicable'))
    await userEvent.click(screen.getByRole('button', { name: 'Approve verification' }))
    expect(await screen.findByText('Explain every Not Applicable decision.')).toBeInTheDocument()

    await userEvent.click(within(invoiceFieldset!).getByLabelText('Incomplete'))
    await userEvent.click(screen.getByRole('button', { name: 'Return to Maker' }))
    expect(await screen.findByText('Give the Maker actionable feedback for incomplete checklist items.')).toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/check'))).toBe(false)

    await userEvent.type(screen.getByLabelText('Correction feedback for Maker'), 'Invoice total does not match the shipment.')
    await userEvent.click(screen.getByRole('button', { name: 'Return to Maker' }))
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Return to Maker' }))
    const call = fetchMock.mock.calls.find(([url]) => String(url).endsWith('/check'))
    expect(JSON.parse(String(call?.[1]?.body))).toMatchObject({
      approved: false,
      reason: 'Invoice total does not match the shipment.',
    })
  })

  it('requires reevaluation justification and surfaces backend self-check denial', async () => {
    const current = job({ checker_correction_required: true, last_return_reason: 'Recheck the N/A evidence.' })
    checkerMock(
      current,
      jsonResponse({
        detail: {
          reason_code: 'self_check_forbidden',
          explanation: 'You cannot verify a checklist revision that you prepared.',
        },
      }, 403),
    )
    render(<App />)

    await completeAllItems()
    await userEvent.click(screen.getByRole('button', { name: 'Approve verification' }))
    expect(await screen.findByText('Explain your reevaluation before submitting this checklist again.')).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText('Reevaluation justification'), 'Reviewed the disputed evidence again.')
    await userEvent.click(screen.getByRole('button', { name: 'Approve verification' }))
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Approve verification' }))
    expect(await screen.findByText('You cannot verify a checklist revision that you prepared.')).toBeInTheDocument()
  })
})

describe('Phase 6 Filing Officer workflow', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    sessionStorage.clear()
    storedSession()
    window.history.replaceState({}, '', '/work/jobs/job-6')
  })

  function filingMock() {
    const checked = job({
      stage: 'checked',
      checked_by_user_id: 'checker-1',
      version: 4,
      checklist_data: {
        revision: 1,
        mode: 'fcl',
        direction: 'export',
        items: [
          { key: 'commercial_invoice', label: 'Commercial invoice matches shipment details', required: true, status: 'complete', justification: null },
          { key: 'packing_list', label: 'Packing list is present and consistent', required: true, status: 'complete', justification: null },
        ],
      },
    })
    return vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, options) => {
      const url = String(input)
      if (url.endsWith('/v1/identity/me')) return jsonResponse(profile(['filing-officer']))
      if (url.endsWith('/responsibilities')) return jsonResponse(filingResponsibilities)
      if (url.endsWith('/v1/jobs/job-6') && requestMethod(options) === 'GET') return jsonResponse(checked)
      if (url.includes('/operational-history')) return jsonResponse([{
        version_number: 4,
        occurred_at: '2026-10-17T10:00:00Z',
        actor_user_id: 'checker-1',
        action: 'job.checked',
        reason: 'Checklist verified.',
        stage: 'checked',
        changed_fields: ['stage'],
      }])
      if (url.endsWith('/file')) return jsonResponse({ ...checked, stage: 'filed', version: 5 })
      if (url.endsWith('/return-for-correction')) return jsonResponse({ ...checked, stage: 'confirmed', version: 5 })
      throw new Error(`Unexpected request: ${requestMethod(options)} ${url}`)
    })
  }

  it('reviews the approved checklist and files the optimistic version', async () => {
    const fetchMock = filingMock()
    render(<App />)

    expect(await screen.findByText('Approved checklist')).toBeInTheDocument()
    expect(await screen.findByText('Checklist verified.')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'File shipment' }))
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'File shipment' }))
    expect(await screen.findByText('Shipment filed successfully.')).toBeInTheDocument()
    const call = fetchMock.mock.calls.find(([url]) => String(url).endsWith('/file'))
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({ expected_version: 4 })
  })

  it('requires an explanation and submits a categorized return', async () => {
    const fetchMock = filingMock()
    render(<App />)

    await screen.findByText('Approved checklist')
    await userEvent.selectOptions(screen.getByLabelText('Responsible area'), 'both')
    await userEvent.click(screen.getByRole('button', { name: 'Return for correction' }))
    expect(await screen.findByText('A written correction explanation is required.')).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText('Required explanation'), 'Shipment description and N/A evidence both need correction.')
    await userEvent.click(screen.getByRole('button', { name: 'Return for correction' }))
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Return shipment' }))
    const call = fetchMock.mock.calls.find(([url]) => String(url).endsWith('/return-for-correction'))
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({
      expected_version: 4,
      category: 'both',
      reason: 'Shipment description and N/A evidence both need correction.',
    })
  })
})

describe('Phase 6 Client Viewer workflow', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    sessionStorage.clear()
    storedSession()
  })

  it('lists only client-safe shipments and opens sanitized status/history', async () => {
    const client = profile(['client-viewer'], { kind: 'client' })
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input)
      if (url.endsWith('/v1/identity/me')) return jsonResponse(client)
      if (url.includes('/v1/client/jobs?')) return jsonResponse({
        items: [{
          job_id: 'job-client',
          reference: 'CLIENT-101',
          direction: 'import',
          mode: 'air',
          stage: 'checked',
          progress_percent: 75,
          updated_at: '2026-10-17T10:00:00Z',
          version: 3,
        }],
        next_cursor: null,
      })
      if (url.endsWith('/v1/jobs/job-client')) return jsonResponse({
        id: 'job-client',
        reference: 'CLIENT-101',
        client_id: 'client-1',
        direction: 'import',
        mode: 'air',
        stage: 'checked',
        version: 3,
      })
      if (url.endsWith('/v1/client/jobs/job-client/status')) return jsonResponse({
        job_id: 'job-client',
        reference: 'CLIENT-101',
        stage: 'checked',
        progress_percent: 75,
        updated_at: '2026-10-17T10:00:00Z',
        version: 3,
      })
      if (url.includes('/v1/client/jobs/job-client/history?')) return jsonResponse([{
        cursor: 'history-1',
        job_id: 'job-client',
        reference: 'CLIENT-101',
        stage: 'checked',
        progress_percent: 75,
        message: 'Shipment checked',
        occurred_at: '2026-10-17T10:00:00Z',
        version: 3,
      }])
      throw new Error(`Unexpected request: ${url}`)
    })
    window.history.replaceState({}, '', '/client/shipments')
    render(<App />)

    expect(await screen.findByText('CLIENT-101')).toBeInTheDocument()
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '75')
    await userEvent.click(screen.getByRole('link', { name: 'CLIENT-101' }))
    expect(await screen.findByText('Shipment checked')).toBeInTheDocument()
    expect(screen.getByText('This view contains client-safe status and progress only.')).toBeInTheDocument()
    expect(screen.queryByText(/actor_user_id/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/checklist/i)).not.toBeInTheDocument()
  })

  it('shows isolated access errors without rendering another client shipment', async () => {
    const client = profile(['client-viewer'], { kind: 'client' })
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input)
      if (url.endsWith('/v1/identity/me')) return jsonResponse(client)
      if (url.includes('/v1/client/jobs?')) {
        return jsonResponse({ detail: 'Client Viewer access required' }, 403)
      }
      throw new Error(`Unexpected request: ${url}`)
    })
    window.history.replaceState({}, '', '/client/shipments')
    render(<App />)

    expect(await screen.findByText('Client Viewer access required')).toBeInTheDocument()
    expect(screen.queryByText('CLIENT-101')).not.toBeInTheDocument()
  })
})
