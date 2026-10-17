import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { api } from '../api/client'
import type {
  ClientJobDetail,
  ClientShipmentPage,
  ClientShipmentStatus,
  ClientUpdate,
  ClientUpdatePage,
} from '../api/contracts'
import { useAuth } from '../auth/AuthContext'
import { PageHeader } from '../components/AppShell'
import { EmptyState, ErrorMessage, InlineLoader } from '../components/Feedback'
import { StatusBadge } from '../components/StatusBadge'

const displayDate = (value: string) => new Date(value).toLocaleString()

function Progress({ percent }: { percent: number }) {
  return (
    <div>
      <div className="mb-1 flex justify-between text-xs text-slate-600">
        <span>Shipment progress</span><span>{percent}%</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-slate-100" role="progressbar" aria-label="Shipment progress" aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent}>
        <div className="h-full rounded-full bg-teal-600" style={{ width: `${percent}%` }} />
      </div>
    </div>
  )
}

export function ClientShipmentsPage() {
  const { token } = useAuth()
  const [data, setData] = useState<ClientShipmentPage>()
  const [cursor, setCursor] = useState<string>()
  const [stack, setStack] = useState<Array<string | undefined>>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let current = true
    api.clientJobs(token!, cursor)
      .then((result) => { if (current) setData(result) })
      .catch((caught: Error) => { if (current) setError(caught.message) })
      .finally(() => { if (current) setLoading(false) })
    return () => { current = false }
  }, [cursor, token])

  return (
    <div>
      <PageHeader eyebrow="Client workspace" title="My shipments" description="Track current progress for shipments belonging to your authorized client account." />
      {error && <ErrorMessage message={error} />}
      {loading ? <InlineLoader label="Loading your shipments" /> : data?.items.length ? (
        <>
          <div className="grid gap-4 md:grid-cols-2">
            {data.items.map((item) => (
              <article className="summary-card" key={item.job_id}>
                <div className="flex items-center justify-between gap-3">
                  <Link className="font-semibold text-teal-700" to={`/client/shipments/${item.job_id}`}>{item.reference}</Link>
                  <StatusBadge status={item.stage} />
                </div>
                <p className="mt-2 text-xs uppercase tracking-wide text-slate-500">{item.direction} / {item.mode}</p>
                <div className="mt-4"><Progress percent={item.progress_percent} /></div>
                <p className="mt-3 text-xs text-slate-500">Updated {displayDate(item.updated_at)}</p>
              </article>
            ))}
          </div>
          <nav className="mt-5 flex justify-between" aria-label="Shipment pagination">
            <button className="button-secondary" disabled={stack.length === 0} onClick={() => {
              const previous = stack.at(-1)
              setLoading(true)
              setError('')
              setStack((values) => values.slice(0, -1))
              setCursor(previous)
            }}>Previous</button>
            <button className="button-secondary" disabled={!data.next_cursor} onClick={() => {
              if (!data.next_cursor) return
              setLoading(true)
              setError('')
              setStack((values) => [...values, cursor])
              setCursor(data.next_cursor ?? undefined)
            }}>Next</button>
          </nav>
        </>
      ) : !loading && !error ? (
        <EmptyState title="No shipments available" message="No shipments are currently visible for your client account." />
      ) : null}
    </div>
  )
}

export function ClientShipmentDetailPage() {
  const { jobId = '' } = useParams()
  const { token } = useAuth()
  const [detail, setDetail] = useState<ClientJobDetail>()
  const [status, setStatus] = useState<ClientShipmentStatus>()
  const [history, setHistory] = useState<ClientUpdate[]>([])
  const [beforeVersion, setBeforeVersion] = useState<number>()
  const [historyStack, setHistoryStack] = useState<Array<number | undefined>>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let current = true
    Promise.all([
      api.clientJob(token!, jobId),
      api.clientStatus(token!, jobId),
      api.clientHistory(token!, jobId, beforeVersion),
    ])
      .then(([job, shipmentStatus, items]) => {
        if (!current) return
        setDetail(job)
        setStatus(shipmentStatus)
        setHistory(items)
      })
      .catch((caught: Error) => { if (current) setError(caught.message) })
      .finally(() => { if (current) setLoading(false) })
    return () => { current = false }
  }, [beforeVersion, jobId, token])

  if (loading) return <InlineLoader label="Loading shipment status" />
  if (!detail || !status) {
    return <div><PageHeader eyebrow="Client workspace" title="Shipment unavailable" description="This shipment is not available to your client account." />{error && <ErrorMessage message={error} />}</div>
  }
  return (
    <div>
      <PageHeader eyebrow="Client shipment" title={detail.reference} description="This view contains client-safe status and progress only." action={<Link className="button-secondary" to="/client/shipments">Back to shipments</Link>} />
      {error && <ErrorMessage message={error} />}
      <section className="grid gap-4 md:grid-cols-3">
        <div className="summary-card"><p className="summary-label">Status</p><div className="mt-2"><StatusBadge status={status.stage} /></div></div>
        <div className="summary-card"><p className="summary-label">Shipment type</p><p className="mt-2 text-sm font-semibold uppercase">{detail.direction} / {detail.mode}</p></div>
        <div className="summary-card"><p className="summary-label">Last updated</p><p className="mt-2 text-sm">{displayDate(status.updated_at)}</p></div>
      </section>
      <section className="summary-card mt-5"><Progress percent={status.progress_percent} /></section>
      <section className="summary-card mt-5">
        <h2 className="text-lg font-semibold">Shipment history</h2>
        {history.length === 0 ? <p className="mt-3 text-sm text-slate-600">No client-visible updates are available.</p> : (
          <ol className="mt-4 space-y-4">
            {history.map((item) => (
              <li className="border-l-2 border-teal-200 pl-4" key={item.cursor}>
                <div className="flex flex-wrap items-center gap-2"><p className="text-sm font-semibold">{item.message}</p><StatusBadge status={item.stage} /></div>
                <p className="mt-1 text-xs text-slate-500">{displayDate(item.occurred_at)}</p>
              </li>
            ))}
          </ol>
        )}
        <nav className="mt-5 flex justify-between" aria-label="Shipment history pagination">
          <button className="button-secondary" disabled={historyStack.length === 0} onClick={() => {
            const previous = historyStack.at(-1)
            setLoading(true)
            setError('')
            setHistoryStack((values) => values.slice(0, -1))
            setBeforeVersion(previous)
          }}>Newer</button>
          <button className="button-secondary" disabled={history.length < 25} onClick={() => {
            const last = history.at(-1)
            if (!last) return
            setLoading(true)
            setError('')
            setHistoryStack((values) => [...values, beforeVersion])
            setBeforeVersion(last.version)
          }}>Older</button>
        </nav>
      </section>
    </div>
  )
}

export function ClientUpdatesPage() {
  const { token } = useAuth()
  const [data, setData] = useState<ClientUpdatePage>()
  const [cursor, setCursor] = useState<string>()
  const [stack, setStack] = useState<Array<string | undefined>>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let current = true
    api.clientUpdates(token!, cursor)
      .then((result) => { if (current) setData(result) })
      .catch((caught: Error) => { if (current) setError(caught.message) })
      .finally(() => { if (current) setLoading(false) })
    return () => { current = false }
  }, [cursor, token])

  return (
    <div>
      <PageHeader eyebrow="Client workspace" title="Recent updates" description="Client-safe shipment milestones, fetched incrementally without exposing internal audit details." />
      {error && <ErrorMessage message={error} />}
      {loading ? <InlineLoader label="Loading shipment updates" /> : data?.items.length ? (
        <>
          <div className="space-y-3">
            {data.items.map((item) => (
              <article className="summary-card" key={item.cursor}>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <Link className="font-semibold text-teal-700" to={`/client/shipments/${item.job_id}`}>{item.reference}</Link>
                  <StatusBadge status={item.stage} />
                </div>
                <p className="mt-2 text-sm text-slate-700">{item.message}</p>
                <p className="mt-2 text-xs text-slate-500">{displayDate(item.occurred_at)}</p>
              </article>
            ))}
          </div>
          <nav className="mt-5 flex justify-between" aria-label="Update pagination">
            <button className="button-secondary" disabled={stack.length === 0} onClick={() => {
              const previous = stack.at(-1)
              setLoading(true)
              setError('')
              setStack((values) => values.slice(0, -1))
              setCursor(previous)
            }}>Previous</button>
            <button className="button-secondary" disabled={!data.next_cursor} onClick={() => {
              if (!data.next_cursor) return
              setLoading(true)
              setError('')
              setStack((values) => [...values, cursor])
              setCursor(data.next_cursor ?? undefined)
            }}>Next</button>
          </nav>
        </>
      ) : !loading && !error ? (
        <EmptyState title="No recent updates" message="There are no new client-visible shipment updates." />
      ) : null}
    </div>
  )
}
