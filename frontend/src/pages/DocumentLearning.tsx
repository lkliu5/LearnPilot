import { lazy, Suspense, useEffect, useMemo, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import type { PageType } from '../App'
import PageHeader from '../components/PageHeader'
import MarkdownRenderer from '../components/MarkdownRenderer'
import QuizRenderer from '../components/QuizRenderer'
import SourceTrace from '../components/SourceTrace'
import FlashcardDeck from '../components/FlashcardDeck'
import DocumentChat from '../components/DocumentChat'
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
  generateOverview,
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
  type OverviewResult,
  type QuizResult,
  type VideoResult,
} from '../services/documentLearning'
import { setTutorContext } from '../services/tutorBus'
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
  /** 勾选的文档 id（= 生成 / 问答的合并范围）；单选时行为同现在。 */
  const [checkedIds, setCheckedIds] = useState<Set<string>>(() => new Set())
  /** 聚焦文档（左栏概览目标 + 生成主文档）。 */
  const [focusedId, setFocusedId] = useState<string | null>(null)

  const [uploading, setUploading] = useState(false)
  const [uploadErr, setUploadErr] = useState<string | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  /** scopeKey（勾选集合排序拼接）→ 已生成产物集合（切换范围即切换视图）。 */
  const [bags, setBags] = useState<Record<string, ArtifactBag>>({})
  const [activeKind, setActiveKind] = useState<Kind | null>(null)
  /** 正在生成中的形态集合：支持多形态并行生成，互不锁死。 */
  const [genKinds, setGenKinds] = useState<Set<Kind>>(() => new Set())
  const [genErr, setGenErr] = useState<string | null>(null)
  const [difficulty, setDifficulty] = useState<string>('初级')

  /** docId → 文档概览（聚焦即自动生成，展示在左栏「关于来源」区）。 */
  const [overviews, setOverviews] = useState<Record<string, OverviewResult>>({})
  const [overviewBusy, setOverviewBusy] = useState<Set<string>>(() => new Set())

  const lectureRef = useRef<HTMLDivElement>(null)

  /* 挂载：拉取我的文档列表，默认聚焦 + 勾选第一篇。 */
  useEffect(() => {
    listDocuments()
      .then((items) => {
        setDocs(items)
        if (items.length) {
          setFocusedId((cur) => cur ?? items[0].id)
          setCheckedIds((cur) => (cur.size ? cur : new Set([items[0].id])))
        }
      })
      .catch((e) => console.error('[doclearn] 加载文档列表失败', e))
      .finally(() => setLoadingDocs(false))
  }, [])

  /* ---------------- 派生：问答 / 生成范围 ---------------- */
  const checkedList = useMemo(() => docs.filter((d) => checkedIds.has(d.id)), [docs, checkedIds])
  const readyChecked = useMemo(() => checkedList.filter((d) => d.status === 'indexed'), [checkedList])
  const scopeIds = useMemo(() => readyChecked.map((d) => d.id), [readyChecked])
  const scopeKey = useMemo(() => [...scopeIds].sort().join(','), [scopeIds])
  const primaryId = useMemo(
    () => (focusedId && scopeIds.includes(focusedId) ? focusedId : scopeIds[0] ?? null),
    [focusedId, scopeIds]
  )
  const scopeTitle = useMemo(() => {
    if (readyChecked.length > 1) return `${readyChecked[0].title} 等 ${readyChecked.length} 篇文档`
    return readyChecked[0]?.title ?? '文档'
  }, [readyChecked])

  const focusedDoc = docs.find((d) => d.id === focusedId) ?? null
  const bag = scopeKey ? bags[scopeKey] ?? {} : {}

  /* 声明当前辅导上下文（聚焦文档）→ 供 App 顶层全局 dock / 选中即问该文档发起辅导。 */
  useEffect(() => {
    setTutorContext({
      kpId: focusedDoc ? `doc:${focusedDoc.id}` : 'doc-learning',
      kpName: focusedDoc?.title ?? '当前文档',
    })
  }, [focusedDoc])

  /* 切换生成范围：把视图切到该范围已生成的第一个产物（没有则回到操作引导）。 */
  useEffect(() => {
    const b = bags[scopeKey]
    const first = b ? (KIND_META.map((k) => k.id).find((k) => b[k]) ?? null) : null
    setActiveKind(first)
    setGenErr(null)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scopeKey])

  /* 聚焦文档就绪即自动生成「文档概览」（NotebookLM 式速读）；已生成 / 生成中不重复拉取。 */
  useEffect(() => {
    if (!focusedId) return
    const doc = docs.find((d) => d.id === focusedId)
    if (!doc || doc.status !== 'indexed') return
    if (overviews[focusedId] || overviewBusy.has(focusedId)) return
    setOverviewBusy((prev) => new Set(prev).add(focusedId))
    generateOverview(focusedId)
      .then((o) => setOverviews((prev) => ({ ...prev, [focusedId]: o })))
      .catch((e) => console.error('[doclearn] 文档概览生成失败', e))
      .finally(() =>
        setOverviewBusy((prev) => {
          const next = new Set(prev)
          next.delete(focusedId)
          return next
        })
      )
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusedId, docs])

  /* ---------------- 选择 ---------------- */

  /** 点击文档主体：聚焦 + 单选（范围收敛为该篇，行为与原单文档一致）。 */
  const selectSingle = (id: string) => {
    setFocusedId(id)
    setCheckedIds(new Set([id]))
  }
  /** 勾选/取消勾选：加入 / 移出合并范围（多选统一生成 / 问答）。 */
  const toggleCheck = (id: string) => {
    setCheckedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
    setFocusedId((cur) => cur ?? id)
  }

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
        selectSingle(document.id)
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
    setCheckedIds((prev) => {
      const next = new Set(prev)
      next.delete(docId)
      return next
    })
    if (focusedId === docId) setFocusedId((cur) => (cur === docId ? null : cur))
  }

  /* ---------------- 生成（基于勾选范围，主文档 primaryId + 合并 scopeIds） ---------------- */

  const runGenerate = async (kind: Kind, opts?: { diff?: string; regen?: boolean }) => {
    if (!primaryId || genKinds.has(kind)) return
    if (!scopeIds.length) {
      setGenErr('所选文档正在解析入库，请稍候再生成。')
      return
    }
    // 已生成且非强制重生成 → 直接切视图
    if (!opts?.regen && bags[scopeKey]?.[kind]) {
      setActiveKind(kind)
      return
    }
    setGenErr(null)
    setGenKinds((prev) => new Set(prev).add(kind))
    const diff = opts?.diff ?? difficulty
    const ids = scopeIds
    try {
      let data: ArtifactBag[Kind]
      if (kind === 'lecture') data = await generateLecture(primaryId, diff, ids)
      else if (kind === 'video') data = await generateVideo(primaryId, diff, ids)
      else if (kind === 'diagram') data = await generateDiagram(primaryId, ids)
      else if (kind === 'mindmap') data = await generateMindmap(primaryId, ids)
      else if (kind === 'quiz') data = await generateQuiz(primaryId, 5, ids)
      else data = await generateFlashcards(primaryId, 8, ids)
      setBags((prev) => ({ ...prev, [scopeKey]: { ...prev[scopeKey], [kind]: data } }))
      setActiveKind(kind)
    } catch (e) {
      console.error('[doclearn] 生成失败', e)
      setGenErr(`「${KIND_META.find((k) => k.id === kind)?.label}」生成失败，请稍后重试。`)
    } finally {
      setGenKinds((prev) => {
        const next = new Set(prev)
        next.delete(kind)
        return next
      })
    }
  }

  /* 讲义难度切换 → 按新难度重生成讲义 */
  const changeLectureLevel = (lv: string) => {
    if (lv === (bag.lecture?.difficulty ?? difficulty) || genKinds.has('lecture')) return
    setDifficulty(lv)
    void runGenerate('lecture', { diff: lv, regen: true })
  }

  const exportLectureMd = () => {
    if (!bag.lecture) return
    exportLectureMarkdown(bag.lecture.markdown, `讲义-${scopeTitle}-${bag.lecture.difficulty}`)
  }
  const exportLecturePdf = () => {
    const body = lectureRef.current?.querySelector('.markdown-body') as HTMLElement | null
    if (!body) return
    const meta = `${scopeTitle} · 难度：${bag.lecture?.difficulty ?? difficulty} · 导出于 ${new Date().toLocaleString('zh-CN')}`
    const ok = exportLectureToPdf(body, `讲义-${scopeTitle}`, meta)
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
                    disabled={genKinds.has('lecture')}
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
              <MermaidDiagram chart={bag.diagram.mermaid} downloadName={`图解-${scopeTitle}`} />
            )}
            <SourceTrace sources={bag.diagram?.sources} />
          </Suspense>
        )
      case 'mindmap':
        return (
          <Suspense fallback={<Loading />}>
            <div className="resource-modal-hint">文档结构化思维导图（可缩放 / 拖拽 / 导出 SVG · PNG）：</div>
            {bag.mindmap && (
              <MindMap markdown={bag.mindmap.markdown} downloadName={`思维导图-${scopeTitle}`} />
            )}
          </Suspense>
        )
      case 'quiz':
        return (
          <>
            <div className="resource-modal-hint">基于文档生成的练习题，作答后即时判分与解析（通过线 70 分）：</div>
            {bag.quiz && bag.quiz.questions.length > 0 ? (
              <QuizRenderer
                questions={bag.quiz.questions}
                autoGrade
                passMark={70}
                onRestudy={() => void runGenerate('lecture')}
              />
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
                title={scopeTitle}
                downloadName={`闪卡-${scopeTitle}`}
              />
            )}
            <SourceTrace sources={bag.flashcards?.sources} />
          </>
        )
    }
  }

  const readyCount = docs.filter((d) => d.status === 'indexed').length

  /* 左栏「关于来源」概览块（聚焦文档的 AI 速读）。 */
  const renderOverview = () => {
    if (!focusedDoc || focusedDoc.status !== 'indexed') return null
    if (!overviews[focusedId!] && !overviewBusy.has(focusedId!)) return null
    const ov = overviews[focusedId!]
    return (
      <div className="doclearn-overview">
        <div className="doclearn-overview__head">
          <span className="doclearn-overview__icon">🧭</span>
          <span className="doclearn-overview__title">文档概览</span>
          <span className="doclearn-overview__tag">AI 速读 · 溯源自本文档</span>
          {overviewBusy.has(focusedId!) && !ov && <span className="doclearn-drop__spinner" />}
        </div>
        <div className="doclearn-overview__docname">{focusedDoc.title}</div>
        {ov ? (
          <>
            <p className="doclearn-overview__summary">{ov.summary}</p>
            {ov.about && <p className="doclearn-overview__about">{ov.about}</p>}
            {ov.structure && (
              <p className="doclearn-overview__structure">
                <b>核心结构概况：</b>
                {ov.structure}
              </p>
            )}
            {ov.keyPoints.length > 0 && (
              <div className="doclearn-overview__keys">
                <span className="doclearn-overview__keys-label">关键点</span>
                <ul>
                  {ov.keyPoints.map((k, i) => (
                    <li key={i}>{k}</li>
                  ))}
                </ul>
              </div>
            )}
          </>
        ) : (
          <p className="doclearn-overview__summary">正在通读文档、生成概览…</p>
        )}
      </div>
    )
  }

  return (
    <div className="doclearn">
      <PageHeader
        title="文档学习"
        highlight="文档"
        subtitle="上传你的资料，左栏管理来源与概览、中栏和文档即问即答、右栏一键生成六类学习资源 · 内容严格溯源自文档"
        badges={[
          { label: '我的文档', value: docs.length },
          { label: '已就绪', value: readyCount, tone: 'safe' },
          { label: '本次范围', value: readyChecked.length, tone: 'accent' },
        ]}
      />

      <div className="doclearn__grid">
        {/* ============ 左栏 · 来源与概览 ============ */}
        <aside className="doclearn__col doclearn__sources">
          <div className="doclearn__panel-title">
            <span>来源与概览</span>
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
                  拖放文件到此，或<b>点击上传</b>（可多选）
                </span>
                <span className="doclearn-drop__hint">支持 PDF · TXT · Markdown · DOCX（≤ {DOC_MAX_MB}MB）</span>
              </>
            )}
          </div>
          {uploadErr && <div className="doclearn-drop__err">{uploadErr}</div>}

          {/* 文档列表（勾选 = 合并范围；点击标题 = 聚焦单选） */}
          {docs.length > 0 && (
            <div className="doclearn-doclist__hint">
              勾选可多选，基于多篇<b>统一生成 / 问答</b>；点击标题查看该文档概览
            </div>
          )}
          <div className="doclearn-doclist">
            {loadingDocs ? (
              <div className="resource-loading">加载文档…</div>
            ) : docs.length === 0 ? (
              <div className="doclearn-doclist__empty">还没有文档，先上传一份开始学习吧。</div>
            ) : (
              docs.map((d) => {
                const checked = checkedIds.has(d.id)
                const focused = focusedId === d.id
                return (
                  <div
                    key={d.id}
                    className={`doclearn-docitem ${focused ? 'doclearn-docitem--active' : ''} ${checked ? 'doclearn-docitem--checked' : ''}`}
                  >
                    <input
                      type="checkbox"
                      className="doclearn-docitem__check"
                      checked={checked}
                      onChange={() => toggleCheck(d.id)}
                      aria-label={`勾选「${d.title}」加入生成/问答范围`}
                      title="加入本次生成 / 问答范围"
                    />
                    <button className="doclearn-docitem__main" onClick={() => selectSingle(d.id)}>
                      <span className={`doclearn-docitem__type doclearn-docitem__type--${d.fileType}`}>
                        {d.fileType.toUpperCase()}
                      </span>
                      <span className="doclearn-docitem__body">
                        <span className="doclearn-docitem__title">{d.title}</span>
                        <span className="doclearn-docitem__meta">
                          <span className={`doclearn-docitem__status doclearn-docitem__status--${d.status}`}>
                            {STATUS_LABEL[d.status]}
                          </span>
                          · {formatBytes(d.size)} · {d.chunks} 块
                        </span>
                      </span>
                    </button>
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
                  </div>
                )
              })
            )}
          </div>

          {/* 文档概览（移至左栏「关于来源」信息区） */}
          {renderOverview()}
        </aside>

        {/* ============ 中栏 · 和文档问答（流式即问即答、溯源、历史保留） ============ */}
        <section className="doclearn__col doclearn__chat">
          <DocumentChat key={scopeKey || 'empty'} docIds={scopeIds} docTitles={readyChecked.map((d) => d.title)} />
        </section>

        {/* ============ 右栏 · 生成六类 + 产出 ============ */}
        <section className="doclearn__col doclearn__studio">
          {!primaryId ? (
            <div className="doclearn-empty">
              <div className="doclearn-empty__art">📚</div>
              <h3 className="doclearn-empty__title">选中文档，一键生成资源</h3>
              <p className="doclearn-empty__desc">
                在左栏上传并勾选文档后，这里可基于所选文档
                <br />
                生成讲义、视频、图解、思维导图、练习题与闪卡，生成后进「我的资源库」可下载。
              </p>
              <button className="doclearn-empty__cta" onClick={() => fileInputRef.current?.click()}>
                ⬆ 上传文档
              </button>
            </div>
          ) : (
            <>
              {/* 生成操作区 */}
              <div className="doclearn-actions">
                <div className="doclearn-actions__head">
                  <span className="doclearn-actions__doc">
                    生成范围：<b>{scopeTitle}</b>
                    {readyChecked.length > 1 && <span className="doclearn-actions__multi">合并 {readyChecked.length} 篇</span>}
                  </span>
                </div>
                <div className="doclearn-actions__grid">
                  {KIND_META.map((k) => {
                    const done = !!bag[k.id]
                    const busy = genKinds.has(k.id)
                    const active = activeKind === k.id
                    return (
                      <button
                        key={k.id}
                        className={`doclearn-act ${active ? 'doclearn-act--active' : ''} ${done ? 'doclearn-act--done' : ''}`}
                        onClick={() => runGenerate(k.id)}
                        disabled={busy || !scopeIds.length}
                        title={done ? '查看已生成内容' : `基于所选文档生成${k.label}`}
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
                              if (!genKinds.has(k.id)) void runGenerate(k.id, { regen: true })
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
                        选择上方任一形态，AI 会<b>基于「{scopeTitle}」</b>为你生成对应学习资料。
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
