/**
 * 苏格拉底辅导数据获取层（接口文档 8.7 + 15.4，接口 22）。
 *
 * 请求头带 `Accept: text/event-stream` 时后端切 SSE 流式：
 *   `data: {"delta":"<片段>"}` 逐条（空行分隔）→ `event: done`（携带 sessionId +
 *   suggestions）；出错时 `event: error` `data: {"code":2001,...}`，前端保留已渲染
 *   片段并回退本地引导链。EventSource 不支持 POST，故用 fetch + ReadableStream 手工解析。
 */
import { ApiError, getToken } from './api'

export interface TutorDone {
  sessionId: string
  suggestions: string[]
}

export interface TutorStreamOptions {
  kpId: string
  /** 多轮会话上下文，首轮可空（由后端生成并经 done 事件带回）。 */
  sessionId?: string
  message: string
  /** 每个增量片段（逐 delta 追加渲染）。 */
  onDelta: (delta: string) => void
}

/** SSE 流式对话：正常结束 resolve done 负载；连接失败 / event:error 时 reject。 */
export async function tutorChatStream(opts: TutorStreamOptions): Promise<TutorDone> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'text/event-stream',
  }
  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch('/api/v1/resource/tutor/chat', {
    method: 'POST',
    headers,
    body: JSON.stringify({ kpId: opts.kpId, sessionId: opts.sessionId, message: opts.message }),
  })

  // 非流式回包（401 / 1004 等信封错误）：解信封抛业务码
  const ctype = res.headers.get('content-type') ?? ''
  if (!ctype.includes('text/event-stream')) {
    let env: { code?: number; message?: string } = {}
    try {
      env = await res.json()
    } catch {
      /* 非 JSON 体走 HTTP 状态兜底 */
    }
    throw new ApiError(env.code ?? res.status, env.message || `请求失败（HTTP ${res.status}）`)
  }
  if (!res.body) throw new ApiError(2001, '当前环境不支持流式读取')

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  let done: TutorDone | null = null

  /** 解析一个 SSE 事件块（event: 行 + data: 行；默认事件为 delta 增量）。 */
  const handleEvent = (block: string) => {
    let event = 'message'
    const dataLines: string[] = []
    for (const line of block.split('\n')) {
      if (line.startsWith('event:')) event = line.slice(6).trim()
      else if (line.startsWith('data:')) dataLines.push(line.slice(5).trimStart())
    }
    if (!dataLines.length) return
    const payload = JSON.parse(dataLines.join('\n'))
    if (event === 'done') {
      done = { sessionId: payload.sessionId, suggestions: payload.suggestions ?? [] }
    } else if (event === 'error') {
      throw new ApiError(payload.code ?? 2001, payload.message || '辅导回复生成失败')
    } else if (typeof payload.delta === 'string') {
      opts.onDelta(payload.delta)
    }
  }

  try {
    for (;;) {
      const { value, done: eof } = await reader.read()
      if (eof) break
      buf += decoder.decode(value, { stream: true })
      let idx: number
      while ((idx = buf.indexOf('\n\n')) >= 0) {
        const block = buf.slice(0, idx).replace(/\r/g, '')
        buf = buf.slice(idx + 2)
        if (block.trim()) handleEvent(block)
      }
    }
  } finally {
    reader.cancel().catch(() => {
      /* 流已结束时忽略 */
    })
  }

  if (!done) throw new ApiError(2001, '流式响应未正常结束')
  return done
}
