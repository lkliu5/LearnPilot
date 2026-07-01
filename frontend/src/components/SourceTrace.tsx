import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

export interface SourceRef {
  title: string
  type: '教材' | '论文' | '文档' | '课程'
  confidence: number
}

/* 模拟 RAG 检索 + 审核 Agent 给出的溯源来源（体现防幻觉/可信）；
   导出供资源页状态条「RAG 引用数」在 mock 模式取真实条数（与讲义溯源实际列出的来源一致）。*/
export const defaultSources: SourceRef[] = [
  { title: '《深度学习》 Goodfellow, Bengio, Courville', type: '教材', confidence: 98 },
  { title: 'arXiv:1706.03762 — Attention Is All You Need', type: '论文', confidence: 95 },
  { title: 'CS231n: Neural Networks（Stanford）', type: '课程', confidence: 94 },
  { title: 'PyTorch 官方文档 · nn.Module', type: '文档', confidence: 92 },
  { title: '《神经网络与深度学习》 邱锡鹏', type: '教材', confidence: 90 },
]

const typeColor: Record<SourceRef['type'], string> = {
  教材: 'var(--primary-600)',
  论文: 'var(--purple-600)',
  文档: 'var(--success-600)',
  课程: 'var(--warning-600)',
}

export default function SourceTrace({ sources = defaultSources }: { sources?: SourceRef[] }) {
  const [open, setOpen] = useState(false)

  return (
    <div className="src-trace">
      <button className="src-trace__toggle" onClick={() => setOpen((v) => !v)}>
        <span className="src-trace__shield">🛡️</span>
        <span className="src-trace__title">RAG 溯源 · 多智能体已交叉校验</span>
        <span className="src-trace__count">{sources.length} 篇来源</span>
        <span className={`src-trace__chevron ${open ? 'src-trace__chevron--open' : ''}`}>▾</span>
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.ul
            className="src-trace__list"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25 }}
          >
            {sources.map((s) => (
              <li key={s.title} className="src-trace__item">
                <span className="src-trace__type" style={{ color: typeColor[s.type] }}>
                  {s.type}
                </span>
                <span className="src-trace__name">{s.title}</span>
                <span className="src-trace__conf">
                  <span className="src-trace__conf-bar">
                    <span className="src-trace__conf-fill" style={{ width: `${s.confidence}%` }} />
                  </span>
                  {s.confidence}%
                </span>
              </li>
            ))}
          </motion.ul>
        )}
      </AnimatePresence>
    </div>
  )
}
