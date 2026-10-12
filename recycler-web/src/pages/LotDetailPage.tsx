import { type FormEvent, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ApiError } from '../api/apiClient'
import { generateIdempotencyKey } from '../api/idempotencyKey'
import { Card, ErrorView, InlineErrorBanner, LoadingView, StatusBadge } from '../components/StateViews'
import { Layout, PageHeader } from '../components/Layout'
import { bidsRepository } from '../features/bids/bidsRepository'
import { useAuth } from '../features/auth/AuthContext'
import { lotsRepository } from '../features/lots/lotsRepository'
import { logisticsRepository } from '../features/logistics/logisticsRepository'
import { paymentsRepository } from '../features/payments/paymentsRepository'
import type { Bid, LogisticsBooking, Lot, Payment } from '../types/domain'

const POST_ACCEPTANCE_STATUSES = [
  'BID_SELECTED',
  'LOGISTICS_BOOKED',
  'READY_FOR_COLLECTION',
  'PAYMENT_PENDING',
  'SOLD',
  'COMPLETED',
]

export function LotDetailPage() {
  const { lotId } = useParams<{ lotId: string }>()
  const { session } = useAuth()

  const [lot, setLot] = useState<Lot | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [amount, setAmount] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [placedBid, setPlacedBid] = useState<Bid | null>(null)
  const [idempotencyKey] = useState(() => generateIdempotencyKey())

  // Post-acceptance flow state — only populated when this recycler owns
  // the accepted bid on this lot (checked via the backend's own 403,
  // never assumed client-side).
  const [ownsAcceptedBid, setOwnsAcceptedBid] = useState(false)
  const [booking, setBooking] = useState<LogisticsBooking | null>(null)
  const [payments, setPayments] = useState<Payment[]>([])
  const [slotTime, setSlotTime] = useState('')
  const [actionError, setActionError] = useState<string | null>(null)
  const [actioning, setActioning] = useState(false)

  useEffect(() => {
    void load()
  }, [lotId])

  async function load() {
    if (!session || !lotId) return
    setLoading(true)
    setError(null)
    try {
      const loadedLot = await lotsRepository.getLot(lotId, session.accessToken)
      setLot(loadedLot)
      if (POST_ACCEPTANCE_STATUSES.includes(loadedLot.status)) {
        await loadOwnershipScopedData(lotId, session.accessToken)
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not load this lot.')
    } finally {
      setLoading(false)
    }
  }

  async function loadOwnershipScopedData(id: string, token: string) {
    try {
      const [currentBooking, currentPayments] = await Promise.all([
        logisticsRepository.getBookingForLot(id, token),
        paymentsRepository.listPaymentsForLot(id, token),
      ])
      setOwnsAcceptedBid(true)
      setBooking(currentBooking)
      setPayments(currentPayments)
    } catch {
      // NOT_ACCEPTED_BID_OWNER (or any other rejection) just means this
      // recycler has nothing to act on here — not a page-level error.
      setOwnsAcceptedBid(false)
    }
  }

  async function handlePlaceBid(e: FormEvent) {
    e.preventDefault()
    if (!session || !lotId) return
    setSubmitError(null)
    setSubmitting(true)
    try {
      const bid = await bidsRepository.placeBid(lotId, amount, session.accessToken, idempotencyKey)
      setPlacedBid(bid)
    } catch (err) {
      setSubmitError(err instanceof ApiError ? err.message : 'Could not place this bid.')
    } finally {
      setSubmitting(false)
    }
  }

  async function handleBookLogistics(e: FormEvent) {
    e.preventDefault()
    if (!session || !lotId || !slotTime) return
    setActionError(null)
    setActioning(true)
    try {
      const result = await logisticsRepository.bookLogistics(
        lotId,
        new Date(slotTime).toISOString(),
        session.accessToken,
        generateIdempotencyKey(),
      )
      setBooking(result)
      await load()
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'Could not book logistics for this lot.')
    } finally {
      setActioning(false)
    }
  }

  async function handleConfirmCollection() {
    if (!session || !booking) return
    setActionError(null)
    setActioning(true)
    try {
      await logisticsRepository.confirmCollection(booking.booking_id, session.accessToken, generateIdempotencyKey())
      await load()
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'Could not confirm collection.')
    } finally {
      setActioning(false)
    }
  }

  async function handlePayNow() {
    if (!session || !lotId) return
    setActionError(null)
    setActioning(true)
    try {
      await paymentsRepository.initiatePayment(lotId, session.accessToken, generateIdempotencyKey())
      await load()
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'Payment could not be completed.')
    } finally {
      setActioning(false)
    }
  }

  return (
    <Layout approved>
      <Link to="/lots" className="back-link">
        ← Back to available lots
      </Link>
      <PageHeader
        title="Lot Detail"
        description={lot ? `${lot.category} · Ward ${lot.ward_id}` : undefined}
        actions={lot ? <StatusBadge status={lot.status} /> : undefined}
      />
      {loading && <LoadingView />}
      {error && <ErrorView message={error} onRetry={load} />}
      {lot && (
        <div className="detail-layout">
          <div className="detail-main">
            <Card>
              <h2>Lot information</h2>
              <div className="kv-list">
                <p>
                  <strong>Lot ID:</strong> {lot.lot_id}
                </p>
                <p>
                  <strong>Category:</strong> {lot.category}
                </p>
                <p>
                  <strong>Ward:</strong> {lot.ward_id}
                </p>
                <p>
                  <strong>Items:</strong> {lot.item_ids.length}
                </p>
                {lot.total_weight_kg != null && (
                  <p>
                    <strong>Collected weight:</strong> {lot.total_weight_kg.toFixed(2)} kg
                  </p>
                )}
                {lot.item_details && lot.item_details.length > 0 && (
                  <p>
                    <strong>Collection traceability:</strong> {lot.item_details.length} collected item records
                  </p>
                )}
                <p>
                  <strong>Status:</strong> <StatusBadge status={lot.status} />
                </p>
                {lot.bid_deadline && (
                  <p>
                    <strong>Bid deadline:</strong> {new Date(lot.bid_deadline).toLocaleString()}
                  </p>
                )}
              </div>
            </Card>

            {ownsAcceptedBid && (
              <Card>
                <h2>Your Accepted Bid — Next Steps</h2>
                {actionError && <InlineErrorBanner message={actionError} />}

                {lot.status === 'BID_SELECTED' && (
                  <form onSubmit={handleBookLogistics}>
                    <p className="hint">Book a collection slot to move this lot forward.</p>
                    <label>
                      Pickup slot
                      <input
                        type="datetime-local"
                        value={slotTime}
                        onChange={(e) => setSlotTime(e.target.value)}
                        required
                      />
                    </label>
                    <button type="submit" disabled={actioning}>
                      {actioning ? 'Booking…' : 'Book Logistics'}
                    </button>
                  </form>
                )}

                {lot.status === 'LOGISTICS_BOOKED' && booking && (
                  <>
                    <p className="callout callout-info">
                      Slot booked for {new Date(booking.slot_time).toLocaleString()}. Confirm once you have
                      physically collected the lot.
                    </p>
                    <button
                      type="button"
                      style={{ marginTop: 16 }}
                      disabled={actioning}
                      onClick={() => void handleConfirmCollection()}
                    >
                      {actioning ? 'Confirming…' : 'Confirm Collection'}
                    </button>
                  </>
                )}

                {lot.status === 'READY_FOR_COLLECTION' && (
                  <>
                    <p className="callout callout-info">
                      Collection confirmed. You may now pay for this lot (mock gateway).
                    </p>
                    <button
                      type="button"
                      style={{ marginTop: 16 }}
                      disabled={actioning}
                      onClick={() => void handlePayNow()}
                    >
                      {actioning ? 'Processing…' : 'Pay Now'}
                    </button>
                  </>
                )}

                {lot.status === 'PAYMENT_PENDING' && <p className="callout">Payment is being processed…</p>}

                {(lot.status === 'SOLD' || lot.status === 'COMPLETED') && payments.length > 0 && (
                  <>
                    <p className="callout callout-success">Payment complete.</p>
                    {payments
                      .filter((p) => p.status === 'SUCCEEDED')
                      .map((p) => (
                        <p key={p.payment_id} style={{ marginTop: 12 }}>
                          <strong>Paid:</strong> ₹{p.amount} · {p.gateway} · ref {p.gateway_reference}
                        </p>
                      ))}
                  </>
                )}

                {payments.some((p) => p.status === 'FAILED') && (
                  <div className="inline-error-banner" style={{ marginTop: 12 }}>
                    A previous payment attempt failed
                    {lot.status === 'READY_FOR_COLLECTION' ? ' — you may retry above.' : '.'}
                  </div>
                )}
              </Card>
            )}
          </div>

          <aside className="detail-side">
            {lot.price_estimate && (
              <div className="card price-card">
                <h2>Estimated Price</h2>
                <p>
                  <strong>Estimated price:</strong> ₹{lot.price_estimate.min_price.toFixed(2)} – ₹
                  {lot.price_estimate.max_price.toFixed(2)} / kg
                </p>
                <p className="price-figure">
                  <strong>Estimated total:</strong> ₹{lot.price_estimate.estimated_total_min.toFixed(2)} – ₹
                  {lot.price_estimate.estimated_total_max.toFixed(2)}
                </p>
                <p className="hint">
                  ML estimate for {lot.price_estimate.weight_kg.toFixed(2)} kg collected. Informational only — not a
                  reserve or final price.
                </p>
              </div>
            )}

            {lot.status !== 'LISTED_FOR_BIDDING' && !placedBid && !POST_ACCEPTANCE_STATUSES.includes(lot.status) && (
              <Card>
                <p className="hint">This lot is not currently open for bidding.</p>
              </Card>
            )}

            {lot.status === 'LISTED_FOR_BIDDING' && !placedBid && (
              <div className="card bid-card">
                <h2>Place a Bid</h2>
                <form onSubmit={handlePlaceBid}>
                  {submitError && <InlineErrorBanner message={submitError} />}
                  <label>
                    Bid amount (₹)
                    <input
                      key="amount"
                      inputMode="decimal"
                      placeholder="e.g. 1250.50"
                      value={amount}
                      onChange={(e) => setAmount(e.target.value)}
                      required
                    />
                  </label>
                  <button type="submit" disabled={submitting}>
                    {submitting ? 'Placing…' : 'Place Bid'}
                  </button>
                </form>
              </div>
            )}

            {placedBid && (
              <div className="card bid-card">
                <h2>Bid placed</h2>
                <div className="kv-list">
                  <p>
                    <strong>Amount:</strong> ₹{placedBid.amount}
                  </p>
                  <p>
                    <strong>Status:</strong> <StatusBadge status={placedBid.status} />
                  </p>
                </div>
                <p className="hint" style={{ marginTop: 12 }}>
                  Track the outcome under <Link to="/my-bids">My Bids</Link>.
                </p>
              </div>
            )}
          </aside>
        </div>
      )}
    </Layout>
  )
}
