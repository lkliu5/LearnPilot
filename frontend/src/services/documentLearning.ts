/**
 * 文档学习·数据获取层（接口文档第 20 章：上传→独立向量集合→基于文档的生成）。
 *
 * - 联调（USE_REAL_API）：走真实后端 /document/* 系列接口，生成内容严格溯源自用户上传文档；
 *   各生成接口由后端旁路以 source="document" 自动埋点到「我的资源库」。
 * - mock：全程本地合成（内存文档表 + 从文档正文派生的假产物），无任何后端 / Key 也能跑通
 *   「上传 → 选中 → 生成六类 → 展示 / 下载」全链路（与项目 Mock-first 纪律一致）。
 *
 * 与 services/resource.ts（内置课程知识点资源）互不影响：这里只处理「用户自带文档」。
 */
import { apiGet, apiPost, apiPostForm, apiRequest, USE_REAL_API } from './api'
import type { LectureScene } from '../remotion/LectureVideo'
import type { QuizQuestion } from '../components/QuizRenderer'
import type { SourceRef } from '../components/SourceTrace'

/* ---------------- 类型（严格对齐接口文档 20.x 字段名） ---------------- */

export type DocFileType = 'pdf' | 'md' | 'txt' | 'docx'
export type DocStatus = 'pending' | 'indexing' | 'indexed' | 'failed'

/** 上传文档实体（20.1 document）。 */
export interface DocumentItem {
  id: string
  title: string
  filename: string
  fileType: DocFileType
  size: number
  status: DocStatus
  chunks: number
  error: string | null
  uploadedAt: string
}

export interface UploadResult {
  taskId: string
  document: DocumentItem
}

/** 后端 sources（confidence 为 0-1）→ SourceTrace 需要的 0-100 百分比。 */
interface RawSource {
  title: string
  type: string
  confidence: number
}
const SRC_TYPES: SourceRef['type'][] = ['教材', '论文', '文档', '课程']
export function toSourceRefs(raw?: RawSource[]): SourceRef[] {
  if (!raw?.length) return []
  return raw.map((s) => ({
    title: s.title,
    type: (SRC_TYPES.includes(s.type as SourceRef['type']) ? s.type : '文档') as SourceRef['type'],
    confidence: s.confidence <= 1 ? Math.round(s.confidence * 100) : Math.round(s.confidence),
  }))
}

export interface LectureResult {
  markdown: string
  difficulty: string
  sources: SourceRef[]
  hallucinationRate: number
}
export interface VideoResult {
  title: string
  difficulty: string
  scenes: LectureScene[]
  sources: SourceRef[]
}
export interface DiagramResult {
  mermaid: string
  sources: SourceRef[]
}
export interface MindmapResult {
  markdown: string
}
export interface QuizResult {
  questions: QuizQuestion[]
  sources: SourceRef[]
}
export interface FlashcardCard {
  front: string
  back: string
}
export interface FlashcardResult {
  cards: FlashcardCard[]
  sources: SourceRef[]
}
/** 文档概览（NotebookLM 式速读）：是什么 / 讲了什么 / 结构概况 / 关键点。 */
export interface OverviewResult {
  summary: string
  about: string
  structure: string
  keyPoints: string[]
  sources: SourceRef[]
}

/* ================================================================== *
 *  mock：内存文档表 + 从正文派生的确定性假产物（无后端时全链路可跑）
 * ================================================================== */

const mockDocs: DocumentItem[] = []
/** docId → 解析出的正文（用于让生成内容「看得出来自该文档」）。 */
const mockContent: Record<string, string> = {}

let mockSeq = 0
const mockId = () => `udoc_mock${(++mockSeq).toString(36)}${Date.now().toString(36).slice(-4)}`

function extToType(name: string): DocFileType {
  const ext = name.split('.').pop()?.toLowerCase() ?? ''
  if (ext === 'pdf') return 'pdf'
  if (ext === 'md' || ext === 'markdown') return 'md'
  if (ext === 'docx' || ext === 'doc') return 'docx'
  return 'txt'
}

/** 从正文切出若干「要点句」（供派生讲义/闪卡/测试，体现内容取自文档）。 */
function keySentences(text: string, n: number): string[] {
  const parts = text
    .replace(/\s+/g, ' ')
    .split(/(?<=[。！？.!?；;\n])/)
    .map((s) => s.trim())
    .filter((s) => s.length >= 6)
  if (parts.length >= n) return parts.slice(0, n)
  // 正文不足（如 PDF 无法本地解析）时用占位，保证结构完整
  const pad = Array.from({ length: n - parts.length }, (_, i) => `文档要点 ${parts.length + i + 1}`)
  return [...parts, ...pad]
}

const mockSources = (doc: DocumentItem): SourceRef[] => [
  { title: `${doc.title} · 段落 1`, type: '文档', confidence: 94 },
  { title: `${doc.title} · 段落 3`, type: '文档', confidence: 88 },
  { title: `${doc.title} · 段落 6`, type: '文档', confidence: 82 },
]

function buildMockLecture(doc: DocumentItem, difficulty: string): LectureResult {
  const sents = keySentences(mockContent[doc.id] ?? '', 6)
  const md = [
    `# ${doc.title}`,
    ``,
    `> 本讲义由 AI 基于你上传的《${doc.filename}》生成，内容严格取自文档（难度：${difficulty}）。`,
    ``,
    `## 一、核心概览`,
    ``,
    sents[0],
    ``,
    `## 二、要点精讲`,
    ``,
    `1. ${sents[1]}`,
    `2. ${sents[2]}`,
    `3. ${sents[3]}`,
    ``,
    `## 三、延伸理解`,
    ``,
    sents[4],
    ``,
    `## 四、小结`,
    ``,
    `- ${sents[5]}`,
    `- 建议结合原文档对照复习，并完成配套练习题 / 闪卡巩固。`,
    ``,
  ].join('\n')
  return { markdown: md, difficulty, sources: mockSources(doc), hallucinationRate: 0.12 }
}

function buildMockVideo(doc: DocumentItem, difficulty: string): VideoResult {
  const s = keySentences(mockContent[doc.id] ?? '', 6)
  const scenes: LectureScene[] = [
    { title: `导入 · ${doc.title}`, points: [s[0].slice(0, 28), '本视频取材自你的文档'], narration: `欢迎学习《${doc.title}》。${s[0]}` },
    { title: '核心要点', points: [s[1].slice(0, 24), s[2].slice(0, 24)], narration: `${s[1]} ${s[2]}` },
    { title: '深入理解', points: [s[3].slice(0, 24), s[4].slice(0, 24)], narration: `${s[3]} ${s[4]}` },
    { title: '总结回顾', points: [s[5].slice(0, 24), '完成练习巩固'], narration: `本节小结：${s[5]}` },
  ]
  return { title: doc.title, difficulty, scenes, sources: mockSources(doc) }
}

function buildMockDiagram(doc: DocumentItem): DiagramResult {
  const s = keySentences(mockContent[doc.id] ?? '', 4).map((t) => t.slice(0, 12).replace(/[[\]{}()"]/g, ''))
  const mermaid = [
    'flowchart TD',
    `  A["${doc.title}"] --> B["${s[0]}"]`,
    `  A --> C["${s[1]}"]`,
    `  B --> D["${s[2]}"]`,
    `  C --> E["${s[3]}"]`,
    `  D --> F["综合应用"]`,
    `  E --> F`,
  ].join('\n')
  return { mermaid, sources: mockSources(doc) }
}

function buildMockOverview(doc: DocumentItem): OverviewResult {
  const s = keySentences(mockContent[doc.id] ?? '', 6)
  const topic = s[0].slice(0, 24).replace(/[，,。.；;：:\s]+$/, '')
  return {
    summary: `《${doc.title}》是一篇围绕「${topic}」展开的资料。`,
    about: s.slice(0, 2).join('').slice(0, 180),
    structure: `全文自「${s[0].slice(0, 14)}」切入，逐步展开到「${s[s.length - 1].slice(0, 14)}」，共梳理约 ${s.length} 个要点。`,
    keyPoints: s.slice(0, 5),
    sources: mockSources(doc),
  }
}

function buildMockMindmap(doc: DocumentItem): MindmapResult {
  const s = keySentences(mockContent[doc.id] ?? '', 6).map((t) => t.slice(0, 18))
  const md = [
    `# ${doc.title}`,
    `## 核心概览`,
    `### ${s[0]}`,
    `## 要点精讲`,
    `### ${s[1]}`,
    `### ${s[2]}`,
    `### ${s[3]}`,
    `## 延伸与小结`,
    `### ${s[4]}`,
    `### ${s[5]}`,
  ].join('\n')
  return { markdown: md }
}

function buildMockQuiz(doc: DocumentItem, count: number): QuizResult {
  const s = keySentences(mockContent[doc.id] ?? '', count + 2)
  const questions: QuizQuestion[] = Array.from({ length: count }, (_, i) => ({
    question_id: `docq_${i + 1}`,
    question_type: i % 3 === 2 ? 'boolean' : 'single',
    question_text:
      i % 3 === 2
        ? `判断：根据《${doc.title}》，“${s[i].slice(0, 22)}…”这一说法成立。`
        : `根据《${doc.title}》，下列关于“${s[i].slice(0, 18)}”的说法，哪一项与文档一致？`,
    options:
      i % 3 === 2
        ? [
            { option_id: 'a', option_text: '正确' },
            { option_id: 'b', option_text: '错误' },
          ]
        : [
            { option_id: 'a', option_text: s[i].slice(0, 26) || '与文档一致的表述' },
            { option_id: 'b', option_text: '与文档无关的干扰项 ①' },
            { option_id: 'c', option_text: '与文档相反的表述' },
            { option_id: 'd', option_text: '与文档无关的干扰项 ②' },
          ],
    correct_answer: 'a',
    explanation: `依据文档原文：${s[i]}`,
  }))
  return { questions, sources: mockSources(doc) }
}

function buildMockFlashcards(doc: DocumentItem, count: number): FlashcardResult {
  const s = keySentences(mockContent[doc.id] ?? '', count)
  const cards: FlashcardCard[] = s.slice(0, count).map((sent, i) => ({
    front: `关于《${doc.title}》的要点 ${i + 1}：文档是怎么讲的？`,
    back: sent,
  }))
  return { cards, sources: mockSources(doc) }
}

/** mock：把上传文件读成文本（md/txt 可读；pdf/docx 本地读不了则给占位正文）。 */
function readFileText(file: File): Promise<string> {
  const t = extToType(file.name)
  if (t === 'pdf' || t === 'docx') {
    return Promise.resolve(
      `《${file.name}》为二进制文档（${t.toUpperCase()}），本地演示模式下不解析其正文。` +
        `联调真实后端后将完成解析、切块与向量化，并据此生成溯源可查的讲义、视频、图解、导图、练习题与闪卡。`
    )
  }
  return new Promise((resolve) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result ?? ''))
    reader.onerror = () => resolve('')
    reader.readAsText(file)
  })
}

/* ================================================================== *
 *  对外 API（联调走后端，mock 走本地合成）
 * ================================================================== */

/** 20.1 上传文档（multipart，字段名 file）。mock 立即置 indexed。 */
export async function uploadDocument(file: File): Promise<UploadResult> {
  if (USE_REAL_API) {
    const form = new FormData()
    form.append('file', file)
    return apiPostForm<UploadResult>('/document/upload', form)
  }
  const text = await readFileText(file)
  const now = new Date().toISOString()
  const doc: DocumentItem = {
    id: mockId(),
    title: file.name.replace(/\.[^.]+$/, ''),
    filename: file.name,
    fileType: extToType(file.name),
    size: file.size,
    status: 'indexed',
    chunks: Math.max(1, Math.round((text.length || 200) / 180)),
    error: null,
    uploadedAt: now,
  }
  mockContent[doc.id] = text
  mockDocs.unshift(doc)
  return { taskId: `t_mock_${doc.id}`, document: doc }
}

/** 20.2 我的文档列表（按上传时间倒序）。 */
export async function listDocuments(): Promise<DocumentItem[]> {
  if (USE_REAL_API) {
    const d = await apiGet<{ items: DocumentItem[]; total: number }>('/document/list')
    return d.items ?? []
  }
  return [...mockDocs]
}

/** 20.3 文档详情（含 contentPreview）。用于上传后轮询状态直至 indexed。 */
export async function getDocument(docId: string): Promise<DocumentItem> {
  if (USE_REAL_API) {
    return apiGet<DocumentItem & { contentPreview?: string }>(`/document/${docId}`)
  }
  const d = mockDocs.find((x) => x.id === docId)
  if (!d) throw new Error('document not found')
  return d
}

/** 20.4 删除文档（连同其独立向量集合）。 */
export async function deleteDocument(docId: string): Promise<void> {
  if (USE_REAL_API) {
    await apiRequest(`/document/${docId}`, { method: 'DELETE' })
    return
  }
  const i = mockDocs.findIndex((x) => x.id === docId)
  if (i >= 0) mockDocs.splice(i, 1)
  delete mockContent[docId]
}

/** 上传后轮询文档状态直至 indexed / failed（联调用；mock 已 indexed 立即返回）。 */
export async function waitIndexed(
  docId: string,
  onTick?: (doc: DocumentItem) => void,
  tries = 20
): Promise<DocumentItem> {
  let doc = await getDocument(docId)
  onTick?.(doc)
  for (let i = 0; i < tries && (doc.status === 'pending' || doc.status === 'indexing'); i++) {
    await new Promise((r) => window.setTimeout(r, 1200))
    doc = await getDocument(docId)
    onTick?.(doc)
  }
  return doc
}

/* -------- 20.5 ~ 20.7 六类内容生成（均基于 documentId，溯源自该文档） -------- */

/** 文档概览（选中文档即自动生成展示）：内容取自该文档，联调走后端、离线走 mock。 */
export async function generateOverview(docId: string): Promise<OverviewResult> {
  if (USE_REAL_API) {
    const d = await apiPost<{
      overview: { summary: string; about: string; structure: string; keyPoints: string[] }
      sources: RawSource[]
    }>('/document/generate/overview', { documentId: docId })
    const o = d.overview ?? { summary: '', about: '', structure: '', keyPoints: [] }
    return {
      summary: o.summary ?? '',
      about: o.about ?? '',
      structure: o.structure ?? '',
      keyPoints: Array.isArray(o.keyPoints) ? o.keyPoints : [],
      sources: toSourceRefs(d.sources),
    }
  }
  await mockDelay()
  return buildMockOverview(await getDocument(docId))
}

export async function generateLecture(docId: string, difficulty = '初级'): Promise<LectureResult> {
  if (USE_REAL_API) {
    const d = await apiPost<{ markdown: string; difficulty: string; sources: RawSource[]; hallucinationRate: number }>(
      '/document/generate/lecture',
      { documentId: docId, difficulty }
    )
    return {
      markdown: d.markdown,
      difficulty: d.difficulty ?? difficulty,
      sources: toSourceRefs(d.sources),
      hallucinationRate: d.hallucinationRate ?? 0,
    }
  }
  await mockDelay()
  return buildMockLecture(await getDocument(docId), difficulty)
}

export async function generateVideo(docId: string, difficulty = '初级'): Promise<VideoResult> {
  if (USE_REAL_API) {
    const d = await apiPost<{
      title: string
      difficulty: string
      scenes: { title: string; points: string[]; narration: string }[]
      sources: RawSource[]
    }>('/document/generate/video', { documentId: docId, difficulty })
    return {
      title: d.title,
      difficulty: d.difficulty ?? difficulty,
      scenes: (d.scenes ?? []).map((s) => ({ title: s.title, points: s.points, narration: s.narration })),
      sources: toSourceRefs(d.sources),
    }
  }
  await mockDelay()
  return buildMockVideo(await getDocument(docId), difficulty)
}

export async function generateDiagram(docId: string): Promise<DiagramResult> {
  if (USE_REAL_API) {
    const d = await apiPost<{ mermaid: string; sources: RawSource[] }>('/document/generate/diagram', {
      documentId: docId,
    })
    return { mermaid: d.mermaid, sources: toSourceRefs(d.sources) }
  }
  await mockDelay()
  return buildMockDiagram(await getDocument(docId))
}

export async function generateMindmap(docId: string): Promise<MindmapResult> {
  if (USE_REAL_API) {
    const d = await apiPost<{ markdown: string }>('/document/generate/mindmap', { documentId: docId })
    return { markdown: d.markdown }
  }
  await mockDelay()
  return buildMockMindmap(await getDocument(docId))
}

export async function generateQuiz(docId: string, count = 5): Promise<QuizResult> {
  if (USE_REAL_API) {
    const d = await apiPost<{ questions: QuizQuestion[]; sources: RawSource[] }>('/document/generate/quiz', {
      documentId: docId,
      count,
    })
    return { questions: d.questions ?? [], sources: toSourceRefs(d.sources) }
  }
  await mockDelay()
  return buildMockQuiz(await getDocument(docId), count)
}

export async function generateFlashcards(docId: string, count = 8): Promise<FlashcardResult> {
  if (USE_REAL_API) {
    const d = await apiPost<{ cards: FlashcardCard[]; sources: RawSource[] }>('/document/generate/flashcards', {
      documentId: docId,
      count,
    })
    return { cards: d.cards ?? [], sources: toSourceRefs(d.sources) }
  }
  await mockDelay()
  return buildMockFlashcards(await getDocument(docId), count)
}

/** mock 生成拟真延时（体现「AI 生成中」loading 态）。 */
function mockDelay() {
  return new Promise((r) => window.setTimeout(r, 900))
}

/* ---------------- 展示辅助 ---------------- */

export const DOC_FILE_ACCEPT = '.pdf,.txt,.md,.markdown,.docx'
export const DOC_MAX_MB = 20

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / (1024 * 1024)).toFixed(1)} MB`
}
