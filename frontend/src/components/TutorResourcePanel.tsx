import { lazy, Suspense, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import MarkdownRenderer from './MarkdownRenderer'
import {
  generateResources,
  type RemedialSuggestResult,
  type RemedialResource,
  type RemedialType,
} from '../services/tutorResource'
import './TutorResourcePanel.css'

const MermaidDiagram = lazy(() => import('./MermaidDiagram'))

/**
 * 智能辅导·资源生成清单 + 按需生成（接口文档 8.8，C-fix 批3-bonus）。
 * 展示识别出的问题点 + 针对性资源清单（勾选）→ 生成所选 → 内联查看生成结果。
 */

const TYPE_ICON: Record<RemedialType, string> = {
  diagram: '🗺️',
  example: '📝',
  video: '🎬',
  lecture: '📖',
}

interface Props {
  suggestion: RemedialSuggestResult
  kpName?: string
}

export default function TutorResourcePanel({ suggestion, kpName }: Props) {
  const [picked, setPicked] = useState<Set<RemedialType>>(
    () => new Set(suggestion.suggestions.map((s) => s.type)) // 默认全选
  )
  const [results, setResults] = useState<RemedialResource[]>([])
  const [generating, setGenerating] = useState(false)

  const toggle = (t: RemedialType) =>
    setPicked((prev) => {
      const next = new Set(prev)
      next.has(t) ? next.delete(t) : next.add(t)
      return next
    })

  const generate = async () => {
    if (!picked.size || generating) return
    setGenerating(true)
    try {
      const res = await generateResources(
        suggestion.kpId,
        suggestion.problemPoint,
        [...picked],
        kpName ?? suggestion.kpName
      )
      setResults(res.results)
    } catch (e) {
      console.error('[tutor-resource] 生成失败', e)
    } finally {
      setGenerating(false)
    }
  }

  return (
    <motion.div
      className="trp"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
    >
      <div className="trp__head">
        <span className="trp__badge">✦ 智能辅导</span>
        <span className="trp__point">
          识别到你的问题点：<strong>{suggestion.problemPoint}</strong>
        </span>
      </div>
      <p className="trp__hint">针对这个盲区可生成以下资源，勾选后按需生成：</p>

      <div className="trp__list">
        {suggestion.suggestions.map((s) => (
          <label key={s.id} className={`trp__item ${picked.has(s.type) ? 'is-picked' : ''}`}>
            <input type="checkbox" checked={picked.has(s.type)} onChange={() => toggle(s.type)} />
            <span className="trp__item-icon">{TYPE_ICON[s.type]}</span>
            <span className="trp__item-body">
              <span className="trp__item-title">{s.title}</span>
              <span className="trp__item-expect">{s.expect}</span>
            </span>
          </label>
        ))}
      </div>

      <button className="trp__gen" disabled={!picked.size || generating} onClick={generate}>
        {generating ? '正在按需生成…' : `生成所选（${picked.size}）`}
      </button>

      <AnimatePresence>
        {results.length > 0 && (
          <motion.div
            className="trp__results"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            {results.map((r, i) => (
              <ResourceResult key={`${r.type}-${i}`} resource={r} />
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

function ResourceResult({ resource: r }: { resource: RemedialResource }) {
  const [showSolution, setShowSolution] = useState(false)
  return (
    <div className="trp__result">
      <div className="trp__result-head">
        <span className="trp__result-icon">{TYPE_ICON[r.type]}</span>
        <span className="trp__result-title">{r.title}</span>
      </div>

      {r.type === 'diagram' && r.mermaid && (
        <Suspense fallback={<div className="trp__loading">图解渲染中…</div>}>
          <MermaidDiagram chart={r.mermaid} />
        </Suspense>
      )}

      {r.type === 'lecture' && r.markdown && (
        <div className="trp__md">
          <MarkdownRenderer content={r.markdown} />
        </div>
      )}

      {r.type === 'example' && (
        <div className="trp__example">
          <p className="trp__example-q">{r.statement}</p>
          {!showSolution ? (
            <button className="trp__example-toggle" onClick={() => setShowSolution(true)}>
              查看解析 →
            </button>
          ) : (
            <pre className="trp__example-a">{r.solution}</pre>
          )}
        </div>
      )}

      {r.type === 'video' && r.scenes && (
        <ol className="trp__scenes">
          {r.scenes.map((sc, i) => (
            <li key={i} className="trp__scene">
              <span className="trp__scene-title">{sc.title}</span>
              <span className="trp__scene-narration">{sc.narration}</span>
              {sc.points?.length > 0 && (
                <ul className="trp__scene-points">
                  {sc.points.map((p, j) => (
                    <li key={j}>{p}</li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}
