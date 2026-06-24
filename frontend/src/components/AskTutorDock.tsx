import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { suggestResources, type RemedialSuggestResult } from '../services/tutorResource'
import TutorResourcePanel from './TutorResourcePanel'
import './AskTutorDock.css'

/**
 * AI 答疑 · 常驻辅导入口（核心功能升格）。
 *
 * 解决目标用户「自学卡住没人答疑」的核心痛点：在学习界面右侧常驻一个醒目入口，
 * 学到卡住随手就能问。点击 → 描述/识别问题点 → 针对性资源清单 → 勾选按需生成。
 *
 * 完全复用既有链路与接口，不改后端：
 *  - suggestResources() = POST /resource/tutor/suggest（识别问题点 + 资源清单）
 *  - TutorResourcePanel 内部 generateResources() = POST /resource/tutor/generate（勾选逐项生成）
 *
 * 可选增强：可「针对当前讲义直接答疑」——无需输入即就当前知识点发起辅导，让针对性更具体。
 */
interface Props {
  kpId: string
  kpName: string
}

/* 常见卡点的引导问句（点一下填入输入框，降低「不知道怎么问」的门槛）*/
const QUICK_QUESTIONS = [
  '这个知识点的核心思路没看懂',
  '公式/推导这一段卡住了',
  '想要一个直观的例子',
]

export default function AskTutorDock({ kpId, kpName }: Props) {
  const [open, setOpen] = useState(false)
  const [question, setQuestion] = useState('')
  const [suggesting, setSuggesting] = useState(false)
  const [suggestion, setSuggestion] = useState<RemedialSuggestResult | null>(null)

  const ask = async (q: string) => {
    if (suggesting) return
    setSuggesting(true)
    setSuggestion(null)
    try {
      setSuggestion(await suggestResources(kpId, q, kpName))
    } catch (e) {
      console.error('[ask-tutor] 资源建议失败', e)
    } finally {
      setSuggesting(false)
    }
  }

  /* 主提问：用输入内容识别问题点；留空则回退为「就当前讲义答疑」 */
  const submit = () =>
    void ask(question.trim() || `我在学习「${kpName}」时卡住了，需要更直观的针对性资源`)

  /* 可选增强：针对当前讲义内容直接发起辅导（无需输入） */
  const askCurrent = () =>
    void ask(`针对「${kpName}」当前讲义内容，我还没完全理解，帮我做更针对性的拆解`)

  return (
    <>
      {/* 常驻侧边入口：主按钮级权重，但置于学习区右缘工具位，不与「去通关」主 CTA 抢焦点 */}
      <button
        type="button"
        className={`ask-tutor-dock ${open ? 'ask-tutor-dock--hidden' : ''}`}
        onClick={() => setOpen(true)}
        aria-label="打开 AI 答疑"
      >
        <span className="ask-tutor-dock__icon" aria-hidden>💡</span>
        <span className="ask-tutor-dock__label">AI&nbsp;答疑</span>
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            className="ask-tutor-scrim"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setOpen(false)}
            role="dialog"
            aria-modal="true"
            aria-label="AI 答疑"
          >
            <motion.aside
              className="ask-tutor-drawer"
              initial={{ x: 40, opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              exit={{ x: 40, opacity: 0 }}
              transition={{ type: 'spring', stiffness: 260, damping: 30 }}
              onClick={(e) => e.stopPropagation()}
            >
              <header className="ask-tutor-drawer__head">
                <div className="ask-tutor-drawer__title">
                  <span className="ask-tutor-drawer__icon" aria-hidden>💡</span>
                  <div>
                    <h3>AI 答疑 · 针对性辅导</h3>
                    <p className="ask-tutor-drawer__sub">
                      针对<strong>「{kpName}」</strong>· 卡住随手就能问
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  className="ask-tutor-drawer__close"
                  onClick={() => setOpen(false)}
                  aria-label="关闭"
                >
                  ×
                </button>
              </header>

              <div className="ask-tutor-drawer__body">
                <p className="ask-tutor-drawer__lead">
                  自学卡住没人答疑？描述你哪里没懂，AI 立刻识别问题点并生成针对性资源（图解 / 例题 / 视频 / 讲义）。
                </p>

                <textarea
                  className="ask-tutor-drawer__input"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  placeholder={`例如：我不理解「${kpName}」里的某一步是怎么推出来的…`}
                  rows={3}
                  disabled={suggesting}
                />

                <div className="ask-tutor-drawer__chips">
                  {QUICK_QUESTIONS.map((q) => (
                    <button
                      key={q}
                      type="button"
                      className="ask-tutor-drawer__chip"
                      onClick={() => setQuestion(q)}
                      disabled={suggesting}
                    >
                      {q}
                    </button>
                  ))}
                </div>

                <div className="ask-tutor-drawer__actions">
                  <button
                    type="button"
                    className="ask-tutor-drawer__primary"
                    onClick={submit}
                    disabled={suggesting}
                  >
                    {suggesting ? '正在识别问题点…' : '识别问题 → 推荐针对性资源'}
                  </button>
                  <button
                    type="button"
                    className="ask-tutor-drawer__ghost"
                    onClick={askCurrent}
                    disabled={suggesting}
                    title="无需输入，直接就当前讲义内容发起辅导"
                  >
                    📖 针对当前讲义答疑
                  </button>
                </div>

                {suggestion && (
                  <div className="ask-tutor-drawer__result">
                    <TutorResourcePanel suggestion={suggestion} kpName={kpName} />
                  </div>
                )}
              </div>
            </motion.aside>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
