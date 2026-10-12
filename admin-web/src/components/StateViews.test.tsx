import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { StatusBadge } from './StateViews'

// Phase 10 regression guard: statusTone() had not been updated since
// Phase 7 and silently mapped every Phase 8/9 status to 'neutral'.
describe('StatusBadge tone mapping (Phase 10 fix)', () => {
  it.each([
    ['NEEDS_REVIEW', 'warning'],
    ['LOGISTICS_BOOKED', 'warning'],
    ['READY_FOR_COLLECTION', 'warning'],
    ['PAYMENT_PENDING', 'warning'],
    ['SOLD', 'success'],
    ['PAID', 'success'],
    ['COMPLETED', 'success'],
    ['SUCCEEDED', 'success'],
    ['CREDITED', 'success'],
    ['REDEEMED', 'success'],
    ['FAILED', 'danger'],
  ])('%s renders with tone class status-badge-%s', (status, expectedTone) => {
    render(<StatusBadge status={status} />)
    const badge = screen.getByText(status.replaceAll('_', ' '))
    expect(badge.className).toContain(`status-badge-${expectedTone}`)
  })

  it('an unrecognized status falls back to neutral rather than throwing', () => {
    render(<StatusBadge status="SOME_FUTURE_STATUS" />)
    const badge = screen.getByText('SOME FUTURE STATUS')
    expect(badge.className).toContain('status-badge-neutral')
  })
})
