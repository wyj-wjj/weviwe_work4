import { createApiClient, normalizeApiError } from '../src/api/client'

test('api client defaults to the same-origin API prefix', () => {
  const client = createApiClient()

  expect(client.defaults.baseURL).toBe('/api')
})

test('api client uses the configured API base URL', () => {
  const client = createApiClient('https://api.example.test')

  expect(client.defaults.baseURL).toBe('https://api.example.test')
})

test('failed requests are normalized to a consistent error path', () => {
  const error = normalizeApiError({
    response: {
      status: 503,
      data: {
        error: {
          code: 'service_unavailable',
          message: '服务暂不可用，请稍后重试',
          details: null,
        },
      },
    },
  })

  expect(error).toEqual({
    status: 503,
    code: 'service_unavailable',
    message: '服务暂不可用，请稍后重试',
    details: null,
  })
})

test('request timeouts are normalized as timeout errors', () => {
  const error = normalizeApiError({
    code: 'ECONNABORTED',
    message: 'timeout of 10000ms exceeded',
  })

  expect(error).toEqual({
    status: 0,
    code: 'request_timeout',
    message: '请求等待时间较长，请稍后重试。',
    details: null,
  })
})

test('api client attaches the current bearer token to requests', async () => {
  const client = createApiClient('https://api.example.test', {
    getToken: () => 'session-token',
  })

  await client.get('/secure', {
    adapter: async (config) => {
      expect(config.headers?.Authorization).toBe('Bearer session-token')
      return {
        data: { ok: true },
        status: 200,
        statusText: 'OK',
        headers: {},
        config,
      }
    },
  })
})

test('api client clears auth state and redirects to login on authentication errors', async () => {
  const onUnauthorized = vi.fn()
  const client = createApiClient('https://api.example.test', {
    onUnauthorized,
  })

  await expect(
    client.get('/secure', {
      adapter: async () => {
        throw {
          response: {
            status: 401,
            data: {
              error: {
                code: 'auth_failed',
                message: '登录已失效',
                details: null,
              },
            },
          },
        }
      },
    }),
  ).rejects.toMatchObject({
    status: 401,
    code: 'auth_failed',
  })

  expect(onUnauthorized).toHaveBeenCalledOnce()
})
