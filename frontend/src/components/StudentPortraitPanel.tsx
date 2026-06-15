import { AnimatePresence, motion } from 'framer-motion'
import { CANONICAL_DIMS, type PortraitDimension } from '../services/profileDialogue'

/**
 * 对话式诊断页右侧「动态学习画像」面板（接口 38，17.2 异质 ≥6 维）。
 * 独立于 Dashboard 的固定 6 知识点掌握度雷达（4.4 /profile/ability-portrait）——
 * 二者数据结构、维度集、用途均不同，并行展示，互不替换。
 *
 * 异质呈现：可量化维度（带 score）走进度条 + mono 数字；定性维度显示自然语言 value；
 * 每张卡片带 confidence + source 徽章（dialogue/inferred/manual）体现可溯源与防幻觉。
 * 维度随对话从无到有，用 Framer Motion 渐入。
 */
interface Props {
  /** 已采集维度，按 key 索引（对话 event:portrait 增量合并后的结果） */
  dims: Record<string, PortraitDimension>
  updatedAt?: string
  complete: boolean
  onFinish: () => void
}

const SOURCE_META: Record<PortraitDimension['source'], { label: string; cls: string }> = {
  dialogue: { label: '对话采集', cls: 'dialogue' },
  inferred: { label: '推断', cls: 'inferred' },
  manual: { label: '手动填写', cls: 'manual' },
}

function confLevel(c: number): 'high' | 'mid' | 'low' {
  if (c >= 0.75) return 'high'
  if (c >= 0.6) return 'mid'
  return 'low'
}

function fmtTime(iso?: string): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

export default function StudentPortraitPanel({ dims, updatedAt, complete, onFinish }: Props) {
  const acquired = CANONICAL_DIMS.filter((d) => dims[d.key])
  const filled = acquired.length
  const total = CANONICAL_DIMS.length
  const pct = Math.round((filled / total) * 100)

  return (
    <div className="sp-panel">
      <div className="sp-panel__head">
        <div>
          <div className="sp-panel__title">
            <span className="sp-panel__spark">✦</span> 动态学习画像
          </div>
          <div className="sp-panel__sub">随对话实时构建 · 异质 {total} 维 · 防幻觉可溯源</div>
        </div>
        <div className="sp-panel__count">
          <span className="sp-panel__count-num">
            {filled}
            <span className="sp-panel__count-total">/{total}</span>
          </span>
          <span className="sp-panel__count-label">维度已采集</span>
        </div>
      </div>

      {/* 整体采集进度 */}
      <div className="sp-panel__progress" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
        <motion.span
          className="sp-panel__progress-fill"
          initial={false}
          animate={{ width: `${pct}%` }}
          transition={{ type: 'spring', stiffness: 120, damping: 20 }}
        />
      </div>

      {/* 维度卡片：异质呈现，从无到有渐入 */}
      <div className="sp-cards">
        {CANONICAL_DIMS.map((c) => {
          const dim = dims[c.key]
          return (
            <AnimatePresence mode="wait" key={c.key}>
              {dim ? (
                <motion.div
                  key="filled"
                  className="sp-card"
                  initial={{ opacity: 0, y: 12, scale: 0.97 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
                >
                  <div className="sp-card__top">
                    <span className="sp-card__label">{dim.label}</span>
                    <span className={`sp-srctag sp-srctag--${SOURCE_META[dim.source].cls}`}>
                      {SOURCE_META[dim.source].label}
                    </span>
                  </div>

                  {/* 可量化维度：进度条 + mono 数字；定性维度：自然语言取值 */}
                  {typeof dim.score === 'number' ? (
                    <div className="sp-card__score">
                      <div className="sp-card__bar">
                        <motion.span
                          className="sp-card__bar-fill"
                          initial={{ width: 0 }}
                          animate={{ width: `${dim.score}%` }}
                          transition={{ duration: 0.6, ease: 'easeOut' }}
                        />
                      </div>
                      <span className="sp-card__score-num">{dim.score}</span>
                    </div>
                  ) : null}
                  <div className="sp-card__value">{dim.value}</div>

                  <div className="sp-card__foot">
                    <span className={`sp-conf sp-conf--${confLevel(dim.confidence)}`}>
                      <span className="sp-conf__dot" />
                      置信 {Math.round(dim.confidence * 100)}%
                    </span>
                    {fmtTime(dim.updatedAt) && <span className="sp-card__time">{fmtTime(dim.updatedAt)}</span>}
                  </div>
                </motion.div>
              ) : (
                <motion.div key="ghost" className="sp-card sp-card--ghost" initial={false}>
                  <div className="sp-card__top">
                    <span className="sp-card__label">{c.label}</span>
                    <span className="sp-card__pending">待采集</span>
                  </div>
                  <div className="sp-card__ghostline" />
                  <div className="sp-card__ghostline sp-card__ghostline--short" />
                </motion.div>
              )}
            </AnimatePresence>
          )
        })}
      </div>

      {/* 完成衔接（17.1 diagnosisComplete）：沿用既有完成流程，导向学习路径 */}
      <AnimatePresence>
        {complete && (
          <motion.div
            className="sp-done"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
          >
            <div className="sp-done__text">
              <strong>诊断完成</strong>
              <span>画像维度已足够，可据此生成针对性学习路径</span>
            </div>
            <button className="sp-done__btn" onClick={onFinish}>
              生成针对性学习路径 →
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      <p className="sp-panel__note">
        画像严格基于对话内容抽取，无法明确判断的维度不臆测；推断维度（
        <span className="sp-srctag sp-srctag--inferred sp-srctag--inline">推断</span>）置信度偏低，
        可在学习 / 测验中「随学随新」。{updatedAt && ` 更新于 ${fmtTime(updatedAt)}`}
      </p>
    </div>
  )
}
