import { useEffect, useRef, useState, lazy, Suspense } from 'react'
import { motion } from 'framer-motion'
import MarkdownRenderer from './MarkdownRenderer'
import { USE_REAL_API } from '../services/api'
import { getLecture, getDiagram } from '../services/resource'
import { KP_RESOURCES } from '../data/kpResources'
import { exportLectureMarkdown, exportLectureToPdf } from '../utils/lectureExport'
import { KIND_LABEL, type ResourceHistoryItem } from '../services/resourceHistory'
import '../pages/LearningResource.css'

/* 重型多模态组件按需懒加载（与学习资源页一致），保持资源库列表轻量 */
const MindMap = lazy(() => import('./MindMap'))
const MermaidDiagram = lazy(() => import('./MermaidDiagram'))
const VideoLecture = lazy(() => import('./VideoLecture'))
const CodeSandbox = lazy(() => import('./CodeSandbox'))

const Loading = () => <div className="resource-loading">资源加载中…</div>

/** 从讲义 markdown 提取标题大纲（跳过代码块内 # 注释）→ 供思维导图结构化（与学习资源页同口径）。 */
function lectureOutline(md: string): string {
  let inFence = false
  const lines: string[] = []
  for (const line of md.split('\n')) {
    if (/^\s*```/.test(line)) {
      inFence = !inFence
      continue
    }
    if (!inFence && /^#{1,4}\s/.test(line)) lines.push(line)
  }
  return lines.join('\n')
}

/* 头部主题色沿用学习资源页的插画浅底，保持视觉一致 */
const KIND_THEME: Record<ResourceHistoryItem['kind'], string> = {
  lecture: '#e7f4ee',
  video: '#e8f0fb',
  mindmap: '#efeafb',
  diagram: '#fbf2e2',
  code: '#eceef3',
}

/**
 * 我的资源库·资源预览弹层。
 *
 * 复用学习资源页的多模态组件与导出能力，在资源库内**直接查看 + 下载**：
 * - 讲义：MarkdownRenderer + 导出 Markdown / PDF（复用 lectureExport）；
 * - 视频：VideoLecture（服务端渲染 mp4 就绪即可下载，内置降级实时播放）；
 * - 图解/导图：MermaidDiagram / MindMap（内置下载 SVG / PNG）；
 * - 代码：CodeSandbox（内置下载代码文件）。
 * 数据源与学习资源页一致：联调取后端 /resource/*，mock 取本地 KP_RESOURCES。
 */
export default function ResourceLibraryPreview({
  record,
  onClose,
  onOpenInLearning,
}: {
  record: ResourceHistoryItem
  onClose: () => void
  onOpenInLearning: (record: ResourceHistoryItem) => void
}) {
  const { kind, kpId, kpName } = record
  // 讲义/视频用记录里的难度；图解/导图/代码无难度 → 取讲义结构化默认档
  const difficulty = record.difficulty || '初级'
  const lectureRef = useRef<HTMLDivElement>(null)

  const [lecture, setLecture] = useState<string>('')
  const [mindmap, setMindmap] = useState<string>('')
  const [diagram, setDiagram] = useState<string>('')
  const [loading, setLoading] = useState<boolean>(kind === 'lecture' || kind === 'mindmap' || kind === 'diagram')

  /* Esc 关闭 + 锁背景滚动（与学习资源页详情一致） */
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', onKey)
      document.body.style.overflow = prevOverflow
    }
  }, [onClose])

  /* 按形态取内容（联调后端 / mock 本地），与学习资源页数据源一致 */
  useEffect(() => {
    let alive = true
    const mock = KP_RESOURCES[kpId]
    async function load() {
      try {
        if (kind === 'lecture') {
          const md = USE_REAL_API
            ? (await getLecture(kpId, difficulty)).markdown
            : mock?.lectureByLevel?.[difficulty as '入门' | '初级' | '高级'] ?? ''
          if (alive) setLecture(md)
        } else if (kind === 'mindmap') {
          const md = USE_REAL_API
            ? lectureOutline((await getLecture(kpId, difficulty)).markdown)
            : mock?.mindmap ?? ''
          if (alive) setMindmap(md)
        } else if (kind === 'diagram') {
          const chart = USE_REAL_API ? (await getDiagram(kpId)).mermaid : mock?.diagram ?? ''
          if (alive) setDiagram(chart)
        }
      } catch (e) {
        console.error('[resource-library] 预览内容加载失败', e)
      } finally {
        if (alive) setLoading(false)
      }
    }
    void load()
    return () => {
      alive = false
    }
    // 记录不变；difficulty 由记录派生
  }, [kind, kpId, difficulty])

  /* 讲义导出（导出当前已渲染内容，不重新生成） */
  const exportBaseName = record.difficulty
    ? `讲义-${kpName}-${record.difficulty}`
    : `讲义-${kpName}`
  const handleExportMarkdown = () => {
    if (lecture) exportLectureMarkdown(lecture, exportBaseName)
  }
  const handleExportPdf = () => {
    const body = lectureRef.current?.querySelector('.markdown-body') as HTMLElement | null
    if (!body) return
    const meta = `${kpName}${record.difficulty ? ` · 难度：${record.difficulty}` : ''} · 导出于 ${new Date().toLocaleString('zh-CN')}`
    const ok = exportLectureToPdf(body, exportBaseName, meta)
    if (!ok) window.alert('浏览器拦截了打印窗口，请允许本站弹出窗口后重试导出 PDF。')
  }

  const renderBody = () => {
    if (kind === 'lecture') {
      return (
        <>
          <div className="lecture-export">
            <span className="lecture-export__label">导出讲义：</span>
            <button
              type="button"
              className="lecture-export__btn"
              onClick={handleExportMarkdown}
              disabled={!lecture}
              title="下载讲义 Markdown 原文（.md）"
            >
              <span aria-hidden="true">⬇</span> Markdown
            </button>
            <button
              type="button"
              className="lecture-export__btn lecture-export__btn--pdf"
              onClick={handleExportPdf}
              disabled={!lecture}
              title="导出为 PDF（经浏览器打印 → 另存为 PDF）"
            >
              <span aria-hidden="true">🖨</span> PDF
            </button>
          </div>
          <div className="lecture-body" ref={lectureRef}>
            {lecture ? (
              <MarkdownRenderer content={lecture} />
            ) : (
              <div className="resource-loading">「{kpName}」的讲义内容加载中…</div>
            )}
          </div>
        </>
      )
    }
    if (kind === 'video') {
      return (
        <Suspense fallback={<Loading />}>
          <div className="resource-modal-hint">AI 生成的讲解视频（Remotion 渲染）+ 同步旁白，可播放/下载 mp4：</div>
          <VideoLecture kpId={kpId} difficulty={difficulty} />
        </Suspense>
      )
    }
    if (kind === 'mindmap') {
      return (
        <Suspense fallback={<Loading />}>
          <div className="resource-modal-hint">讲义结构化的知识脉络图，可缩放/拖拽，支持下载 SVG / PNG：</div>
          {loading ? (
            <div className="resource-loading">「{kpName}」的思维导图加载中…</div>
          ) : mindmap ? (
            <MindMap markdown={mindmap} downloadName={`思维导图-${kpName}`} />
          ) : (
            <div className="resource-loading">该思维导图暂无可用内容。</div>
          )}
        </Suspense>
      )
    }
    if (kind === 'diagram') {
      return (
        <Suspense fallback={<Loading />}>
          <div className="resource-modal-hint">「{kpName}」知识脉络图（可缩放/拖拽），支持下载 SVG / PNG：</div>
          {loading ? (
            <div className="resource-loading">「{kpName}」的知识图解加载中…</div>
          ) : diagram ? (
            <MermaidDiagram chart={diagram} downloadName={`图解-${kpName}`} />
          ) : (
            <div className="resource-loading">该图解暂无可用内容。</div>
          )}
        </Suspense>
      )
    }
    // code
    return (
      <Suspense fallback={<Loading />}>
        <div className="resource-modal-hint">浏览器内可运行的代码示例，可下载代码文件：</div>
        <CodeSandbox baseName={`代码-${kpName}`} />
      </Suspense>
    )
  }

  return (
    <motion.div
      className="rescard-overlay"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={record.title}
    >
      <motion.div className="rescard-detail" onClick={(e) => e.stopPropagation()}>
        <motion.div
          className="rescard-detail__head rescard-detail__head--plain"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          style={{ background: KIND_THEME[kind] }}
        />
        <h3 className="rescard-detail__title">
          {KIND_LABEL[kind]} · {kpName}
          {record.difficulty ? ` · ${record.difficulty}` : ''}
        </h3>
        <button type="button" className="rescard-detail__close" onClick={onClose} autoFocus aria-label="关闭">
          ×
        </button>

        <motion.div
          className="rescard-detail__body"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1, duration: 0.24 }}
        >
          <div className="reslib-preview__toolbar">
            <button type="button" className="reslib-preview__jump" onClick={() => onOpenInLearning(record)}>
              在学习页打开 →
            </button>
          </div>
          {renderBody()}
        </motion.div>
      </motion.div>
    </motion.div>
  )
}
