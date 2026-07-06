/**
 * 学习流程（费曼 + 康奈尔）数据获取层（接口文档第 18 章，接口 39–44）。
 *
 * - 18.1 POST /learning/cornell-cues   康奈尔线索 + 主笔记骨架 + 总结引导
 * - 18.2 POST /learning/feynman        费曼讲解评估（SSE/JSON 双模式，SSE 同 15.4/17.1 体例）
 * - 18.3 GET/POST /learning/steps/{kp} 6 步过程进度（video|lecture|diagram|note|feynman|practice）
 * - 18.4 GET  /learning/notes/{kp}     读取康奈尔笔记
 * - 18.5 PUT  /learning/notes/{kp}     整体覆盖保存（前端防抖调用）
 *
 * Mock-first：USE_REAL_API=false 时返回与知识点相关的确定性假数据，并用模块内存
 * （noteStore / stepStore）维持「保存→回读一致」，无后端即可走通整条有序流。
 */
import { apiGet, apiPost, apiRequest, getToken } from './api'
import { USE_REAL_API } from './api'
import { kpById } from '../data/knowledgePoints'
import { ksPointById } from '../data/knowledgeSystem'
import type { KPStatus } from '../store/mastery'

/* ---------------- 类型（严格对齐 18 章契约字段名） ---------------- */

export interface CornellCue {
  id: string
  type: 'question' | 'keyword'
  text: string
}

export interface NoteOutline {
  id: string
  cueId: string | null
  heading: string
  points: string[]
}

export interface CornellCues {
  kpId: string
  difficulty: string
  cues: CornellCue[]
  noteOutline: NoteOutline[]
  summaryHint: string
  sources: { title: string; type: string; confidence: number }[]
}

export interface CueNote {
  cueId: string
  text: string
}

export interface CornellNote {
  kpId: string
  cueNotes: CueNote[]
  mainNotes: string
  summary: string
  updatedAt: string
}

export type StepKey = 'video' | 'lecture' | 'diagram' | 'note' | 'feynman' | 'practice'
export const STEP_KEYS: StepKey[] = ['video', 'lecture', 'diagram', 'note', 'feynman', 'practice']

export interface StepProgress {
  kpId: string
  steps: Record<string, boolean>
  mastery: KPStatus
  completedCount: number
  total: number
  updatedAt: string
}

export interface ReviewRef {
  kind: string
  title: string
  kpId: string
  endpoint: string
  difficulty?: string
}

export interface FeynmanGap {
  id: string
  kpId: string
  title: string
  detail: string
  severity: 'high' | 'medium' | 'low'
  review?: ReviewRef[]
}

export interface FeynmanDone {
  sessionId: string
  score: number | null
  followups: string[]
  complete: boolean
}

/* ---------------- 18.1 康奈尔线索生成 ---------------- */

/** nn（神经网络基础）的确定性 mock 线索/骨架；其余知识点用通用骨架按名称填充。 */
function mockCues(kpId: string, difficulty: string): CornellCues {
  const name = kpById(kpId)?.name ?? ksPointById(kpId)?.name ?? '当前知识点'
  if (kpId === 'nn') {
    return {
      kpId,
      difficulty,
      cues: [
        { id: 'c1', type: 'question', text: '为什么神经网络需要激活函数？' },
        { id: 'c2', type: 'question', text: '前向传播与反向传播分别解决什么问题？' },
        { id: 'c3', type: 'keyword', text: '加权求和 → 偏置 → 激活' },
        { id: 'c4', type: 'question', text: '梯度下降是如何更新权重的？' },
        { id: 'c5', type: 'keyword', text: 'ReLU / Sigmoid / Tanh' },
      ],
      noteOutline: [
        {
          id: 'n1',
          cueId: 'c1',
          heading: '激活函数的作用',
          points: ['引入非线性表达能力', '若无激活，多层网络等价于单层线性变换'],
        },
        {
          id: 'n2',
          cueId: 'c2',
          heading: '前向 / 反向传播',
          points: ['前向：输入逐层加权激活得到输出', '反向：链式法则回传误差，算出各权重梯度'],
        },
        {
          id: 'n3',
          cueId: 'c3',
          heading: '神经元三步运算',
          points: ['加权求和 Σ w·x', '加偏置 +b', '经激活函数输出'],
        },
      ],
      summaryHint: '用一句话概括：神经网络如何通过逐层加权与非线性激活拟合复杂函数？',
      sources: [
        { title: '《深度学习》花书 第 6 章', type: '教材', confidence: 0.9 },
        { title: 'CS231n: Neural Networks（Stanford）', type: '课程', confidence: 0.88 },
      ],
    }
  }
  return {
    kpId,
    difficulty,
    cues: [
      { id: 'c1', type: 'question', text: `「${name}」要解决的核心问题是什么？` },
      { id: 'c2', type: 'question', text: `「${name}」的关键步骤/组成有哪些？` },
      { id: 'c3', type: 'keyword', text: `${name} · 核心概念` },
      { id: 'c4', type: 'question', text: `它与上一个知识点是如何衔接的？` },
    ],
    noteOutline: [
      { id: 'n1', cueId: 'c1', heading: `${name} 概述`, points: ['它解决的问题', '为什么重要'] },
      { id: 'n2', cueId: 'c2', heading: '关键步骤', points: ['步骤一', '步骤二'] },
    ],
    summaryHint: `用一句话概括「${name}」的核心思想。`,
    sources: [{ title: 'RAG 知识库检索来源', type: '文档', confidence: 0.86 }],
  }
}

/** 18.1 生成康奈尔线索 + 主笔记骨架 + 总结引导。 */
export async function getCornellCues(kpId: string, difficulty = '初级'): Promise<CornellCues> {
  if (!USE_REAL_API) return mockCues(kpId, difficulty)
  return apiPost<CornellCues>('/learning/cornell-cues', { kpId, difficulty })
}

/* ---------------- 18.4 / 18.5 康奈尔笔记（mock 用内存维持回读一致） ---------------- */

const noteStore = new Map<string, CornellNote>()
const nowIso = () => new Date().toISOString()

/** 18.4 读取康奈尔笔记；无则返回空笔记（不视为错误，同契约口径）。 */
export async function getCornellNote(kpId: string): Promise<CornellNote> {
  if (!USE_REAL_API) {
    return (
      noteStore.get(kpId) ?? {
        kpId,
        cueNotes: [],
        mainNotes: '',
        summary: '',
        updatedAt: nowIso(),
      }
    )
  }
  return apiGet<CornellNote>(`/learning/notes/${kpId}`)
}

/** 18.5 整体覆盖保存康奈尔笔记（前端防抖调用），返回盖戳后的笔记。 */
export async function saveCornellNote(
  kpId: string,
  note: { cueNotes: CueNote[]; mainNotes: string; summary: string }
): Promise<CornellNote> {
  if (!USE_REAL_API) {
    const saved: CornellNote = { kpId, ...note, updatedAt: nowIso() }
    noteStore.set(kpId, saved)
    return saved
  }
  return apiRequest<CornellNote>(`/learning/notes/${kpId}`, { method: 'PUT', body: note })
}

/* ---------------- 18.3 学习步骤进度（mock 用内存维持） ---------------- */

const stepStore = new Map<string, Record<string, boolean>>()

function buildProgress(kpId: string, steps: Record<string, boolean>, mastery: KPStatus): StepProgress {
  const completedCount = STEP_KEYS.filter((k) => steps[k]).length
  return { kpId, steps, mastery, completedCount, total: STEP_KEYS.length, updatedAt: nowIso() }
}

/** 18.3 读取某知识点 6 步过程进度（mastery 透传，仅作展示；「已掌握」以 7.1 为准）。 */
export async function getSteps(kpId: string): Promise<StepProgress> {
  if (!USE_REAL_API) {
    const steps = stepStore.get(kpId) ?? {}
    return buildProgress(kpId, steps, 'learning')
  }
  return apiGet<StepProgress>(`/learning/steps/${kpId}`)
}

/** 18.3 标记某步骤完成 / 取消（幂等），返回刷新后的整体进度。 */
export async function markStep(kpId: string, step: StepKey, done: boolean): Promise<StepProgress> {
  if (!USE_REAL_API) {
    const steps = { ...(stepStore.get(kpId) ?? {}), [step]: done }
    stepStore.set(kpId, steps)
    return buildProgress(kpId, steps, 'learning')
  }
  return apiPost<StepProgress>(`/learning/steps/${kpId}`, { step, done })
}

/* ---------------- 18.2 费曼讲解评估（SSE / mock 流式） ---------------- */

export interface FeynmanStreamOptions {
  kpId: string
  /** 多轮上下文，首轮可空（由后端 done 事件带回）。 */
  sessionId?: string
  /** 学生本轮「讲解」文本。 */
  explanation: string
  /** 逐 delta 点评 / 追问片段。 */
  onDelta: (delta: string) => void
  /** 本轮识别出的知识缺口（通常末尾下发一次）。 */
  onGaps: (gaps: FeynmanGap[]) => void
}

/** mock：每个 sessionId 的轮次计数，用于第二轮起减少缺口并判定 complete（避免重复点评）。 */
const mockFeynmanTurn = new Map<string, number>()
const delay = (ms: number) => new Promise((r) => window.setTimeout(r, ms))

async function mockFeynman(opts: FeynmanStreamOptions): Promise<FeynmanDone> {
  const sid = opts.sessionId ?? `f_mock_${noteStore.size}_${stepStore.size}_${opts.explanation.length}`
  const turn = (mockFeynmanTurn.get(sid) ?? 0) + 1
  mockFeynmanTurn.set(sid, turn)

  const said = opts.explanation
  const mentionedActivation = /激活|非线性|relu|sigmoid|tanh/i.test(said)
  const mentionedBackprop = /反向|梯度|backprop|损失|下降/i.test(said)

  const first =
    turn === 1
      ? [
          '我听到了你的讲解，',
          '你抓住了「加权求和」这一步，思路是对的——',
          mentionedActivation
            ? '也提到了激活函数，很好。'
            : '但有个关键环节被跳过了：你没有提到**激活函数**。',
          mentionedBackprop ? '反向传播也覆盖到了。' : '另外，网络是怎么「学」的（反向传播 + 梯度下降）也还没讲清。',
        ]
      : [
          '这一版比上一轮完整多了！',
          '你把非线性与权重更新都讲到了，',
          '说明你已经把这条链路想通了 🎉。',
        ]

  for (const chunk of first) {
    await delay(280)
    opts.onDelta(chunk)
  }

  const gaps: FeynmanGap[] = []
  if (turn === 1 && !mentionedActivation) {
    gaps.push({
      id: 'g1',
      kpId: opts.kpId,
      title: '遗漏激活函数（非线性）',
      detail: '讲解中只到加权求和，未提到激活函数，而非线性正是神经网络区别于线性模型的核心。',
      severity: 'high',
      review: [
        { kind: 'lecture', title: '《神经网络基础》自适应讲义', kpId: opts.kpId, endpoint: '/resource/lecture', difficulty: '初级' },
        { kind: 'diagram', title: '神经网络基础 · 知识图解', kpId: opts.kpId, endpoint: '/resource/diagram' },
      ],
    })
  }
  if (turn === 1 && !mentionedBackprop) {
    gaps.push({
      id: 'g2',
      kpId: opts.kpId,
      title: '未说明「网络如何学习」',
      detail: '没有提到反向传播与梯度下降——这是权重得以更新、网络得以收敛的机制。',
      severity: 'medium',
      review: [
        { kind: 'video', title: '神经网络基础 · 讲解视频', kpId: opts.kpId, endpoint: '/resource/video' },
      ],
    })
  }
  if (gaps.length) {
    await delay(320)
    opts.onGaps(gaps)
  }

  const complete = gaps.length === 0
  const score = turn === 1 ? (mentionedActivation ? 78 : 62) : 92
  const followups = complete
    ? []
    : ['如果去掉激活函数，三层网络和一层有什么区别？', '损失变大时，权重应该往哪个方向调整？']
  return { sessionId: sid, score, followups, complete }
}

/** 18.2 费曼讲解评估（SSE 流式；mock 模式走本地流式模拟）。失败抛错由调用方兜底。 */
export async function feynmanStream(opts: FeynmanStreamOptions): Promise<FeynmanDone> {
  if (!USE_REAL_API) return mockFeynman(opts)

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'text/event-stream',
  }
  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch('/api/v1/learning/feynman', {
    method: 'POST',
    headers,
    body: JSON.stringify({ kpId: opts.kpId, sessionId: opts.sessionId, explanation: opts.explanation }),
  })

  const ctype = res.headers.get('content-type') ?? ''
  // 后端未走 SSE（返回整体 JSON 信封或错误）：解信封取终态字段
  if (!ctype.includes('text/event-stream')) {
    const env = (await res.json()) as { code?: number; message?: string; data?: Record<string, unknown> }
    if (env.code && env.code !== 0) throw new Error(env.message || '费曼评估失败')
    const d = (env.data ?? {}) as Record<string, unknown>
    if (typeof d.feedback === 'string') opts.onDelta(d.feedback)
    if (Array.isArray(d.gaps)) opts.onGaps(d.gaps as FeynmanGap[])
    return {
      sessionId: String(d.sessionId ?? ''),
      score: (d.score as number) ?? null,
      followups: (d.followups as string[]) ?? [],
      complete: Boolean(d.complete),
    }
  }
  if (!res.body) throw new Error('当前环境不支持流式读取')

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  let done: FeynmanDone | null = null

  const handleEvent = (block: string) => {
    let event = 'message'
    const dataLines: string[] = []
    for (const line of block.split('\n')) {
      if (line.startsWith('event:')) event = line.slice(6).trim()
      else if (line.startsWith('data:')) dataLines.push(line.slice(5).trimStart())
    }
    if (!dataLines.length) return
    const payload = JSON.parse(dataLines.join('\n'))
    if (event === 'gaps') {
      opts.onGaps((payload.gaps ?? []) as FeynmanGap[])
    } else if (event === 'done') {
      done = {
        sessionId: payload.sessionId,
        score: payload.score ?? null,
        followups: payload.followups ?? [],
        complete: Boolean(payload.complete),
      }
    } else if (event === 'error') {
      throw new Error(payload.message || '费曼评估生成失败')
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
    reader.cancel().catch(() => {})
  }

  if (!done) throw new Error('费曼流式响应未正常结束')
  return done
}

/* ---------------- 工具：18.1 noteOutline → 主笔记区预填 Markdown ---------------- */

/** 把主笔记骨架渲染为可继续编辑的 Markdown（康奈尔右栏初始内容）。 */
export function outlineToMarkdown(outline: NoteOutline[]): string {
  return outline
    .map((o) => `## ${o.heading}\n${o.points.map((p) => `- ${p}`).join('\n')}`)
    .join('\n\n')
}
