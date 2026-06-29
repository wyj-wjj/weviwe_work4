import { defineStore } from 'pinia'

export type AccountType = 'admin' | 'full_user' | 'general_user'
export type ContentLevel = 'general' | 'full'

export interface AuthUser {
  id: number
  username: string
  display_name: string
  account_type: AccountType
  content_level: ContentLevel
  department_id?: number | null
  department_name?: string | null
}

interface StoredAuthSession {
  token: string
  user: AuthUser
}

const AUTH_STORAGE_KEY = 'weview.auth'

function loadStoredSession(): StoredAuthSession | null {
  try {
    const raw = sessionStorage.getItem(AUTH_STORAGE_KEY)
    if (!raw) {
      return null
    }

    const parsed = JSON.parse(raw) as StoredAuthSession
    if (!parsed.token || !parsed.user) {
      return null
    }

    return parsed
  } catch {
    sessionStorage.removeItem(AUTH_STORAGE_KEY)
    return null
  }
}

export const useAuthStore = defineStore('auth', {
  state: () => {
    const storedSession = loadStoredSession()

    return {
      token: storedSession?.token ?? null,
      user: storedSession?.user ?? null,
    } as {
      token: string | null
      user: AuthUser | null
    }
  },
  getters: {
    isAuthenticated: (state) => Boolean(state.token && state.user),
    isAdmin: (state) => state.user?.account_type === 'admin',
    accountType: (state): AccountType | null => state.user?.account_type ?? null,
    contentLevel: (state): ContentLevel | null => state.user?.content_level ?? null,
    defaultRoute: (state) => (state.user?.account_type === 'admin' ? '/admin' : '/app'),
  },
  actions: {
    setSession(token: string, user: AuthUser) {
      this.token = token
      this.user = user
      sessionStorage.setItem(
        AUTH_STORAGE_KEY,
        JSON.stringify({
          token,
          user,
        }),
      )
    },
    clearSession() {
      this.token = null
      this.user = null
      sessionStorage.removeItem(AUTH_STORAGE_KEY)
    },
    logout() {
      this.clearSession()
    },
  },
})
