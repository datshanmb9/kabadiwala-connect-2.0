import type { ReactNode } from 'react'

export function LoadingView({ message }: { message?: string }) {
  return (
    <div className="state-view" role="status">
      <div className="spinner" />
      {message && <p>{message}</p>}
    </div>
  )
}

export function EmptyView({ message }: { message: string }) {
  return (
    <div className="state-view state-view-empty">
      <p>{message}</p>
    </div>
  )
}

export function ErrorView({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="state-view state-view-error">
      <p>{message}</p>
      {onRetry && (
        <button type="button" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  )
}

export function InlineErrorBanner({ message }: { message: string }) {
  return (
    <div className="inline-error-banner" role="alert">
      {message}
    </div>
  )
}

export function Card({ children }: { children: ReactNode }) {
  return <div className="card">{children}</div>
}

export function StatusBadge({ status }: { status: string }) {
  const tone = statusTone(status)
  return <span className={`status-badge status-badge-${tone}`}>{status.replaceAll('_', ' ')}</span>
}

// Phase 10 fix: this mapping had not been updated since Phase 7 — every
// status introduced by Phase 8 (AI classification) and Phase 9
// (logistics/payments/rewards) silently fell through to 'neutral'. Kept
// as one flat list (not split per domain) since a status string is
// unambiguous across this app's admin-only surface.
function statusTone(status: string): 'neutral' | 'warning' | 'success' | 'danger' {
  if (
    [
      'PENDING',
      'PLACED',
      'LISTED_FOR_BIDDING',
      'NEEDS_REVIEW',
      'LOGISTICS_BOOKED',
      'READY_FOR_COLLECTION',
      'PAYMENT_PENDING',
      'BOOKED',
    ].includes(status)
  )
    return 'warning'
  if (
    [
      'APPROVED',
      'ACCEPTED',
      'BID_SELECTED',
      'CLASSIFIED',
      'LOT_CREATED',
      'COLLECTED',
      'SOLD',
      'PAID',
      'COMPLETED',
      'SUCCEEDED',
      'CREDITED',
      'REDEEMED',
      'VERIFIED',
    ].includes(status)
  )
    return 'success'
  if (['REJECTED', 'CANCELLED', 'FAILED', 'FLAGGED_FOR_REVIEW', 'FLAGGED', 'ESCALATED'].includes(status))
    return 'danger'
  return 'neutral'
}
