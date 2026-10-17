import { useEffect, useState } from 'react'

import { api } from '../api/client'
import type {
  ChecklistItem,
  ChecklistStatus,
  FilingReturnCategory,
  Job,
  OperationalHistoryItem,
} from '../api/contracts'
import { ConfirmationDialog } from './Controls'
import { ErrorMessage, InlineLoader } from './Feedback'

function checklist(job: Job): ChecklistItem[] | null {
  const items = job.checklist_data.items
  if (!Array.isArray(items)) return null
  const parsed: ChecklistItem[] = []
  for (const item of items) {
    if (
      typeof item !== 'object' ||
      item === null ||
      typeof item.key !== 'string' ||
      typeof item.label !== 'string' ||
      typeof item.required !== 'boolean'
    ) return null
    const status = item.status
    if (
      status !== null &&
      status !== 'complete' &&
      status !== 'incomplete' &&
      status !== 'not_applicable'
    ) return null
    parsed.push({
      key: item.key,
      label: item.label,
      required: item.required,
      status,
      justification: typeof item.justification === 'string' ? item.justification : null,
    })
  }
  return parsed
}

export function ChecklistSummary({ job }: { job: Job }) {
  const items = checklist(job)
  if (!items) {
    return <ErrorMessage title="Checklist unavailable" message="The checklist data is incomplete or inconsistent. No action is available." />
  }
  return (
    <div className="space-y-2">
      {items.map((item) => (
        <div className="rounded-xl border border-slate-200 p-3" key={item.key}>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm font-medium text-ink">{item.label}</p>
            <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold capitalize text-slate-700">
              {item.status?.replaceAll('_', ' ') ?? 'Pending'}
            </span>
          </div>
          {item.justification && <p className="mt-2 text-xs text-slate-600">{item.justification}</p>}
        </div>
      ))}
    </div>
  )
}

export function CheckerPanel({
  job,
  token,
  onUpdated,
  onMessage,
}: {
  job: Job
  token: string
  onUpdated: (job: Job) => void
  onMessage: (message: string, error?: boolean) => void
}) {
  const initial = checklist(job)
  const [items, setItems] = useState(initial ?? [])
  const [reason, setReason] = useState('')
  const [justification, setJustification] = useState('')
  const [confirm, setConfirm] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  if (!initial) return <ChecklistSummary job={job} />

  const incomplete = items.some((item) => item.status === 'incomplete')
  const decisionLabel = incomplete ? 'Return to Maker' : 'Approve verification'

  function setStatus(key: string, status: ChecklistStatus) {
    setItems((values) => values.map((item) => (
      item.key === key
        ? { ...item, status, justification: status === 'not_applicable' ? item.justification : null }
        : item
    )))
  }

  function setItemJustification(key: string, value: string) {
    setItems((values) => values.map((item) => (
      item.key === key ? { ...item, justification: value } : item
    )))
  }

  function validate(): string | null {
    if (items.some((item) => item.status === null)) {
      return 'Choose Complete, Incomplete, or Not Applicable for every checklist item.'
    }
    if (items.some((item) => item.status === 'not_applicable' && !item.justification?.trim())) {
      return 'Explain every Not Applicable decision.'
    }
    if (incomplete && !reason.trim()) {
      return 'Give the Maker actionable feedback for incomplete checklist items.'
    }
    if (job.checker_correction_required && !justification.trim()) {
      return 'Explain your reevaluation before submitting this checklist again.'
    }
    return null
  }

  function requestConfirmation() {
    const problem = validate()
    if (problem) {
      onMessage(problem, true)
      return
    }
    setConfirm(true)
  }

  async function submit() {
    setConfirm(false)
    setSubmitting(true)
    onMessage('')
    try {
      const updated = await api.checkJob(token, job.id, {
        expected_version: job.version,
        approved: !incomplete,
        reason: reason.trim(),
        checklist_items: items.map((item) => ({
          key: item.key,
          status: item.status!,
          justification: item.justification?.trim() || null,
        })),
        justification: justification.trim(),
      })
      onUpdated(updated)
      onMessage(incomplete
        ? 'Shipment returned to the Maker with correction feedback.'
        : 'Checklist independently verified and sent for filing.')
    } catch (caught) {
      onMessage(caught instanceof Error ? caught.message : 'Checklist submission failed.', true)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section className="summary-card mt-5">
      <h2 className="text-lg font-semibold">Verification checklist</h2>
      <p className="mt-1 text-sm text-slate-600">Review every generated {job.mode.toUpperCase()} / {job.direction} requirement independently.</p>
      <div className="mt-5 space-y-4">
        {items.map((item) => (
          <fieldset className="rounded-xl border border-slate-200 p-4" key={item.key}>
            <legend className="px-1 text-sm font-semibold text-ink">{item.label}</legend>
            <div className="mt-2 flex flex-wrap gap-4">
              {([
                ['complete', 'Complete'],
                ['incomplete', 'Incomplete'],
                ['not_applicable', 'Not Applicable'],
              ] as const).map(([value, label]) => (
                <label className="flex items-center gap-2 text-sm" key={value}>
                  <input
                    checked={item.status === value}
                    name={`checklist-${item.key}`}
                    onChange={() => setStatus(item.key, value)}
                    type="radio"
                  />
                  {label}
                </label>
              ))}
            </div>
            {item.status === 'not_applicable' && (
              <label className="form-label mt-3">
                Not Applicable justification
                <textarea
                  className="field mt-1 min-h-20"
                  value={item.justification ?? ''}
                  onChange={(event) => setItemJustification(item.key, event.target.value)}
                />
              </label>
            )}
          </fieldset>
        ))}
      </div>
      {incomplete && (
        <label className="form-label mt-5">
          Correction feedback for Maker
          <textarea className="field mt-1 min-h-24" value={reason} onChange={(event) => setReason(event.target.value)} />
        </label>
      )}
      {job.checker_correction_required && (
        <label className="form-label mt-5">
          Reevaluation justification
          <textarea
            className="field mt-1 min-h-24"
            value={justification}
            onChange={(event) => setJustification(event.target.value)}
            placeholder="Explain the reconsidered decision or why unchanged information remains correct."
          />
        </label>
      )}
      <button className={incomplete ? 'button-secondary mt-5' : 'button-primary mt-5'} disabled={submitting} onClick={requestConfirmation} type="button">
        {submitting ? 'Submitting...' : decisionLabel}
      </button>
      <ConfirmationDialog
        open={confirm}
        title={incomplete ? 'Return this shipment for correction?' : 'Approve this checklist?'}
        message={incomplete
          ? 'The shipment will return to the Maker with your written feedback.'
          : 'Your independent verification will make this revision available to Filing.'}
        confirmLabel={decisionLabel}
        dangerous={incomplete}
        onConfirm={() => void submit()}
        onCancel={() => setConfirm(false)}
      />
    </section>
  )
}

export function FilingPanel({
  job,
  token,
  onUpdated,
  onMessage,
}: {
  job: Job
  token: string
  onUpdated: (job: Job) => void
  onMessage: (message: string, error?: boolean) => void
}) {
  const [history, setHistory] = useState<OperationalHistoryItem[]>([])
  const [historyLoading, setHistoryLoading] = useState(true)
  const [historyError, setHistoryError] = useState('')
  const [category, setCategory] = useState<FilingReturnCategory>('maker_fault')
  const [reason, setReason] = useState('')
  const [confirmAction, setConfirmAction] = useState<'file' | 'return' | null>(null)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    let current = true
    api.operationalHistory(token, job.id)
      .then((result) => { if (current) setHistory(result) })
      .catch((caught: Error) => { if (current) setHistoryError(caught.message) })
      .finally(() => { if (current) setHistoryLoading(false) })
    return () => { current = false }
  }, [job.id, token])

  function requestReturn() {
    if (!reason.trim()) {
      onMessage('A written correction explanation is required.', true)
      return
    }
    setConfirmAction('return')
  }

  async function submit() {
    const action = confirmAction
    setConfirmAction(null)
    setSubmitting(true)
    onMessage('')
    try {
      const updated = action === 'file'
        ? await api.fileJob(token, job.id, job.version)
        : await api.returnForCorrection(token, job.id, job.version, category, reason.trim())
      onUpdated(updated)
      onMessage(action === 'file'
        ? 'Shipment filed successfully.'
        : 'Shipment returned to the selected responsible employee or employees.')
    } catch (caught) {
      onMessage(caught instanceof Error ? caught.message : 'Filing action failed.', true)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      <section className="summary-card mt-5">
        <h2 className="text-lg font-semibold">Approved checklist</h2>
        <div className="mt-4"><ChecklistSummary job={job} /></div>
        <div className="mt-5 flex flex-wrap gap-3">
          <button className="button-primary" disabled={submitting} onClick={() => setConfirmAction('file')} type="button">File shipment</button>
        </div>
      </section>
      <section className="summary-card mt-5">
        <h2 className="text-lg font-semibold">Return for correction</h2>
        <label className="form-label mt-4">
          Responsible area
          <select className="field mt-1" value={category} onChange={(event) => setCategory(event.target.value as FilingReturnCategory)}>
            <option value="maker_fault">Maker</option>
            <option value="checker_fault">Checker</option>
            <option value="both">Maker and Checker</option>
          </select>
        </label>
        <label className="form-label mt-4">
          Required explanation
          <textarea className="field mt-1 min-h-24" value={reason} onChange={(event) => setReason(event.target.value)} />
        </label>
        <button className="button-secondary mt-4" disabled={submitting} onClick={requestReturn} type="button">Return for correction</button>
      </section>
      <section className="summary-card mt-5">
        <h2 className="text-lg font-semibold">Operational history</h2>
        {historyError && <div className="mt-3"><ErrorMessage message={historyError} /></div>}
        {historyLoading ? <InlineLoader label="Loading operational history" /> : history.length === 0 ? (
          <p className="mt-3 text-sm text-slate-600">No operational history is available.</p>
        ) : (
          <ol className="mt-4 space-y-3">
            {history.map((item) => (
              <li className="border-l-2 border-teal-200 pl-4 text-sm" key={item.version_number}>
                <p className="font-medium text-ink">{item.action.replaceAll('_', ' ')}</p>
                <p className="text-slate-600">{item.reason}</p>
              </li>
            ))}
          </ol>
        )}
      </section>
      <ConfirmationDialog
        open={confirmAction !== null}
        title={confirmAction === 'file' ? 'File this shipment?' : 'Return this shipment?'}
        message={confirmAction === 'file'
          ? 'This records filing against the independently checked revision.'
          : 'The selected employee or employees will receive your correction explanation.'}
        confirmLabel={confirmAction === 'file' ? 'File shipment' : 'Return shipment'}
        dangerous={confirmAction === 'return'}
        onConfirm={() => void submit()}
        onCancel={() => setConfirmAction(null)}
      />
    </>
  )
}
