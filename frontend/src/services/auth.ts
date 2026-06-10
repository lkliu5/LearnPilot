/**
 * 认证数据获取层（接口文档第 3 章）。登录成功后落 token + user 到 localStorage，
 * 后续请求由 api.ts 自动附带 Authorization。
 */
import { apiPost, clearAuth, setToken, setUser, type AuthUser } from './api'

interface LoginResponse {
  token: string
  expiresIn: number
  user: AuthUser
}

/** 登录（接口文档 3.1 + 15.1）。成功落 token/user 并返回 user。 */
export async function login(username: string, password: string, remember = true): Promise<AuthUser> {
  const data = await apiPost<LoginResponse>('/auth/login', { username, password, remember })
  setToken(data.token)
  setUser(data.user)
  return data.user
}

/** 退出（接口文档 3.3）。无论后端是否成功都清本地登录态。 */
export async function logout(): Promise<void> {
  try {
    await apiPost('/auth/logout')
  } catch {
    /* 退出失败不阻断本地清票 */
  }
  clearAuth()
}
