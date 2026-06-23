import axios, { type AxiosInstance } from 'axios'

export interface ApiError {
  status: number
  code: string
  message: string
  details: unknown | null
}

interface BackendErrorShape {
  error?: {
    code?: string
    message?: string
    details?: unknown | null
  }
}

export interface ApiClientAuthOptions {
  getToken?: () => string | null
  onUnauthorized?: () => void
}

const defaultAuthOptions: ApiClientAuthOptions = {}

export function configureApiAuth(options: ApiClientAuthOptions) {
  defaultAuthOptions.getToken = options.getToken
  defaultAuthOptions.onUnauthorized = options.onUnauthorized
}

export function createApiClient(
  baseURL = import.meta.env.VITE_API_BASE_URL || '/api',
  authOptions: ApiClientAuthOptions = defaultAuthOptions,
): AxiosInstance {
  const client = axios.create({
    baseURL,
    timeout: 15000,
  })

  client.interceptors.request.use((config) => {
    const token = authOptions.getToken?.()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  })

  client.interceptors.response.use(
    (response) => response,
    (error) => {
      const normalizedError = normalizeApiError(error)
      if (normalizedError.status === 401) {
        authOptions.onUnauthorized?.()
      }
      return Promise.reject(normalizedError)
    },
  )

  return client
}

export function normalizeApiError(error: unknown): ApiError {
  const maybeError = error as {
    response?: {
      status?: number
      data?: BackendErrorShape
    }
    code?: string
    message?: string
  }

  const responseError = maybeError.response?.data?.error
  const isTimeout =
    maybeError.code === 'ECONNABORTED' ||
    (maybeError.message?.toLowerCase().includes('timeout') ?? false)

  return {
    status: maybeError.response?.status ?? 0,
    code: responseError?.code ?? (isTimeout ? 'request_timeout' : 'network_error'),
    message:
      responseError?.message ??
      (isTimeout ? '请求等待时间较长，请稍后重试。' : maybeError.message) ??
      '服务暂不可用，请稍后重试',
    details: responseError?.details ?? null,
  }
}

export const apiClient = createApiClient()
