import { ApiClient, apiClient as defaultApiClient } from '../../api/apiClient'
import type {
  AuditLogEntry,
  Bid,
  Collector,
  Complaint,
  DashboardSummary,
  Handover,
  Lot,
  Payment,
  Recycler,
  Reward,
  RrrCentre,
  Submission,
  Ward,
} from '../../types/domain'

function qs(params: Record<string, string | undefined>): string {
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== '')
  if (entries.length === 0) return ''
  return '?' + entries.map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v as string)}`).join('&')
}

/**
 * One consolidated repository for every Government-Admin-only backend
 * route added in Phase 7. Deliberately not split into one repository per
 * domain (unlike recycler-web/rrr-centre-web's per-feature repositories)
 * — these are all thin, mostly-read admin calls behind the same
 * GOVERNMENT_ADMIN role gate, and splitting them into 8 near-empty
 * classes would add ceremony without adding clarity, per the "no
 * unnecessary abstraction" project convention.
 */
export class AdminRepository {
  private readonly client: ApiClient
  constructor(client: ApiClient = defaultApiClient) {
    this.client = client
  }

  async getDashboardSummary(token: string): Promise<DashboardSummary> {
    const res = await this.client.get<{ success: true; summary: DashboardSummary }>(
      '/api/v1/admin/dashboard/summary',
      token,
    )
    return res.summary
  }

  // --- RRR Centres ---------------------------------------------------

  async listRrrCentres(token: string, status?: string): Promise<RrrCentre[]> {
    const res = await this.client.get<{ success: true; rrr_centres: RrrCentre[] }>(
      `/api/v1/admin/rrr-centres${qs({ status })}`,
      token,
    )
    return res.rrr_centres
  }

  async approveRrrCentre(userId: string, token: string): Promise<RrrCentre> {
    return this.client.post<RrrCentre>(`/api/v1/admin/rrr-centres/${userId}/approve`, undefined, token)
  }

  async rejectRrrCentre(userId: string, token: string): Promise<RrrCentre> {
    return this.client.post<RrrCentre>(`/api/v1/admin/rrr-centres/${userId}/reject`, undefined, token)
  }

  // --- Recyclers -------------------------------------------------------

  async listRecyclers(token: string, status?: string): Promise<Recycler[]> {
    const res = await this.client.get<{ success: true; recyclers: Recycler[] }>(
      `/api/v1/admin/recyclers${qs({ status })}`,
      token,
    )
    return res.recyclers
  }

  async approveRecycler(userId: string, token: string): Promise<Recycler> {
    return this.client.post<Recycler>(`/api/v1/admin/recyclers/${userId}/approve`, undefined, token)
  }

  async rejectRecycler(userId: string, token: string): Promise<Recycler> {
    return this.client.post<Recycler>(`/api/v1/admin/recyclers/${userId}/reject`, undefined, token)
  }

  // --- Collectors --------------------------------------------------------

  async listCollectors(token: string): Promise<Collector[]> {
    const res = await this.client.get<{ success: true; collectors: Collector[] }>(
      '/api/v1/admin/collectors',
      token,
    )
    return res.collectors
  }

  async createCollector(
    input: { employeeId: string; password: string; wardId: string; rrrId?: string; assignedAreaRadiusM?: number },
    token: string,
  ): Promise<Collector> {
    return this.client.post<Collector>(
      '/api/v1/admin/collectors',
      {
        employee_id: input.employeeId,
        password: input.password,
        ward_id: input.wardId,
        rrr_id: input.rrrId ?? null,
        assigned_area_radius_m: input.assignedAreaRadiusM ?? null,
      },
      token,
    )
  }

  async updateCollectorAssignment(
    userId: string,
    input: { wardId?: string; rrrId?: string; assignedAreaRadiusM?: number },
    token: string,
  ): Promise<Collector> {
    const res = await this.client.patch<{ success: true; collector: Collector }>(
      `/api/v1/admin/collectors/${userId}`,
      { ward_id: input.wardId, rrr_id: input.rrrId, assigned_area_radius_m: input.assignedAreaRadiusM },
      token,
    )
    return res.collector
  }

  async setCollectorStatus(userId: string, status: 'ACTIVE' | 'DISABLED', token: string): Promise<Collector> {
    const res = await this.client.post<{ success: true; collector: Collector }>(
      `/api/v1/admin/collectors/${userId}/status`,
      { status },
      token,
    )
    return res.collector
  }

  // --- Wards ---------------------------------------------------------

  async listWards(token: string): Promise<Ward[]> {
    const res = await this.client.get<{ success: true; wards: Ward[] }>('/api/v1/wards', token)
    return res.wards
  }

  async createWard(wardId: string, name: string, token: string): Promise<Ward> {
    return this.client.post<Ward>('/api/v1/wards', { ward_id: wardId, name }, token)
  }

  // --- E-waste oversight (read-only) ----------------------------------

  async listSubmissions(token: string, status?: string): Promise<Submission[]> {
    const res = await this.client.get<{ success: true; submissions: Submission[] }>(
      `/api/v1/admin/submissions${qs({ status })}`,
      token,
    )
    return res.submissions
  }

  async listHandovers(token: string, verificationResult?: string): Promise<Handover[]> {
    const res = await this.client.get<{ success: true; handovers: Handover[] }>(
      `/api/v1/admin/handovers${qs({ verification_result: verificationResult })}`,
      token,
    )
    return res.handovers
  }

  // --- Lots / bids oversight (read-only) ------------------------------

  async listLots(token: string, status?: string): Promise<Lot[]> {
    const res = await this.client.get<{ success: true; lots: Lot[] }>(`/api/v1/admin/lots${qs({ status })}`, token)
    return res.lots
  }

  async listBids(token: string, status?: string): Promise<Bid[]> {
    const res = await this.client.get<{ success: true; bids: Bid[] }>(`/api/v1/admin/bids${qs({ status })}`, token)
    return res.bids
  }

  // --- Complaints ------------------------------------------------------

  async listComplaints(token: string, status?: string): Promise<Complaint[]> {
    const res = await this.client.get<{ success: true; complaints: Complaint[] }>(
      `/api/v1/admin/complaints${qs({ status })}`,
      token,
    )
    return res.complaints
  }

  async reviewComplaint(
    complaintId: string,
    newStatus: string,
    token: string,
    resolutionNotes?: string,
  ): Promise<Complaint> {
    return this.client.post<Complaint>(
      `/api/v1/admin/complaints/${complaintId}/review`,
      { new_status: newStatus, resolution_notes: resolutionNotes },
      token,
    )
  }

  // --- Payments oversight (read-only) ---------------------------------

  async listPayments(token: string, status?: string): Promise<Payment[]> {
    const res = await this.client.get<{ success: true; payments: Payment[] }>(
      `/api/v1/admin/payments${qs({ status })}`,
      token,
    )
    return res.payments
  }

  // --- Rewards ---------------------------------------------------------

  async computeRewards(period: string, token: string): Promise<Reward[]> {
    const res = await this.client.post<{ success: true; created: Reward[]; count: number }>(
      '/api/v1/admin/rewards/compute',
      { period },
      token,
    )
    return res.created
  }

  async listRewards(token: string, period?: string): Promise<Reward[]> {
    const res = await this.client.get<{ success: true; rewards: Reward[] }>(
      `/api/v1/admin/rewards${qs({ period })}`,
      token,
    )
    return res.rewards
  }

  // --- Audit logs / Government Actions --------------------------------

  async listAuditLogs(
    token: string,
    filters: { actorRole?: string; entityType?: string } = {},
  ): Promise<AuditLogEntry[]> {
    const res = await this.client.get<{ success: true; logs: AuditLogEntry[] }>(
      `/api/v1/audit-logs${qs({ actor_role: filters.actorRole, entity_type: filters.entityType })}`,
      token,
    )
    return res.logs
  }
}

export const adminRepository = new AdminRepository()
