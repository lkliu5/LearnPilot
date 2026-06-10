import { PRESET, type JobMarket } from '../data/jobMarket/preset'

export type { JobMarket, JobSkill, HotJob } from '../data/jobMarket/preset'
export { HOT_JOBS } from '../data/jobMarket/preset'

/**
 * 岗位市场画像 Provider（适配器）：
 * - 不在点击时现场联网爬取；读取"定期快照"（public/data/job-market/*.json）。
 * - localStorage 缓存 + TTL：打开秒显缓存，过期再后台取新。
 * - 降级：取数失败 → 旧缓存 / 内置预置岗位库（离线）。
 * 日后把 fetch 换成后端 API 即可，UI 不变。
 */
const CACHE_PREFIX = 'zx-jobmarket:'
const TTL = 12 * 60 * 60 * 1000 // 12h

export interface JobMarketResult {
  data: JobMarket
  /** 是否来自离线降级（旧缓存 / 预置库）*/
  offline: boolean
}

interface CacheEntry {
  data: JobMarket
  cachedAt: number
}

function readCache(id: string): CacheEntry | null {
  try {
    const raw = localStorage.getItem(CACHE_PREFIX + id)
    return raw ? (JSON.parse(raw) as CacheEntry) : null
  } catch {
    return null
  }
}

function writeCache(id: string, data: JobMarket) {
  try {
    localStorage.setItem(CACHE_PREFIX + id, JSON.stringify({ data, cachedAt: Date.now() }))
  } catch {
    /* 忽略写入失败（隐私模式等）*/
  }
}

export async function getJobMarket(id: string): Promise<JobMarketResult> {
  const cached = readCache(id)
  // 1) 命中未过期缓存：秒显
  if (cached && Date.now() - cached.cachedAt < TTL) {
    return { data: cached.data, offline: false }
  }
  // 2) 取最新快照
  try {
    const res = await fetch(`/data/job-market/${id}.json`, { cache: 'no-store' })
    if (!res.ok) throw new Error(`snapshot ${id} not found`)
    const data = (await res.json()) as JobMarket
    writeCache(id, data)
    return { data, offline: false }
  } catch {
    // 3) 降级：旧缓存 → 预置库
    if (cached) return { data: cached.data, offline: true }
    if (PRESET[id]) return { data: PRESET[id], offline: true }
    throw new Error(`no job market data for ${id}`)
  }
}

/** 相对时间：用于"更新于 X 前" */
export function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  if (Number.isNaN(diff)) return '未知'
  const min = Math.floor(diff / 60000)
  if (min < 1) return '刚刚'
  if (min < 60) return `${min} 分钟前`
  const hr = Math.floor(min / 60)
  if (hr < 24) return `${hr} 小时前`
  return `${Math.floor(hr / 24)} 天前`
}
