// Mirrors the actual backend response shapes exactly (see
// backend/app/modules/*/schemas.py) — no field here is invented client-side.

export interface AuthSession {
  accessToken: string
  refreshToken: string
  role: string
  userId: string
  username: string
}

export interface RecyclerProfile {
  user_id: string
  username: string
  license_id: string
  company_name: string
  status: 'PENDING' | 'APPROVED' | 'REJECTED'
}

export interface Lot {
  lot_id: string
  rrr_id: string
  ward_id: string
  category: string
  item_ids: string[]
  status: string
  bid_deadline: string | null
  total_weight_kg?: number | null
  item_details?: LotItemDetail[]
  price_estimate?: LotPriceEstimate | null
}

// The items' stored ML estimate, aggregated by the backend (see
// backend/app/modules/pricing/service.py lot_price_estimate). Totals are
// already min/max price per kg x the lot's collected weight.
export interface LotPriceEstimate {
  predicted_price_per_kg: number | null
  min_price: number
  max_price: number
  weight_kg: number
  estimated_total_min: number
  estimated_total_max: number
  is_estimate: boolean
  model_version: string | null
  estimated_at: string | null
}

export interface LotItemDetail {
  submission_id: string
  home_user_id: string
  actual_weight_kg: number | null
  collection_photo_file_id: string | null
  collector_id: string | null
  collector_lat: number | null
  collector_lng: number | null
  collection_ts: string | null
}

export interface Bid {
  bid_id: string
  lot_id: string
  recycler_id: string
  amount: string
  status: string
  placed_at: string
  accepted_at: string | null
}

export interface LogisticsBooking {
  booking_id: string
  lot_id: string
  recycler_id: string
  slot_time: string
  status: string
}

export interface Payment {
  payment_id: string
  lot_id: string
  recycler_id: string
  amount: string
  status: string
  gateway: string
  gateway_reference: string | null
  created_at: string
}
