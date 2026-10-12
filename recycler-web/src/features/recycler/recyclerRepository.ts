import { ApiClient, apiClient as defaultApiClient } from '../../api/apiClient'
import type { RecyclerProfile } from '../../types/domain'

export interface RegisterInput {
  username: string
  password: string
  companyName: string
}

export class RecyclerRepository {
  private readonly client: ApiClient
  constructor(client: ApiClient = defaultApiClient) {
    this.client = client
  }

  /** Public endpoint — self-registration, pending admin approval. */
  async register(input: RegisterInput): Promise<RecyclerProfile> {
    return this.client.post<RecyclerProfile>('/api/v1/recyclers/register', {
      username: input.username,
      password: input.password,
      company_name: input.companyName,
    })
  }

  async getProfile(accessToken: string): Promise<RecyclerProfile> {
    return this.client.get<RecyclerProfile>('/api/v1/recyclers/me', accessToken)
  }
}

export const recyclerRepository = new RecyclerRepository()
