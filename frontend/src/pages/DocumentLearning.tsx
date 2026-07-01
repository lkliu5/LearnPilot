import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import type { PageType } from '../App'
import PageHeader from '../components/PageHeader'
import MarkdownRenderer from '../components/MarkdownRenderer'
import QuizRenderer from '../components/QuizRenderer'
import SourceTrace from '../components/SourceTrace'
import FlashcardDeck from '../components/FlashcardDeck'
import { exportLectureMarkdown, exportLectureToPdf } from '../utils/lectureExport'
/* 复用学习资源页的共享样式（讲义导出条 / 难度切换 / loading / 各渲染组件的导出工具条等，
   均为 class 前缀样式、无全局副作用），保证复用的渲染/下载组件在本页样式一致。 */
import '../pages/LearningResource.css'
import {
  DOC_FILE_ACCEPT,
  DOC_MAX_MB,
  deleteDocument,
  formatBytes,
  generateDiagram,
  generateFlashcards,
  generateLecture,
  generateMindmap,
  generateQuiz,
  generateVideo,
  listDocuments,
  uploadDocument,
  waitIndexed,
  type DiagramResult,
  type DocumentItem,
  type FlashcardResult,
  type LectureResult,
  type MindmapResult,
  type QuizResult,
  type VideoResult,
} from '../services/documentLearning'
import './DocumentLearning.css'

const MindMap = lazy(() => import('../components/MindMap'))
const MermaidDiagram = lazy(() => import('../components/MermaidDiagram'))
const VideoLecture = lazy(() => import('../components/VideoLecture'))

const Loading = () => <div className="resource-loading">资源加载中…</div>

type Kind = 'lecture' | 'video' | 'diagram' | 'mindmap' | 'quiz' | 'flashcards'
const LEVELS = ['入门', '初级', '中级', '高级', '精通'] as const

interface ArtifactBag {
  lecture?: LectureResult
  video?: VideoResult
  diagram?: DiagramResult
  mindmap?: MindmapResult
  quiz?: QuizResult
  flashcards?: FlashcardResult
}

const KIND_META: { id: Kind; label: string; desc: string; icon: string }[] = [
  { id: 'lecture', label: '定制讲义', desc: '结构化 Markdown 讲义', icon: '📖' },
  { id: 'video', label: '讲解视频', desc: '分镜脚本 + 同步旁白', icon: '🎬' },
  { id: 'diagram', label: '知识图解', desc: 'Mermaid 流程图', icon: '🧩' },
  { id: 'mindmap', label: '思维导图', desc: '脉络树状图', icon: '🗺️' },
  { id: 'quiz', label: '练习题', desc: '分阶自测题', icon: '📝' },
  { id: 'flashcards', label: '记忆闪卡', desc: '正反翻卡速记', icon: '🃏' },
]

const STATUS_LABEL: Record<DocumentItem['status'], string> = {
  pending: '待处理',
  indexing: '解析入库中',
  indexed: '就绪',
  failed: '失败',
}

export default function DocumentLearning({ onNavigate: _onNavigate }: { onNavigate?: (page: PageType) => void }) {
  const [docs, setDocs] = useState<DocumentItem[]>([])
  const [loadingDocs, setLoadingDocs] = useState(true)
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const [uploading, setUploading] = useState(false)
  const [uploadErr, setUploadErr] = useState<string | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  /** docId → 已生成产物集合（切换文档即切换视图）。 */
  const [bags, setBags] = useState<Record<string, ArtifactBag>>({})
  const [activeKind, setActiveKind] = useState<Kind | null>(null)
  const [genKind, setGenKind] = useState<Kind | null>(null)
  const [genErr, setGenErr] = useState<string | null>(null)
  const [difficulty, setDifficulty] = useState<string>('初级')

  const lectureRef = useRef<HTMLDivElement>(null)

  /* 挂载：拉取我的文档列表 */
  useEffect(() => {
    listDocuments()
      .then((items) => {
        setDocs(items)
        if (items.length) setSelectedId((cur) => cur ?? items[0].id)
      })
      .catch((e) => console.error('[doclearn] 加载文档列表失败', e))
      .finally(() => setLoadingDocs(false))
  }, [])

  const selectedDoc = docs.find((d) => d.id === selectedId) ?? null
  const bag = selectedId ? bags[selectedId] ?? {} : {}

  /* 切换选中文档：把视图切到该文档已生成的第一个产物（没有则回到操作引导） */
  useEffect(() => {
    if (!selectedId) {
      setActiveKind(null)
      return
    }
    const b = bags[selectedId]
    const first = b ? (KIND_META.map((k) => k.id).find((k) => b[k]) ?? null) : null
    setActiveKind(first)
    setGenErr(null)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId])

  /* ---------------- 上传 ---------------- */

  const validate = (file: File): string | null => {
    const ok = DOC_FILE_ACCEPT.split(',').some((e) => file.name.toLowerCase().endsWith(e.trim()))
    if (!ok) return `不支持的文件类型：${file.name}（仅支持 PDF / TXT / MD / DOCX）`
    if (file.size > DOC_MAX_MB * 1024 * 1024) return `文件过大：${file.name}（上限 ${DOC_MAX_MB}MB）`
    return null
  }

  const handleFiles = async (files: FileList | File[]) => {
    const list = Array.from(files)
    if (!list.length) return
    setUploadErr(null)
    for (const file of list) {
      const err = validate(file)
      if (err) {
        setUploadErr(err)
        continue
      }
      setUploading(true)
      try {
        const { document } = await uploadDocument(file)
        setDocs((prev) => [document, ...prev.filter((d) => d.id !== document.id)])
        setSelectedId(document.id)
        // 联调下解析/向量化异步：轮询状态直至 indexed，实时回填列表徽章
        if (document.status !== 'indexed' && document.status !== 'failed') {
          void waitIndexed(document.id, (d) =>
            setDocs((prev) => prev.map((x) => (x.id === d.id ? d : x)))
          )
        }
      } catch (e) {
        console.error('[doclearn] 上传失败', e)
        setUploadErr(`上传失败：${file.name}`)
      } finally {
        setUploading(false)
      }
    }
  }

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    if (e.dataTransfer.files?.length) void handleFiles(e.dataTransfer.files)
  }

  const handleDelete = async (docId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    const doc = docs.find((d) => d.id === docId)
    if (!window.confirm(`确定删除文档「${doc?.title ?? docId}」及其生成资料？`)) return
    try {
      await deleteDocument(docId)
    } catch (err) {
      console.error('[doclearn] 删除失败', err)
    }
    setDocs((prev) => prev.filter((d) => d.id !== docId))
    setBags((prev) => {
      const next = { ...prev }
      delete next[docId]
      return next
    })
    if (selectedId === docId) setSelectedId((cur) => (cur === docId ? null : cur))
  }

  /* ---------------- 生成 ---------------- */

  const runGenerate = async (kind: Kind, opts?: { diff?: string; regen?: boolean }) => {
    if (!selectedId || genKind) return
    const doc = docs.find((d) => d.id === selectedId)
    if (!doc) return
    if (doc.status !== 'indexed') {
      setGenErr('文档正在解析入库，请稍候再生成。')
      return
    }
    // 已生成且非强制重生成 → 直接切视图
    if (!opts?.regen && bags[selectedId]?.[kind]) {
      setActiveKind(kind)
      return
    }
    setGenErr(null)
    setGenKind(kind)
    const diff = opts?.diff ?? difficulty
    try {
      let data: ArtifactBag[Kind]
      if (kind === 'lecture') data = await generateLecture(selectedId, diff)
      else if (kind === 'video') data = await generateVideo(selectedId, diff)
      else if (kind === 'diagram') data = await generateDiagram(selectedId)
      else if (kind === 'mindmap') data = await generateMindmap(selectedId)
      else if (kind === 'quiz') data = await generateQuiz(selectedId, 5)
      else data = await generateFlashcards(selectedId, 8)
      setBags((prev) => ({ ...prev, [selectedId]: { ...prev[selectedId], [kind]: data } }))
      setActiveKind(kind)
    } catch (e) {
      console.error('[doclearn] 生成失败', e)
      setGenErr(`「${KIND_META.find((k) => k.id === kind)?.label}」生成失败，请稍后重试。`)
    } finally {
      setGenKind(null)
    }
  }

  /* 讲义难度切换 → 按新难度重生成讲义 */
  const changeLectureLevel = (lv: string) => {
    if (lv === (bag.lecture?.difficulty ?? difficulty) || genKind) return
    setDifficulty(lv)
    void runGenerate('lecture', { diff: lv, regen: true })
  }

  const exportLectureMd = () => {
    if (!bag.lecture) return
    exportLectureMarkdown(bag.lecture.markdown, `讲义-${selectedDoc?.title ?? '文档'}-${bag.lecture.difficulty}`)
  }
  const exportLecturePdf = () => {
    const body = lectureRef.current?.querySelector('.markdown-body') as HTMLElement | null
    if (!body) return
    const meta = `${selectedDoc?.title ?? '文档'} · 难度：${bag.lecture?.difficulty ?? difficulty} · 导出于 ${new Date().toLocaleString('zh-CN')}`
    const ok = exportLectureToPdf(body, `讲义-${selectedDoc?.title ?? '文档'}`, meta)
    if (!ok) window.alert('浏览器拦截了打印窗口，请允许本站弹出窗口后重试导出 PDF。')
  }

  /* ---------------- 渲染：产出区 ---------------- */

  const renderOutput = () => {
    if (!activeKind) return null
    switch (activeKind) {
      case 'lecture':
        return (
          <>
            <div className="level-switch">
              <span className="level-switch__label">难度自适应：</span>
              <div className="level-switch__seg">
                {LEVELS.map((lv) => (
                  <button
                    key={lv}
                    className={`level-switch__btn ${(bag.lecture?.difficulty ?? difficulty) === lv ? 'level-switch__btn--active' : ''}`}
                    onClick={() => changeLectureLevel(lv)}
                    disabled={genKind === 'lecture'}
                  >
                    {lv}
                  </button>
                ))}
              </div>
              <span className="level-switch__hint">切换难度，AI 按该文档实时重生成讲义</span>
            </div>
            {bag.lecture && (
              <div className="doclearn-halluc" title="讲义内容与文档原文的偏离度，越低越可信">
                文档溯源 · 幻觉率 {Math.round(bag.lecture.hallucinationRate * 100)}%
              </div>
            )}
            <SourceTrace sources={bag.lecture?.sources} />
            <div className="lecture-export">
              <span className="lecture-export__label">导出讲义：</span>
              <button type="button" className="lecture-export__btn" onClick={exportLectureMd} disabled={!bag.lecture}>
                <span aria-hidden="true">⬇</span> Markdown
              </button>
              <button
                type="button"
                className="lecture-export__btn lecture-export__btn--pdf"
                onClick={exportLecturePdf}
                disabled={!bag.lecture}
              >
                <span aria-hidden="true">🖨</span> PDF
              </button>
            </div>
            <div className="lecture-body" ref={lectureRef}>
              {bag.lecture ? (
                <MarkdownRenderer content={bag.lecture.markdown} />
              ) : (
                <div className="resource-loading">正在基于文档生成讲义…</div>
              )}
            </div>
          </>
        )
      case 'video':
        return (
          <Suspense fallback={<Loading />}>
            <div className="resource-modal-hint">基于文档生成的讲解视频（Remotion 实时渲染 + 同步旁白）：</div>
            {bag.video && (
              <VideoLecture title={bag.video.title} scenes={bag.video.scenes} difficulty={bag.video.difficulty} />
            )}
            <SourceTrace sources={bag.video?.sources} />
          </Suspense>
        )
      case 'diagram':
        return (
          <Suspense fallback={<Loading />}>
            <div className="resource-modal-hint">文档知识脉络图解（可缩放 / 拖拽 / 导出 SVG · PNG）：</div>
            {bag.diagram && (
              <MermaidDiagram chart={bag.diagram.mermaid} downloadName={`图解-${selectedDoc?.title ?? '文档'}`} />
            )}
            <SourceTrace sources={bag.diagram?.sources} />
          </Suspense>
        )
      case 'mindmap':
        return (
          <Suspense fallback={<Loading />}>
            <div className="resource-modal-hint">文档结构化思维导图（可缩放 / 拖拽 / 导出 SVG · PNG）：</div>
            {bag.mindmap && (
              <MindMap markdown={bag.mindmap.markdown} downloadName={`思维导图-${selectedDoc?.title ?? '文档'}`} />
            )}
          </Suspense>
        )
      case 'quiz':
        return (
          <>
            <div className="resource-modal-hint">基于文档生成的练习题，作答后即时判分与解析：</div>
            {bag.quiz && bag.quiz.questions.length > 0 ? (
              <QuizRenderer questions={bag.quiz.questions} />
            ) : (
              <div className="resource-loading">正在基于文档生成练习题…</div>
            )}
            <SourceTrace sources={bag.quiz?.sources} />
          </>
        )
      case 'flashcards':
        return (
          <>
            <div className="resource-modal-hint">正反翻卡速记，点击卡片翻面，← → 翻页浏览整套：</div>
            {bag.flashcards && (
              <FlashcardDeck
                cards={bag.flashcards.cards}
                title={selectedDoc?.title ?? '文档闪卡'}
                downloadName={`闪卡-${selectedDoc?.title ?? '文档'}`}
              />
            )}
            <SourceTrace sources={bag.flashcards?.sources} />
          </>
        )
    }
  }

  const readyCount = docs.filter((d) => d.status === 'indexed').length

  return (
    <div className="doclearn">
      <PageHeader
        title="文档学习"
        highlight="文档"
        subtitle="上传你的资料，AI 基于该文档生成讲义 / 视频 / 图解 / 思维导图 / 练习题 / 闪卡 · 内容严格溯源自文档"
        badges={[
          { label: '我的文档', value: docs.length },
          { label: '已就绪', value: readyCount, tone: 'safe' },
        ]}
      />

      <div className="doclearn__grid">
        {/* ============ 来源区 ============ */}
        <aside className="doclearn__sources">
          <div className="doclearn__panel-title">
            <span>来源文档</span>
            <span className="doclearn__panel-count">{docs.length}</span>
          </div>

          {/* 上传拖放区 */}
          <div
            className={`doclearn-drop ${dragOver ? 'doclearn-drop--over' : ''} ${uploading ? 'doclearn-drop--busy' : ''}`}
            onClick={() => !uploading && fileInputRef.current?.click()}
            onDragOver={(e) => {
              e.preventDefault()
              setDragOver(true)
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={onDrop}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept={DOC_FILE_ACCEPT}
              multiple
              hidden
              onChange={(e) => {
                if (e.target.files) void handleFiles(e.target.files)
                e.target.value = ''
              }}
            />
            {uploading ? (
              <>
                <span className="doclearn-drop__spinner" />
                <span className="doclearn-drop__text">上传解析中…</span>
              </>
            ) : (
              <>
                <span className="doclearn-drop__icon">⬆</span>
                <span className="doclearn-drop__text">
                  拖放文件到此，或<b>点击上传</b>
                </span>
                <span className="doclearn-drop__hint">支持 PDF · TXT · Markdown · DOCX（≤ {DOC_MAX_MB}MB）</span>
              </>
            )}
          </div>
          {uploadErr && <div className="doclearn-drop__err">{uploadErr}</div>}

          {/* 文档列表 */}
          <div className="doclearn-doclist">
            {loadingDocs ? (
              <div className="resource-loading">加载文档…</div>
            ) : docs.length === 0 ? (
              <div className="doclearn-doclist__empty">还没有文档，先上传一份开始学习吧。</div>
            ) : (
              docs.map((d) => (
                <button
                  key={d.id}
                  className={`doclearn-docitem ${selectedId === d.id ? 'doclearn-docitem--active' : ''}`}
                  onClick={() => setSelectedId(d.id)}
                >
                  <span className={`doclearn-docitem__type doclearn-docitem__type--${d.fileType}`}>{d.fileType.toUpperCase()}</span>
                  <span className="doclearn-docitem__body">
                    <span className="doclearn-docitem__title">{d.title}</span>
                    <span className="doclearn-docitem__meta">
                      <span className={`doclearn-docitem__status doclearn-docitem__status--${d.status}`}>
                        {STATUS_LABEL[d.status]}
                      </span>
                      · {formatBytes(d.size)} · {d.chunks} 块
                    </span>
                  </span>
                  <span
                    className="doclearn-docitem__del"
                    onClick={(e) => handleDelete(d.id, e)}
                    role="button"
                    tabIndex={-1}
                    aria-label="删除文档"
                    title="删除"
                  >
                    ×
                  </span>
                </button>
              ))
            )}
          </div>
        </aside>

        {/* ============ 生成 + 产出区 ============ */}
        <section className="doclearn__studio">
          {!selectedDoc ? (
            <div className="doclearn-empty">
              <div className="doclearn-empty__art">📚</div>
              <h3 className="doclearn-empty__title">从上传一份文档开始</h3>
              <p className="doclearn-empty__desc">
                上传 PDF / 文本 / Markdown / Word 资料后，在这里选中它，
                <br />
                即可让 AI 基于文档生成讲义、视频、图解、思维导图、练习题与闪卡。
              </p>
              <button className="doclearn-empty__cta" onClick={() => fileInputRef.current?.click()}>
                ⬆ 上传第一份文档
              </button>
            </div>
          ) : (
            <>
              {/* 生成操作区 */}
              <div className="doclearn-actions">
                <div className="doclearn-actions__head">
                  <span className="doclearn-actions__doc">当前文档：<b>{selectedDoc.title}</b></span>
                  {selectedDoc.status !== 'indexed' && (
                    <span className="doclearn-actions__wait">
                      <span className="doclearn-drop__spinner" /> {STATUS_LABEL[selectedDoc.status]}
                    </span>
                  )}
                </div>
                <div className="doclearn-actions__grid">
                  {KIND_META.map((k) => {
                    const done = !!bag[k.id]
                    const busy = genKind === k.id
                    const active = activeKind === k.id
                    return (
                      <button
                        key={k.id}
                        className={`doclearn-act ${active ? 'doclearn-act--active' : ''} ${done ? 'doclearn-act--done' : ''}`}
                        onClick={() => runGenerate(k.id)}
                        disabled={!!genKind || selectedDoc.status !== 'indexed'}
                        title={done ? '查看已生成内容' : `基于文档生成${k.label}`}
                      >
                        <span className="doclearn-act__icon">{busy ? <span className="doclearn-drop__spinner" /> : k.icon}</span>
                        <span className="doclearn-act__label">{k.label}</span>
                        <span className="doclearn-act__desc">{busy ? '生成中…' : done ? '已生成 · 点击查看' : k.desc}</span>
                        {done && (
                          <span
                            className="doclearn-act__regen"
                            role="button"
                            tabIndex={-1}
                            title="重新生成"
                            onClick={(e) => {
                              e.stopPropagation()
                              if (!genKind) void runGenerate(k.id, { regen: true })
                            }}
                          >
                            ↻
                          </span>
                        )}
                      </button>
                    )
                  })}
                </div>
                {genErr && <div className="doclearn-drop__err">{genErr}</div>}
              </div>

              {/* 产出区 */}
              <div className="doclearn-output">
                <AnimatePresence mode="wait">
                  {activeKind ? (
                    <motion.div
                      key={activeKind}
                      initial={{ opacity: 0, y: 12 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -8 }}
                      transition={{ duration: 0.25 }}
                    >
                      {renderOutput()}
                    </motion.div>
                  ) : (
                    <motion.div
                      key="out-empty"
                      className="doclearn-output__empty"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                    >
                      <span className="doclearn-output__empty-icon">✨</span>
                      <p>
                        选择上方任一形态，AI 会<b>基于「{selectedDoc.title}」</b>为你生成对应学习资料。
                      </p>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  )
}
