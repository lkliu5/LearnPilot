/**
 * 对话式学习画像诊断数据获取层（接口文档第 17 章，接口 37/38）。
 *
 * - 17.1 `POST /profile/dialogue`：与 8.7/15.4 一致的 SSE 双模式——请求头带
 *   `Accept: text/event-stream` 时逐 `data:{delta}` 下发追问语，`event: portrait`
 *   下发本轮抽取的画像维度增量，`event: done` 终态（sessionId/suggestions/diagnosisComplete）。
 * - 17.2/17.3 `GET /profile/student-portrait`：异质 ≥6 维 StudentPortrait。
 *
 * Mock-first：无后端（USE_REAL_API=false）时走本地脚本化多轮对话，逐 token 模拟流式 +
 * 边问边抽画像，保证「无任何 API Key 跑通全链路」。
 */
import { ApiError, USE_REAL_API, apiGet, getToken } from './api'

/** 17.2 PortraitDimension（亦即 17.1 portraitUpdates[] / event:portrait 的 updates[] 元素） */
export interface PortraitDimension {
  key: string
  label: string
  value: string
  /** 仅可量化维度（如知识基础）给出，0-100 */
  score?: number
  /** 置信度 0-1；inferred 维度须偏低（≤0.6） */
  confidence: number
  source: 'dialogue' | 'manual' | 'inferred'
  updatedAt?: string
}

/** 17.2 异质学生动态画像 */
export interface StudentPortrait {
  dimensions: PortraitDimension[]
  version: string
  updatedAt: string
}

/** 17.1 本轮终态（event:done） */
export interface DialogueDone {
  sessionId: string
  suggestions: string[]
  diagnosisComplete: boolean
}

export interface DialogueStreamOptions {
  /** 多轮上下文 id，首轮可空（由后端 / mock 生成并经 done 回传） */
  sessionId?: string
  message: string
  /** 首轮可带已知信息辅助冷启动（4.1 枚举：major/goal） */
  context?: { major?: string; goal?: string }
  /** 逐增量片段（追问语 token） */
  onDelta: (delta: string) => void
  /** 本轮抽取的画像维度增量（可多次回调，边问边抽） */
  onPortrait: (updates: PortraitDimension[]) => void
}

/**
 * 建议维度集（17.2，key 稳定）。右侧画像面板按此顺序展示「N/6」与待采集占位。
 * 异质：knowledge_base 可量化（带 score），其余为定性维度。
 */
export const CANONICAL_DIMS: { key: string; label: string }[] = [
  { key: 'knowledge_base', label: '知识基础' },
  { key: 'cognitive_style', label: '认知风格' },
  { key: 'error_preference', label: '易错点偏好' },
  { key: 'learning_goal', label: '学习目标' },
  { key: 'prior_experience', label: '先验经验' },
  { key: 'learning_pace', label: '学习节奏' },
]

/* ============ 对外统一入口（按总开关切真实 / mock） ============ */

export function profileDialogueStream(opts: DialogueStreamOptions): Promise<DialogueDone> {
  return USE_REAL_API ? realDialogue(opts) : mockDialogue(opts)
}

export function getStudentPortrait(): Promise<StudentPortrait> {
  if (USE_REAL_API) return apiGet<StudentPortrait>('/profile/student-portrait')
  // mock：尚无诊断数据，返回空画像（17.3 约定，非错误）
  return Promise.resolve({ dimensions: [], version: 'v1', updatedAt: new Date().toISOString() })
}

/* ============ 真实后端 SSE（镜像 tutor.ts，新增 event:portrait 处理） ============ */

async function realDialogue(opts: DialogueStreamOptions): Promise<DialogueDone> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'text/event-stream',
  }
  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch('/api/v1/profile/dialogue', {
    method: 'POST',
    headers,
    body: JSON.stringify({ sessionId: opts.sessionId, message: opts.message, context: opts.context }),
  })

  // 非流式回包（401 / 业务码）：解信封抛业务码
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
  let done: DialogueDone | null = null

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
      done = {
        sessionId: payload.sessionId,
        suggestions: payload.suggestions ?? [],
        diagnosisComplete: !!payload.diagnosisComplete,
      }
    } else if (event === 'portrait') {
      if (Array.isArray(payload.updates) && payload.updates.length) opts.onPortrait(payload.updates)
    } else if (event === 'error') {
      throw new ApiError(payload.code ?? 2001, payload.message || '画像诊断回复生成失败')
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

/* ============ 本地 mock（脚本化多轮 · 逐 token 流式 · 边问边抽画像） ============ */

interface MockTurn {
  reply: string
  updates: Omit<PortraitDimension, 'updatedAt'>[]
  suggestions: string[]
  diagnosisComplete: boolean
}

/**
 * 脚本化诊断流：每条用户消息推进一轮，逐步填满 6 个异质维度（首轮抽 2 维），
 * 末轮 diagnosisComplete=true。维度取值遵守 17.1 防幻觉约束：
 * 推断维度（error_preference）标 inferred 且 confidence ≤ 0.6。
 */
const MOCK_SCRIPT: MockTurn[] = [
  {
    reply:
      '了解了。听起来你有一定的工程底子——那在「机器学习 / 神经网络」这块，你是系统学过，还是主要靠项目里边用边查？',
    updates: [
      { key: 'prior_experience', label: '先验经验', value: '有 Python 工程实践（爬虫 / 脚本）', confidence: 0.8, source: 'dialogue' },
      { key: 'knowledge_base', label: '知识基础', value: '有编程基础，ML 理论一般', score: 55, confidence: 0.7, source: 'dialogue' },
    ],
    suggestions: ['完整学过一些', '主要靠项目里边用边查', '基本零基础'],
    diagnosisComplete: false,
  },
  {
    reply:
      '明白了。那你平时更习惯怎么学新东西——是先把概念原理弄透再上手，还是先跑通一个例子、遇到问题再回头补理论？',
    updates: [
      { key: 'cognitive_style', label: '认知风格', value: '偏实践 / 动手型，先跑通再补理论', confidence: 0.65, source: 'dialogue' },
    ],
    suggestions: ['先弄懂原理再动手', '先跑通例子再补理论', '看情况，两者都有'],
    diagnosisComplete: false,
  },
  {
    reply:
      '这个学习方式很清晰。那你这次学习主要冲着什么目标去——是转岗 / 求职，还是项目需要、或单纯兴趣？方便的话说说想达到的程度。',
    updates: [
      { key: 'learning_goal', label: '学习目标', value: '转大模型应用工程师', confidence: 0.9, source: 'dialogue' },
    ],
    suggestions: ['转岗求职', '项目需要', '兴趣 / 自我提升'],
    diagnosisComplete: false,
  },
  {
    reply:
      '目标很明确。回想你之前学这些时，最容易卡住或弄混的地方通常是什么？比如某些概念总记不牢、或一到推导就发懵？',
    updates: [
      // 由「偏实践 / 概念理论一般」间接推断，故标 inferred + 低置信度（17.1 防幻觉约束）
      { key: 'error_preference', label: '易错点偏好', value: '概念易混淆（如梯度 / 反向传播）', confidence: 0.5, source: 'inferred' },
    ],
    suggestions: ['概念容易混', '数学推导发怵', '代码实现不熟'],
    diagnosisComplete: false,
  },
  {
    reply:
      '都记下了 ✦。最后一个——你大概能投入的学习节奏是怎样的？是每天稳定推进，还是周末集中冲、平时较零散？',
    updates: [
      { key: 'learning_pace', label: '学习节奏', value: '适中，偏稳扎稳打', confidence: 0.6, source: 'dialogue' },
    ],
    suggestions: ['每天稳定推进', '周末集中冲', '比较零散'],
    diagnosisComplete: false,
  },
  {
    reply:
      '好的，画像已经比较完整了 🎉 右侧 6 个维度都采集到了。我已经能据此为你定制学习路径——随时可以生成；后续学习和测验里，画像还会「随学随新」继续更新。',
    updates: [
      // 末轮据对话整体把知识基础 score 略作校准（体现可量化维度更新）
      { key: 'knowledge_base', label: '知识基础', value: '有编程基础，ML 理论待夯实', score: 62, confidence: 0.75, source: 'dialogue' },
    ],
    suggestions: ['生成学习路径', '我再补充几句'],
    diagnosisComplete: true,
  },
]

let mockSeq = 0
const mockTurns = new Map<string, number>()

const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms))

/** 逐 2~3 字符下发，模拟 SSE token 流式 */
async function streamText(text: string, onDelta: (d: string) => void) {
  for (let i = 0; i < text.length; i += 2) {
    onDelta(text.slice(i, i + 2))
    await sleep(20)
  }
}

async function mockDialogue(opts: DialogueStreamOptions): Promise<DialogueDone> {
  const sid = opts.sessionId ?? `d_mock_${++mockSeq}`
  const turn = mockTurns.get(sid) ?? 0
  const script = MOCK_SCRIPT[Math.min(turn, MOCK_SCRIPT.length - 1)]

  await streamText(script.reply, opts.onDelta)

  if (script.updates.length) {
    await sleep(160) // 追问语落定后再「抽出」画像，呈现边问边抽的节奏
    const now = new Date().toISOString()
    opts.onPortrait(script.updates.map((u) => ({ ...u, updatedAt: now })))
  }

  mockTurns.set(sid, turn + 1)
  return { sessionId: sid, suggestions: script.suggestions, diagnosisComplete: script.diagnosisComplete }
}
