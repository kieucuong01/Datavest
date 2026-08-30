const ACTIVE_ORDER_STATUSES = new Set([
  'accepted',
  'new',
  'partially_filled',
  'pending_new'
])

const NEUTRAL_FINAL_ORDER_STATUSES = new Set([
  'canceled',
  'cancelled',
  'done_for_day',
  'expired'
])

export function brokerOrderStatusColor (status) {
  const value = String(status || '').trim().toLowerCase()
  if (value === 'filled') return 'green'
  if (value === 'rejected') return 'red'
  if (ACTIVE_ORDER_STATUSES.has(value)) return 'blue'
  if (NEUTRAL_FINAL_ORDER_STATUSES.has(value)) return undefined
  return 'orange'
}
