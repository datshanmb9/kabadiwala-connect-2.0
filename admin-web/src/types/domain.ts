// Mirrors the actual backend response shapes exactly (see
// backend/app/modules/*/schemas.py and the raw dicts returned by each
// admin list endpoint) — no field here is invented client-side.

export interface AuthSession {
  accessToken: string
  refreshToken: string
  role: string
  userId: string
  username: string
}

export interface DashboardSummary {
  users_by_role: Record<string, number>
  wards_count: number
  rrr_centres_by_status: Record<string, number>
  recyclers_by_status: Record<string, number>
  submissions_by_status: Record<string, number>
  lots_by_status: Record<string, number>
  bids_by_status: Record<string, number>
  complaints_by_status: Record<string, number>
  flagged_submissions_count: number
}

export interface RrrCentre {
  user_id: string
  username: string
  rrr_id: string
  tender_id: string
  ward_id: string
  licence_doc_ref: string | null
  status: 'PENDING' | 'APPROVED' | 'REJECTED'
}

export interface Recycler {
  user_id: string
  username: string
  license_id: string
  company_name: string
  status: 'PENDING' | 'APPROVED' | 'REJECTED'
}

export interface Collector {
  user_id: string
  employee_id: string
  ward_id: string
  rrr_id: string | null
  assigned_area_radius_m: number | null
  status: string
}

export interface Ward {
  ward_id: string
  name: string
  rrr_centre_id?: string
}

export interface Submission {
  submission_id: string
  home_user_id: string
  ward_id: string
  status: string
  category?: string
  home_lat: number | null
  home_lng: number | null
  home_ts: string
}

export interface Handover {
  submission_id: string
  collector_id: string
  rrr_id: string | null
  collector_lat: number | null
  collector_lng: number | null
  collector_ts: string
  distance_m: number | null
  verification_result: string
  failure_reasons: string[]
}

export interface Lot {
  lot_id: string
  rrr_id: string
  ward_id: string
  category: string
  item_ids: string[]
  status: string
  bid_deadline: string | null
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

export interface Complaint {
  complaint_id: string
  reporter_id: string
  reporter_role: string
  target_type: string
  target_id: string
  category: string
  description: string
  status: string
  resolution_notes: string | null
  created_at: string
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

export interface Reward {
  reward_id: string
  home_user_id: string
  period: string
  points: number
  amount: string
  status: string
  created_at: string
}

export interface AuditLogEntry {
  log_id: string
  actor_id: string | null
  actor_role: string | null
  action: string
  entity_type: string
  entity_id: string
  details: Record<string, unknown>
  timestamp: string
}
