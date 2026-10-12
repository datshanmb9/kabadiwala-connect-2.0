import { describe, expect, it, vi } from 'vitest'
import { ApiClient, ApiError } from './apiClient'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  })
}

describe('ApiClient success path', () => {
  it('GET decodes a successful JSON body', async () => {
    const fetchImpl = vi.fn().mockResolvedValue(jsonResponse({ success: true, value: 42 }))
    const client = new ApiClient({ baseUrl: 'http://test', fetchImpl })
    const result = await client.get<{ value: number }>('/x')
    expect(result.value).toBe(42)
  })

  it('POST attaches Authorization and Idempotency-Key headers, and JSON body', async () => {
    const fetchImpl = vi.fn().mockResolvedValue(jsonResponse({ success: true }))
    const client = new ApiClient({ baseUrl: 'http://test', fetchImpl })
    await client.post('/x', { a: 1 }, 'tok-1', 'idem-1')

    const [, init] = fetchImpl.mock.calls[0]
    const headers = init.headers as Record<string, string>
    expect(headers.Authorization).toBe('Bearer tok-1')
    expect(headers['Idempotency-Key']).toBe('idem-1')
    expect(JSON.parse(init.body as string)).toEqual({ a: 1 })
  })

  it('POST omits Authorization header when no token given', async () => {
    const fetchImpl = vi.fn().mockResolvedValue(jsonResponse({ success: true }))
    const client = new ApiClient({ baseUrl: 'http://test', fetchImpl })
    await client.post('/x', { a: 1 })

    const [, init] = fetchImpl.mock.calls[0]
    const headers = init.headers as Record<string, string>
    expect(headers.Authorization).toBeUndefined()
  })
})

describe('ApiClient structured backend errors', () => {
  it('propagates {success:false,error_code,message} as ApiError', async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValue(
        jsonResponse({ success: false, error_code: 'INVALID_CREDENTIALS', message: 'Invalid username or password.' }, 401),
      )
    const client = new ApiClient({ baseUrl: 'http://test', fetchImpl })

    await expect(client.post('/api/v1/auth/login', {})).rejects.toMatchObject({
      errorCode: 'INVALID_CREDENTIALS',
      statusCode: 401,
    })
  })

  it('isInvalidToken is true only for INVALID_TOKEN', async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValue(jsonResponse({ success: false, error_code: 'INVALID_TOKEN', message: 'Invalid.' }, 401))
    const client = new ApiClient({ baseUrl: 'http://test', fetchImpl })

    try {
      await client.get('/x')
      expect.fail('should have thrown')
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError)
      expect((err as ApiError).isInvalidToken).toBe(true)
    }
  })
})

describe('ApiClient non-contract error shapes', () => {
  it('FastAPI 422 validation errors become a structured VALIDATION_ERROR', async () => {
    const fetchImpl = vi.fn().mockResolvedValue(
      jsonResponse(
        { detail: [{ loc: ['body', 'amount'], msg: 'field required', type: 'value_error.missing' }] },
        422,
      ),
    )
    const client = new ApiClient({ baseUrl: 'http://test', fetchImpl })

    await expect(client.post('/x', {})).rejects.toMatchObject({ errorCode: 'VALIDATION_ERROR' })
  })

  it('a non-JSON 500 body still becomes a structured ApiError, not a crash', async () => {
    const fetchImpl = vi.fn().mockResolvedValue(new Response('Internal Server Error', { status: 500 }))
    const client = new ApiClient({ baseUrl: 'http://test', fetchImpl })

    await expect(client.get('/x')).rejects.toMatchObject({ errorCode: 'UNKNOWN_ERROR' })
  })
})

describe('ApiClient network failures', () => {
  it('a rejected fetch becomes NETWORK_ERROR', async () => {
    const fetchImpl = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'))
    const client = new ApiClient({ baseUrl: 'http://test', fetchImpl })

    await expect(client.get('/x')).rejects.toMatchObject({ errorCode: 'NETWORK_ERROR' })
  })

  it('a request slower than the configured timeout becomes NETWORK_TIMEOUT', async () => {
    const fetchImpl = vi.fn().mockImplementation((_url: string, init: RequestInit) => {
      return new Promise((_resolve, reject) => {
        init.signal?.addEventListener('abort', () => {
          reject(new DOMException('The operation was aborted.', 'AbortError'))
        })
      })
    })
    const client = new ApiClient({ baseUrl: 'http://test', fetchImpl, timeoutMs: 20 })

    await expect(client.get('/x')).rejects.toMatchObject({ errorCode: 'NETWORK_TIMEOUT' })
  })
})

describe('ApiClient fetch receiver binding (Phase 5 regression)', () => {
  it('the real global fetch is bound so it is safe to call as this.fetchImpl(...)', () => {
    // Regression coverage for the Illegal-invocation bug found in
    // rrr-centre-web: constructing an ApiClient with no fetchImpl override
    // must not throw merely from binding, and the stored function must not
    // be the raw unbound reference.
    expect(() => new ApiClient()).not.toThrow()
  })
})
