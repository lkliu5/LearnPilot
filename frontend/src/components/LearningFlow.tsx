import { useEffect, useRef, useState, lazy, Suspense } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import MarkdownRenderer from './MarkdownRenderer'
import QuizRenderer, { type QuizQuestion } from './QuizRenderer'
import WeakPointReinforce from './WeakPointReinforce'
import CornellNotes from './CornellNotes'
import FeynmanTutor from './FeynmanTutor'
import { STATUS_LABEL, type KPStatus } from '../store/mastery'
import {
  getCornellCues,
  getSteps,
  markStep,
  type CornellCues,
  type StepKey,
  type StepProgress,
  type ReviewRef,
} from '../services/learningFlow'
import type { PageType } from '../App'
import { exportLectureMarkdown, exportLectureToPdf } from '../utils/lectureExport'
import './LearningFlow.css'

const VideoLecture = lazy(() => import('./VideoLecture'))
const MermaidDiagram = lazy(() => import('./MermaidDiagram'))
const CodeSandbox = lazy(() => import('./CodeSandbox'))

/** 有序学习流的 4 个阶段 → 18.3 的 6 个步骤键。 */
const PHASES = [
  { key: 'input', label: '输入', icon: '📥', desc: '先看一遍：视频 / 讲义 / 图解', steps: ['video', 'lecture', 'diagram'] as StepKey[] },
  { key: 'note', label: '康奈尔笔记', icon: '📝', desc: '三栏笔记 · 复述 + 总结', steps: ['note'] as StepKey[] },
  { key: 'feynman', label: '费曼讲解', icon: '🎓', desc: '以讲代学，暴露缺口', steps: ['feynman'] as StepKey[] },
  { key: 'practice', label: '代码实操', icon: '💻', desc: '动手运行验证', steps: ['practice'] as StepKey[] },
] as const

/** 步骤键 → 所属阶段下标（用于「从当前未完成步接着学」）。 */
const PHASE_OF_STEP: Record<StepKey, number> = {
  video: 0,
  lecture: 0,
  diagram: 0,
  note: 1,
  feynman: 2,
  practice: 3,
}

const INPUT_TABS: { key: StepKey; emoji: string; label: string }[] = [
  { key: 'video', emoji: '🎬', label: '讲解视频' },
  { key: 'lecture', emoji: '📖', label: '定制讲义' },
  { key: 'diagram', emoji: '📊', label: '知识图解' },
]

interface LearningFlowProps {
  kpId: string
  kpName: string
  level: string
  lectureMarkdown: string
  diagramChart: string
  questions: QuizQuestion[]
  kpStatus: KPStatus
  /** 复用父级判分/掌握度逻辑（mock 本地判分 / 联调 9.1 提交后刷新掌握度）。 */
  onQuizResult: (wrong: QuizQuestion[], submitted?: boolean, answers?: Record<string, string | string[]>) => void
  /** 进入「检验」前置 pending-check（仅首次，passed 不回退）。 */
  onGoCheck: () => void
  /** 费曼缺口「回看」：切到资源中枢对应 Tab。 */
  onReview: (ref: ReviewRef) => void
  onNavigate?: (page: PageType) => void
}

const Loading = () => <div className="resource-loading">资源加载中…</div>

export default function LearningFlow({
  kpId,
  kpName,
  level,
  lectureMarkdown,
  diagramChart,
  questions,
  kpStatus,
  onQuizResult,
  onGoCheck,
  onReview,
  onNavigate,
}: LearningFlowProps) {
  const [cues, setCues] = useState<CornellCues | null>(null)
  const [progress, setProgress] = useState<StepProgress | null>(null)
  const [phaseIdx, setPhaseIdx] = useState(0)
  const [inputTab, setInputTab] = useState<StepKey>('video')
  const flowLectureRef = useRef<HTMLDivElement>(null)
  const [wrongQs, setWrongQs] = useState<QuizQuestion[]>([])
  const [bootstrapped, setBootstrapped] = useState(false)

  /* 载入 18.1 线索 + 18.3 进度；首次定位到「当前未完成步」所在阶段 */
  useEffect(() => {
    getCornellCues(kpId, level)
      .then(setCues)
      .catch((e) => console.error('[flow] 线索生成失败', e))
    getSteps(kpId)
      .then((p) => {
        setProgress(p)
        if (!bootstrapped) {
          const firstIncomplete = (['video', 'lecture', 'diagram', 'note', 'feynman', 'practice'] as StepKey[]).find(
            (k) => !p.steps[k]
          )
          setPhaseIdx(firstIncomplete ? PHASE_OF_STEP[firstIncomplete] : PHASES.length - 1)
          const inputFirst = (['video', 'lecture', 'diagram'] as StepKey[]).find((k) => !p.steps[k])
          if (inputFirst) setInputTab(inputFirst)
          setBootstrapped(true)
        }
      })
      .catch((e) => console.error('[flow] 进度读取失败', e))
    // 知识点切换时重载（页面随导航重挂载，kpId 停留期内稳定）
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kpId])

  const steps = progress?.steps ?? {}
  const completedCount = progress?.completedCount ?? 0
  /* 终点 gate 解锁条件：6 个学习步骤全部完成才呈现/解锁阶段测试——
     学习内容没走完时测试不可作答、不可完成（阶段测试是唯一的终点 gate）。 */
  const allStepsDone = (['video', 'lecture', 'diagram', 'note', 'feynman', 'practice'] as StepKey[]).every(
    (k) => steps[k]
  )

  /** 标记某步骤完成/取消并刷新进度（18.3 POST）。 */
  const toggleStep = (step: StepKey, done: boolean) => {
    markStep(kpId, step, done)
      .then(setProgress)
      .catch((e) => console.error('[flow] 步骤标记失败', e))
  }

  const phase = PHASES[phaseIdx]
  const isLastPhase = phaseIdx === PHASES.length - 1
  const goNext = () => setPhaseIdx((i) => Math.min(i + 1, PHASES.length - 1))
  const goPrev = () => setPhaseIdx((i) => Math.max(i - 1, 0))

  /* 走完最后一段（实操）→ 引导去独立的阶段测试 gate：滚动定位 + 置 pending-check */
  const gateRef = useRef<HTMLElement>(null)
  const goToGate = () => {
    // 仅在学习步骤全部完成后才前置 pending-check（未走完不进入检验态）
    if (allStepsDone) onGoCheck()
    gateRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  const handleQuiz = (
    wrong: QuizQuestion[],
    submitted?: boolean,
    answers?: Record<string, string | string[]>
  ) => {
    setWrongQs(wrong)
    onQuizResult(wrong, submitted, answers)
  }

  /* 阶段是否完成：input 看其 3 步全完成；其余看单步 */
  const phaseDone = (i: number) => PHASES[i].steps.every((s) => steps[s])

  return (
    <div className="flow">
      {/* ===== 步骤条（stepper）：当前节点高亮，已完成打勾 ===== */}
      <div className="flow__stepper">
        {PHASES.map((p, i) => {
          const done = phaseDone(i)
          const active = i === phaseIdx
          return (
            <button
              key={p.key}
              type="button"
              className={`flow__step ${active ? 'flow__step--active' : ''} ${done ? 'flow__step--done' : ''}`}
              onClick={() => setPhaseIdx(i)}
            >
              <span className="flow__step-node">{done ? '✓' : p.icon}</span>
              <span className="flow__step-meta">
                <span className="flow__step-label">{p.label}</span>
                <span className="flow__step-desc">{p.desc}</span>
              </span>
              {i < PHASES.length - 1 && <span className="flow__step-line" />}
            </button>
          )
        })}
      </div>

      <div className="flow__progress">
        <span className="flow__progress-text">
          过程进度 {completedCount}/6 步 · 当前：{phase.label}
        </span>
        <span className="flow__progress-bar">
          <span className="flow__progress-fill" style={{ width: `${(completedCount / 6) * 100}%` }} />
        </span>
      </div>

      {/* ===== 阶段内容 ===== */}
      <div className="flow__panel">
        <AnimatePresence mode="wait">
          <motion.div
            key={phase.key}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.22 }}
          >
            {phase.key === 'input' && (
              <div className="flow__input">
                <div className="flow__input-tabs">
                  {INPUT_TABS.map((t) => (
                    <button
                      key={t.key}
                      type="button"
                      className={`flow__input-tab ${inputTab === t.key ? 'flow__input-tab--active' : ''} ${steps[t.key] ? 'flow__input-tab--done' : ''}`}
                      onClick={() => setInputTab(t.key)}
                    >
                      <span>{t.emoji} {t.label}</span>
                      {steps[t.key] && <span className="flow__input-tab-check">✓</span>}
                    </button>
                  ))}
                </div>

                <div className="flow__input-body">
                  {inputTab === 'video' && (
                    <Suspense fallback={<Loading />}>
                      <div className="resource-modal-hint">AI 生成的讲解视频（Remotion 渲染）+ 同步旁白：</div>
                      <VideoLecture difficulty={level} />
                    </Suspense>
                  )}
                  {inputTab === 'lecture' && (
                    <div className="flow__lecture">
                      {lectureMarkdown ? (
                        <>
                          {/* 讲义导出：导出当前已渲染内容，不重新生成（.md 原文最稳；.pdf 经浏览器打印另存）*/}
                          <div className="lecture-export">
                            <span className="lecture-export__label">导出讲义：</span>
                            <button
                              type="button"
                              className="lecture-export__btn"
                              onClick={() => exportLectureMarkdown(lectureMarkdown, `讲义-${kpName}-${level}`)}
                              title="下载讲义 Markdown 原文（.md）"
                            >
                              <span aria-hidden="true">⬇</span> Markdown
                            </button>
                            <button
                              type="button"
                              className="lecture-export__btn lecture-export__btn--pdf"
                              onClick={() => {
                                const body = flowLectureRef.current?.querySelector('.markdown-body') as HTMLElement | null
                                if (!body) return
                                const meta = `${kpName} · 难度：${level} · 导出于 ${new Date().toLocaleString('zh-CN')}`
                                if (!exportLectureToPdf(body, `讲义-${kpName}-${level}`, meta)) {
                                  window.alert('浏览器拦截了打印窗口，请允许本站弹出窗口后重试导出 PDF。')
                                }
                              }}
                              title="导出为 PDF（经浏览器打印 → 另存为 PDF，保留公式/图解/表格/图片）"
                            >
                              <span aria-hidden="true">🖨</span> PDF
                            </button>
                          </div>
                          <div ref={flowLectureRef}>
                            <MarkdownRenderer content={lectureMarkdown} />
                          </div>
                        </>
                      ) : (
                        <div className="resource-loading">「{kpName}」的定制讲义生成中…</div>
                      )}
                    </div>
                  )}
                  {inputTab === 'diagram' && (
                    <Suspense fallback={<Loading />}>
                      <div className="resource-modal-hint">「{kpName}」知识脉络图（可缩放/拖拽）：</div>
                      {diagramChart ? (
                        <MermaidDiagram chart={diagramChart} downloadName={`图解-${kpName}`} />
                      ) : (
                        <div className="resource-loading">知识图解生成中…</div>
                      )}
                    </Suspense>
                  )}
                </div>

                <label className="flow__seen">
                  <input
                    type="checkbox"
                    checked={!!steps[inputTab]}
                    onChange={(e) => toggleStep(inputTab, e.target.checked)}
                  />
                  我看过「{INPUT_TABS.find((t) => t.key === inputTab)?.label}」了
                </label>
              </div>
            )}

            {phase.key === 'note' && (
              <CornellNotes kpId={kpId} cues={cues} onSaved={() => !steps.note && toggleStep('note', true)} />
            )}

            {phase.key === 'feynman' && (
              <FeynmanTutor
                kpId={kpId}
                onReview={onReview}
                onComplete={() => !steps.feynman && toggleStep('feynman', true)}
              />
            )}

            {phase.key === 'practice' && (
              <div className="flow__practice">
                <Suspense fallback={<Loading />}>
                  <div className="resource-modal-hint">浏览器内可运行的神经元示例，改完代码即时看结果：</div>
                  <CodeSandbox baseName={`代码-${kpName}`} />
                </Suspense>
                <label className="flow__seen">
                  <input
                    type="checkbox"
                    checked={!!steps.practice}
                    onChange={(e) => toggleStep('practice', e.target.checked)}
                  />
                  我完成了代码实操
                </label>
              </div>
            )}
          </motion.div>
        </AnimatePresence>
      </div>

      {/* ===== 阶段内导航 ===== */}
      <div className="flow__nav">
        <button type="button" className="flow__nav-btn" onClick={goPrev} disabled={phaseIdx === 0}>
          ← 上一步
        </button>
        <span className="flow__nav-hint">
          {isLastPhase
            ? allStepsDone
              ? '过程已走完，下一步去末尾的阶段测试检验掌握度'
              : '完成全部 6 个学习步骤后，末尾的阶段测试将自动解锁'
            : phase.desc}
        </span>
        {isLastPhase ? (
          <button type="button" className="flow__nav-btn flow__nav-btn--primary" onClick={goToGate}>
            去阶段测试检验 →
          </button>
        ) : (
          <button type="button" className="flow__nav-btn flow__nav-btn--primary" onClick={goNext}>
            下一步 →
          </button>
        )}
      </div>

      {/* ===== 阶段测试 · 独立 gate（与学习内容明确分区）===== */}
      <section className="gate" ref={gateRef}>
        <div className="gate__head">
          <div className="gate__head-text">
            <span className="gate__kicker">独立检验 · GATE</span>
            <h3 className="gate__title">阶段测试</h3>
            <p className="gate__sub">
              过程 6 步是「学」，这里是「检」——只有<strong>通过测试（≥60 分）</strong>才会点亮「已掌握」并推进学习路径进度。
            </p>
          </div>
          <span className={`gate__mastery gate__mastery--${kpStatus}`}>
            {kpStatus === 'passed' ? '✓ 已掌握' : `未掌握 · ${STATUS_LABEL[kpStatus]}`}
          </span>
        </div>

        {kpStatus === 'passed' ? (
          <div className="gate__passed">
            <span className="gate__passed-icon">🎉</span>
            <div className="gate__passed-text">
              <strong>「{kpName}」已通过阶段测试</strong>
              <span>进度已同步到学习路径、知识图谱与学情概览，当前节点已推进。</span>
            </div>
            <button className="gate__passed-btn" type="button" onClick={() => onNavigate?.('learning-path')}>
              去学下一个 →
            </button>
          </div>
        ) : !allStepsDone ? (
          /* 学习内容没走完 → 测试锁定，不渲染 QuizRenderer（不可作答 / 不可完成） */
          <div className="gate__locked">
            <span className="gate__locked-icon">🔒</span>
            <div className="gate__locked-text">
              <strong>阶段测试未解锁</strong>
              <span>
                先完成上面的 6 个学习步骤（当前 {completedCount}/6），测试将在末尾自动解锁——
                通过测试即点亮「已掌握」并推进学习路径进度。
              </span>
            </div>
          </div>
        ) : questions.length > 0 ? (
          <>
            <div className="gate__quiz-tip" onClick={onGoCheck}>
              准备好了就作答，提交后自动判分。
            </div>
            <QuizRenderer questions={questions} onSubmitResult={handleQuiz} />
            {wrongQs.length > 0 && <WeakPointReinforce wrong={wrongQs} />}
          </>
        ) : (
          <div className="resource-loading">「{kpName}」的阶段测试题准备中…</div>
        )}
      </section>
    </div>
  )
}
