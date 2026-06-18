import { useEffect, useRef, useState, lazy, Suspense } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import MarkdownRenderer from '../components/MarkdownRenderer'
import QuizRenderer, { type QuizQuestion } from '../components/QuizRenderer'
import SourceTrace, { type SourceRef } from '../components/SourceTrace'
import WeakPointReinforce from '../components/WeakPointReinforce'
import PageHeader from '../components/PageHeader'
import LearningFlow from '../components/LearningFlow'
import ResourceIllustration, { type ResourceIllustrationType } from '../components/ResourceIllustration'
import { RevealGroup, RevealItem } from '../components/Reveal'
import { useMastery, STATUS_LABEL } from '../store/mastery'
import { CURRENT_KP_ID, kpById } from '../data/knowledgePoints'
import { USE_REAL_API } from '../services/api'
import { getDiagram, getLecture, getQuiz, submitQuiz, type LectureData } from '../services/resource'
import type { ReviewRef } from '../services/learningFlow'
import { executeWorkflow, connectWorkflowSocket } from '../services/workflow'
import { consumeResourceEntryTab, getResourceKpId, getResourceMode, type ResourceMode } from '../services/resourceNav'
import { setWorkflowReplay } from '../services/workflowNav'
import type { PageType } from '../App'
import './LearningResource.css'

/* B10：工作流阶段 → 迷你进度文案（资源页重新生成时内嵌展示） */
const REGEN_PHASE_LABEL: Record<string, string> = {
  idle: '排队中',
  diagnosis: '学情诊断',
  generation: '资源生成',
  validation: '内容审核',
  complete: '已完成',
}

/* 后端讲义 sources（confidence 0-1）→ SourceTrace 展示口径（0-100） */
const toSourceRefs = (sources: LectureData['sources']): SourceRef[] =>
  sources.map((s) => ({
    title: s.title,
    type: s.type as SourceRef['type'],
    confidence: Math.round(s.confidence * 100),
  }))

/* 重型多模态组件按需懒加载（打开对应 Tab 才加载，保持页面轻量）*/
const MindMap = lazy(() => import('../components/MindMap'))
const CodeSandbox = lazy(() => import('../components/CodeSandbox'))
const MermaidDiagram = lazy(() => import('../components/MermaidDiagram'))
const VideoLecture = lazy(() => import('../components/VideoLecture'))
const ResourceAggregator = lazy(() => import('../components/ResourceAggregator'))
const SocraticTutor = lazy(() => import('../components/SocraticTutor'))

/* 模拟"领域知识生成 Agent"为当前学习者生成的个性化讲义（基于画像，难度自适应）*/
const lectureContent = `# 神经网络基础

> 本讲义由**领域知识生成 Agent**基于你的学情画像生成，难度已适配为「初级」，并经**内容审核 Agent** RAG 交叉校验（幻觉率 < 5%）。

## 一、什么是神经网络

神经网络（Neural Network）是一种受生物神经系统启发的计算模型。它由大量**神经元（Neuron）**相互连接构成，通过调整连接权重来学习数据中的规律。

一个神经元完成三步运算：

1. 对输入做**加权求和**
2. 加上**偏置（bias）**
3. 经过**激活函数**输出

## 二、前向传播

前向传播是数据从输入层流向输出层的过程。对单个神经元：

\`\`\`python
import numpy as np

def neuron(inputs, weights, bias):
    # 1. 加权求和 + 偏置
    z = np.dot(inputs, weights) + bias
    # 2. ReLU 激活
    return np.maximum(0, z)

x = np.array([0.5, 0.8, 0.2])
w = np.array([0.4, 0.7, 0.1])
print(neuron(x, w, bias=0.1))  # -> 0.88
\`\`\`

## 三、常见激活函数

- **ReLU**：\`max(0, x)\`，计算快、缓解梯度消失，最常用
- **Sigmoid**：将输出压缩到 (0, 1)，适合二分类输出层
- **Tanh**：输出范围 (-1, 1)，零均值，收敛通常快于 Sigmoid

## 四、反向传播与学习

网络通过**反向传播（Backpropagation）**计算损失对每个权重的梯度，再用**梯度下降**更新权重：

\`w ← w − η · ∂L/∂w\`

其中 \`η\` 是学习率（learning rate）。多轮迭代后，网络逐步逼近最优参数。

> **小结**：神经元 → 前向传播 → 激活 → 反向传播更新权重，构成了神经网络学习的完整闭环。下一步建议学习「深度学习原理」。`

/* 难度自适应：同一知识点的「入门 / 初级 / 高级」三档讲义（演示 Agent 实时再生成）*/
const lectureByLevel: Record<string, string> = {
  入门: `# 神经网络基础（入门版）

> 本讲义由**领域知识生成 Agent**按「入门」难度为你重新生成——用最直白的比喻，少公式。

## 一、把神经元想成一个「打分员」

想象一个评委给选手打分：他听到几个信息（输入），每个信息**重要程度不同**（权重），把它们综合起来给个分数，分数太低就当作 0（激活）。这就是一个**神经元**。

## 二、三步走

1. 把每个输入 × 它的重要程度，加起来（**加权求和**）
2. 再加一个「基础分」（**偏置**）
3. 太小的就归零，留下有用的（**激活函数 ReLU**）

## 三、很多神经元连起来

一个评委不够，就请很多评委分层投票——这就是**神经网络**。它通过不断调整「重要程度」，越打越准。

> **一句话**：神经网络 = 一群会自我调整的打分员。下一步可以看「初级版」了解具体计算。`,

  初级: lectureContent,

  高级: `# 神经网络基础（高级版）

> 本讲义由**领域知识生成 Agent**按「高级」难度生成——侧重数学形式化与工程细节。

## 一、神经元的数学形式

第 \`l\` 层第 \`j\` 个神经元：

\`\`\`
z_j^(l) = Σ_i w_ji^(l) · a_i^(l-1) + b_j^(l)
a_j^(l) = σ(z_j^(l))
\`\`\`

其中 \`σ\` 为激活函数，\`a^(0) = x\` 为输入。

## 二、前向传播（向量化）

整层以矩阵形式一次计算，效率远高于逐神经元：

\`\`\`python
Z = W @ A_prev + b      # W:(n_l, n_{l-1})
A = relu(Z)
\`\`\`

## 三、反向传播与梯度

链式法则逐层回传误差 \`δ\`：

\`\`\`
δ^(L) = ∇_a L ⊙ σ'(z^(L))
δ^(l) = (W^(l+1)ᵀ δ^(l+1)) ⊙ σ'(z^(l))
∂L/∂W^(l) = δ^(l) (a^(l-1))ᵀ
\`\`\`

## 四、工程要点

- **初始化**：He 初始化配 ReLU，避免梯度消失/爆炸
- **优化器**：Adam 自适应学习率，收敛快于朴素 SGD
- **正则化**：Dropout、BatchNorm、权重衰减抑制过拟合

> **小结**：掌握向量化前向 + 链式反向 + 初始化/优化/正则三件套，即可手写一个可训练的 MLP。下一步建议「深度学习原理 / CNN」。`,
}

const LEVELS = ['入门', '初级', '高级'] as const

const quizQuestions: QuizQuestion[] = [
  {
    question_id: 'q1',
    question_type: 'single',
    question_text: '一个神经元的运算顺序是？',
    options: [
      { option_id: 'a', option_text: '激活函数 → 加权求和 → 加偏置' },
      { option_id: 'b', option_text: '加权求和 → 加偏置 → 激活函数' },
      { option_id: 'c', option_text: '加偏置 → 激活函数 → 加权求和' },
    ],
    correct_answer: 'b',
    explanation: '神经元先对输入加权求和，再加上偏置，最后通过激活函数得到输出。',
  },
  {
    question_id: 'q2',
    question_type: 'multiple',
    question_text: '以下哪些是常见的激活函数？（多选）',
    options: [
      { option_id: 'a', option_text: 'ReLU' },
      { option_id: 'b', option_text: 'Sigmoid' },
      { option_id: 'c', option_text: 'Gradient' },
      { option_id: 'd', option_text: 'Tanh' },
    ],
    correct_answer: ['a', 'b', 'd'],
    explanation: 'ReLU、Sigmoid、Tanh 都是常见激活函数；Gradient（梯度）是反向传播中的概念，不是激活函数。',
  },
  {
    question_id: 'q3',
    question_type: 'boolean',
    question_text: 'ReLU 激活函数有助于缓解梯度消失问题。',
    options: [
      { option_id: 'true', option_text: '正确' },
      { option_id: 'false', option_text: '错误' },
    ],
    correct_answer: 'true',
    explanation: 'ReLU 在正区间梯度恒为 1，相比 Sigmoid 能有效缓解深层网络的梯度消失问题。',
  },
]

/* 思维导图大纲（由生成 Agent 从讲义结构化得到）*/
const mindmapMarkdown = `# 神经网络基础
## 神经元
### 加权求和 Σ w·x
### 加偏置 +b
### 激活函数
#### ReLU
#### Sigmoid
#### Tanh
## 前向传播
### 输入层 → 隐藏层 → 输出层
## 反向传播
### 计算梯度
### 梯度下降
### 学习率 η
## 进阶方向
### CNN
### RNN
### Transformer
`

/* 知识图解（神经元前向 / 反向流程）*/
const mermaidChart = `flowchart LR
  X["输入 x"] --> S(["加权求和<br/>Σ w·x"])
  W["权重 w"] --> S
  S --> B(["加偏置<br/>+ b"])
  B --> A{{"激活函数<br/>ReLU"}}
  A --> O["输出 a"]
  O -. 反向传播更新 .-> W
`

/* 资源中枢可打开的全部内容（5 张插画卡 + 测试 + 两个辅助项）；
   插画卡走 layoutId 共享元素过场，其余从主按钮/小 chip 打开。 */
type Tab = 'lecture' | 'video' | 'mindmap' | 'diagram' | 'code' | 'quiz' | 'external' | 'tutor'

/* 每个内容的详情头部主题色（沿用插画浅底，保持卡片→详情视觉连续）*/
const RESOURCE_META: Record<Tab, { title: string; theme: string }> = {
  lecture: { title: '定制讲义', theme: '#e7f4ee' },
  video: { title: '讲解视频', theme: '#e8f0fb' },
  mindmap: { title: '思维导图', theme: '#efeafb' },
  diagram: { title: '知识图解', theme: '#fbf2e2' },
  code: { title: '代码实操', theme: '#eceef3' },
  quiz: { title: '分阶测试', theme: 'color-mix(in srgb, var(--success-500) 14%, var(--surface))' },
  external: { title: '资源推荐', theme: 'color-mix(in srgb, var(--primary) 12%, var(--surface))' },
  tutor: { title: '导学对话', theme: 'color-mix(in srgb, var(--primary) 12%, var(--surface))' },
}

/* 学习内容 → 插画卡片网格（与 ResourceIllustration 的 5 个类型一一对应）*/
const RESOURCE_CARDS: { id: ResourceIllustrationType; title: string; desc: string }[] = [
  { id: 'lecture', title: '定制讲义', desc: '根据你的学习路径生成的个性化讲义，难度自适应、RAG 可溯源。' },
  { id: 'video', title: '讲解视频', desc: '动画演示与案例讲解，配同步旁白，更直观地理解知识点。' },
  { id: 'mindmap', title: '思维导图', desc: '把讲义结构化成知识脉络图，构建完整的知识体系。' },
  { id: 'diagram', title: '知识图解', desc: '图文结合的方式，更清晰地展示前向/反向的知识关系。' },
  { id: 'code', title: '代码实操', desc: '浏览器内可运行的示例，改完即时看结果，加深实践应用。' },
]

const ALL_TAB_IDS = Object.keys(RESOURCE_META)
const isTab = (v: string | null): v is Tab => !!v && ALL_TAB_IDS.includes(v)

/** 从讲义 markdown 提取标题大纲（跳过代码块内的 # 注释行），供思维导图结构化 */
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

const Loading = () => <div className="resource-loading">资源加载中…</div>

export default function LearningResource({ onNavigate }: { onNavigate?: (page: PageType) => void }) {
  /* 当前知识点：联调从 resourceNav 路由传参通道取（页面随导航重挂载，挂载时读取即可）；
     mock 模式恒为 CURRENT_KP_ID——本地演示内容只有 nn 一套，避免「标题 CNN、内容 nn」错配 */
  const kpId = USE_REAL_API ? getResourceKpId() : CURRENT_KP_ID
  /* 进入模式：「开始学习」→ flow（费曼+康奈尔有序流）；「查看资源」→ browse（8-tab 中枢）*/
  const [mode, setMode] = useState<ResourceMode>(() => getResourceMode())
  /* 资源详情过场：openId=当前打开的内容（null=只显示卡片网格）。
     落点：路径页「查看资源」带的落点 Tab 会直接展开对应内容；无显式落点则停在网格。 */
  const [openId, setOpenId] = useState<Tab | null>(() => {
    const t = consumeResourceEntryTab()
    return isTab(t) ? t : null
  })

  /* 费曼缺口「回看」：切到资源中枢，直接展开对应资源详情 */
  const REVIEW_KIND_TO_TAB: Record<string, Tab> = {
    lecture: 'lecture',
    video: 'video',
    diagram: 'diagram',
    mindmap: 'mindmap',
    quiz: 'quiz',
    code: 'code',
    external: 'external',
  }
  const handleReview = (ref: ReviewRef) => {
    setMode('browse')
    setOpenId(REVIEW_KIND_TO_TAB[ref.kind] ?? 'lecture')
  }
  const [level, setLevel] = useState<(typeof LEVELS)[number]>('初级')
  const [regenerating, setRegenerating] = useState(false)
  const [wrongQs, setWrongQs] = useState<QuizQuestion[]>([])
  const [trustOpen, setTrustOpen] = useState(false)

  /* 联调数据源（mock 模式下不使用，保持现有常量驱动）：
     questions 来自 GET /quiz/{kp}（联调初值为空，避免拉取期间闪现 nn 演示题）；
     lectureMap 缓存各难度档 markdown */
  const [questions, setQuestions] = useState<QuizQuestion[]>(USE_REAL_API ? [] : quizQuestions)
  const [lectureMap, setLectureMap] = useState<Record<string, string>>({})
  /* 知识图解 Mermaid：联调按当前 kpId 经后端 LLMClient 真实生成；mock 用本地常量 */
  const [diagramChart, setDiagramChart] = useState<string>('')
  /* B10：各难度档讲义的真实溯源 sources 与产出工作流 id（联调用，驱动溯源徽章/「查看生成过程」）*/
  const [lectureSources, setLectureSources] = useState<Record<string, SourceRef[]>>({})
  const [lectureWf, setLectureWf] = useState<Record<string, string | null>>({})
  /* B10：讲义「重新生成」闭环（仅联调）：确认弹层 / 实时进行中 / 迷你进度阶段文案 */
  const [regenConfirm, setRegenConfirm] = useState(false)
  const [regenRunning, setRegenRunning] = useState(false)
  const [regenPhase, setRegenPhase] = useState('诊断')
  const regenSocketRef = useRef<{ close: () => void } | null>(null)

  /* 联调：把一份讲义回包写入三个缓存映射（markdown / sources / workflowId） */
  const applyLecture = (lv: string, d: LectureData) => {
    setLectureMap((m) => ({ ...m, [lv]: d.markdown }))
    setLectureSources((m) => ({ ...m, [lv]: toSourceRefs(d.sources) }))
    setLectureWf((m) => ({ ...m, [lv]: d.workflowId }))
  }

  /* 知识点闭环状态：完成以"通过分阶测试(≥60%)"为唯一判定 */
  const kpStatus = useMastery((s) => s.status[kpId] ?? 'learning')
  const goCheck = useMastery((s) => s.goCheck)
  const markPassed = useMastery((s) => s.markPassed)
  const loadMastery = useMastery((s) => s.load)
  const kpName = kpById(kpId)?.name ?? '当前知识点'

  /* 联调初始化：拉取后端测验题 + 当前难度讲义 + 刷新掌握度（mock 模式跳过）*/
  useEffect(() => {
    if (!USE_REAL_API) return
    loadMastery()
    getQuiz(kpId)
      .then((d) => setQuestions(d.questions))
      .catch((e) => console.error('[resource] 加载测验题失败', e))
    getLecture(kpId, level)
      .then((d) => applyLecture(level, d))
      .catch((e) => console.error('[resource] 加载讲义失败', e))
    getDiagram(kpId)
      .then((d) => setDiagramChart(d.mermaid))
      .catch((e) => console.error('[resource] 加载知识图解失败', e))
    // 仅挂载时执行一次（level 初值为「初级」；kpId 挂载期内不变）
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  /* 卸载清理：断开可能在跑的重新生成 WS（不触发回退） */
  useEffect(() => () => regenSocketRef.current?.close(), [])

  /* 当前展示的讲义内容：联调取后端缓存，mock 取本地三档常量 */
  const activeLecture = USE_REAL_API ? lectureMap[level] ?? '' : lectureByLevel[level]

  /* 思维导图：联调由当前讲义 markdown 实时结构化（标题大纲，与"从讲义结构化得到"的
     设计一致；后端 8.4 导图接口未实现，讲义已按 kpId 请求故大纲随 kpId 变化）；
     mock 保持本地大纲常量 */
  const activeMindmap = USE_REAL_API ? lectureOutline(activeLecture) : mindmapMarkdown

  const handleQuizResult = (
    wrong: QuizQuestion[],
    submitted?: boolean,
    answers?: Record<string, string | string[]>
  ) => {
    setWrongQs(wrong)
    if (!submitted) return
    if (USE_REAL_API) {
      // 提交作答给后端判分；≥60 后端联动置 passed，再拉取掌握度刷新徽章
      submitQuiz(kpId, answers ?? {})
        .then(() => loadMastery())
        .catch((e) => console.error('[resource] 提交测验失败', e))
    } else if ((questions.length - wrong.length) / questions.length >= 0.6) {
      markPassed(kpId)
    }
  }

  /* 难度自适应：切换难度 → Agent 实时再生成讲义（mock 模拟 1.1s；联调请求后端）*/
  const changeLevel = (lv: (typeof LEVELS)[number]) => {
    if (lv === level || regenerating) return
    setRegenerating(true)
    if (USE_REAL_API) {
      getLecture(kpId, lv)
        .then((d) => {
          applyLecture(lv, d)
          setLevel(lv)
          setRegenerating(false)
        })
        .catch((e) => {
          console.error('[resource] 切换难度重生成失败', e)
          setLevel(lv)
          setRegenerating(false)
        })
      return
    }
    window.setTimeout(() => {
      setLevel(lv)
      setRegenerating(false)
    }, 1100)
  }

  /* ---------- B10：讲义「重新生成」闭环（仅联调；mock 模式不渲染入口） ---------- */

  /** 重新生成完成后轮询讲义直至命中本次工作流产物（后台 complete 后才提交回写）。 */
  const finishRegen = async (wfId: string) => {
    for (let i = 0; i < 15; i++) {
      try {
        const d = await getLecture(kpId, level)
        if (d.workflowId === wfId || i === 14) {
          applyLecture(level, d)
          break
        }
      } catch (e) {
        console.error('[resource] 重新生成后刷新讲义失败', e)
        break
      }
      await new Promise((r) => window.setTimeout(r, 400))
    }
    setRegenRunning(false)
  }

  /** 确认后触发：11.1 execute（当前 kp+难度）→ 11.2 WS 迷你进度 → complete 刷新讲义。 */
  const confirmRegen = async () => {
    setRegenConfirm(false)
    setRegenRunning(true)
    setRegenPhase('诊断')
    let wfId: string
    try {
      wfId = (await executeWorkflow({ kpId, difficulty: level })).workflowId
    } catch (e) {
      console.error('[resource] 触发重新生成失败', e)
      setRegenRunning(false)
      return
    }
    regenSocketRef.current = connectWorkflowSocket(wfId, {
      onFrame: (snap) => setRegenPhase(REGEN_PHASE_LABEL[snap.phase] ?? snap.phase),
      onComplete: () => {
        regenSocketRef.current = null
        void finishRegen(wfId)
      },
      onFail: (reason) => {
        console.error('[resource] 重新生成实时通道异常：', reason)
        regenSocketRef.current = null
        setRegenRunning(false)
      },
    })
  }

  /** 跳转大屏回放产出当前讲义的工作流（查看生成过程）。 */
  const viewGenerationProcess = () => {
    const wf = lectureWf[level]
    if (!wf) return
    setWorkflowReplay(wf)
    onNavigate?.('workflow')
  }

  /* ---------- 资源详情过场：打开 / 关闭 + Esc + 焦点管理 + 滚动锁 ---------- */
  const ILLUSTRATED = new Set<Tab>(['lecture', 'video', 'mindmap', 'diagram', 'code'])
  const openCard = (id: Tab) => {
    // 进入「分阶测试」沿用既有检验前置：未掌握时置 pending-check（passed 不回退）
    if (id === 'quiz' && kpStatus === 'learning') goCheck(kpId)
    setOpenId(id)
  }
  const closeCard = () => setOpenId(null)

  /* 打开详情时：Esc 关闭、锁背景滚动、关闭后焦点回到触发元素 */
  useEffect(() => {
    if (!openId) return
    const prev = document.activeElement as HTMLElement | null
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpenId(null)
    }
    window.addEventListener('keydown', onKey)
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', onKey)
      document.body.style.overflow = prevOverflow
      prev?.focus?.()
    }
  }, [openId])

  /* 单个内容的真实渲染（复用既有 /resource/* 数据与多模态组件）*/
  const renderBody = (id: Tab) => {
    switch (id) {
      case 'lecture':
        return (
          <>
            {/* 难度自适应再生成（讲义专属操作，归位到讲义详情）*/}
            <div className="level-switch">
              <span className="level-switch__label">难度自适应：</span>
              <div className="level-switch__seg">
                {LEVELS.map((lv) => (
                  <button
                    key={lv}
                    className={`level-switch__btn ${level === lv ? 'level-switch__btn--active' : ''}`}
                    onClick={() => changeLevel(lv)}
                    disabled={regenerating}
                  >
                    {lv}
                  </button>
                ))}
              </div>
              <span className="level-switch__hint">切换难度，AI 实时重生成讲义</span>
            </div>

            {/* B10：本档讲义产出工作流（仅联调）——查看生成过程 / 重新生成进行中提示 */}
            {USE_REAL_API && regenRunning && (
              <div className="lecture-regen-bar">
                <span className="lecture-regen-bar__progress">
                  <span className="lecture-regen-bar__orb" />
                  多智能体工作流 · {regenPhase}…
                </span>
              </div>
            )}
            {USE_REAL_API && !regenRunning && lectureWf[level] && (
              <div className="lecture-regen-bar">
                <button type="button" className="lecture-regen-bar__link" onClick={viewGenerationProcess}>
                  查看生成过程 →
                </button>
              </div>
            )}

            {/* RAG 溯源（针对讲义内容，归位到讲义详情底部工具条上方）*/}
            <SourceTrace sources={USE_REAL_API ? lectureSources[level] : undefined} />

            <div className="lecture-body">
              {activeLecture ? (
                <MarkdownRenderer content={activeLecture} />
              ) : (
                <div className="resource-loading">「{kpName}」的定制讲义生成中，请稍候…</div>
              )}
              <AnimatePresence>
                {regenerating && (
                  <motion.div
                    className="lecture-regen"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                  >
                    <div className="lecture-regen__orb" />
                    <span>领域知识生成 Agent 正在按新难度重生成讲义…</span>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </>
        )
      case 'video':
        return (
          <Suspense fallback={<Loading />}>
            <div className="resource-modal-hint">AI 生成的讲解视频（Remotion 渲染）+ 同步旁白，点击播放：</div>
            <VideoLecture />
          </Suspense>
        )
      case 'mindmap':
        return (
          <Suspense fallback={<Loading />}>
            <div className="resource-modal-hint">AI 已将讲义结构化为知识脉络图，可缩放/拖拽：</div>
            {activeMindmap ? (
              <MindMap markdown={activeMindmap} />
            ) : (
              <div className="resource-loading">「{kpName}」的讲义生成后将自动结构化为思维导图…</div>
            )}
          </Suspense>
        )
      case 'code':
        return (
          <Suspense fallback={<Loading />}>
            <div className="resource-modal-hint">浏览器内可运行的神经元示例，改完左侧代码即时看结果：</div>
            <CodeSandbox />
          </Suspense>
        )
      case 'diagram':
        return (
          <Suspense fallback={<Loading />}>
            <div className="resource-modal-hint">「{kpName}」知识脉络图（AI 按当前主题生成，可缩放/拖拽）：</div>
            {USE_REAL_API && !diagramChart ? (
              <div className="resource-loading">「{kpName}」的知识图解生成中，请稍候…</div>
            ) : (
              <MermaidDiagram chart={USE_REAL_API ? diagramChart : mermaidChart} />
            )}
          </Suspense>
        )
      case 'external':
        return (
          <Suspense fallback={<Loading />}>
            <ResourceAggregator />
          </Suspense>
        )
      case 'tutor':
        return (
          <Suspense fallback={<Loading />}>
            <SocraticTutor />
          </Suspense>
        )
      case 'quiz':
        return (
          <>
            <div className="resource-modal-hint">
              通过即点亮「已掌握」并推进进度（答对 ≥ 60% 判定通过）。
            </div>
            {questions.length > 0 ? (
              <QuizRenderer questions={questions} onSubmitResult={handleQuizResult} />
            ) : (
              <div className="resource-loading">「{kpName}」的分阶测试题准备中，请稍候…</div>
            )}
            {wrongQs.length > 0 && <WeakPointReinforce wrong={wrongQs} />}
          </>
        )
    }
  }

  return (
    <div className="resource-page">
      {/* 统一标题区：锚条 + 高亮 + 状态徽章组 */}
      <PageHeader
        title="个性化学习资源"
        highlight="学习资源"
        subtitle="AI 多模态资源包 · 讲义 / 思维导图 / 代码 / 图解 / 测试 · 难度自适应"
        badges={[
          { label: '当前知识点', value: kpName },
          {
            label: '状态',
            value: STATUS_LABEL[kpStatus],
            tone: kpStatus === 'passed' ? 'safe' : kpStatus === 'pending-check' ? 'accent' : 'default',
          },
          { label: '适配难度', value: level, tone: 'accent' },
          { label: 'RAG 引用文档', value: 12 },
        ]}
        actions={
          <button
            type="button"
            className={`resource-trust ${trustOpen ? 'resource-trust--open' : ''}`}
            onClick={() => setTrustOpen((o) => !o)}
            aria-expanded={trustOpen}
          >
            <svg className="resource-trust__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2 4 5v6c0 5 3.4 8.5 8 10 4.6-1.5 8-5 8-10V5l-8-3z" />
              <path d="m9 12 2 2 4-4" />
            </svg>
            <span className="resource-trust__main">
              <span className="resource-trust__value">已校验 · 幻觉率&lt;5%</span>
              <span className="resource-trust__label">可信度 · 点击查看机制</span>
            </span>
          </button>
        }
      />

      {trustOpen && (
        <div className="resource-trust-detail">
          <strong>多智能体交叉校验</strong>：领域知识生成 Agent 产出内容后，由内容审核 Agent 基于 RAG 知识库逐条核对术语与事实，一旦发现幻觉即打回重生成（最多 3 轮），最终幻觉率压至 <strong>&lt; 5%</strong>，确保你看到的讲义可信、可溯源。
        </div>
      )}

      {/* 模式切换：有序学习流（费曼+康奈尔） ↔ 资源中枢（8-tab 自由浏览） */}
      <div className="flow-mode">
        <button
          type="button"
          className={`flow-mode__btn ${mode === 'flow' ? 'flow-mode__btn--active' : ''}`}
          onClick={() => setMode('flow')}
        >
          🧭 有序学习
        </button>
        <button
          type="button"
          className={`flow-mode__btn ${mode === 'browse' ? 'flow-mode__btn--active' : ''}`}
          onClick={() => setMode('browse')}
        >
          🗂 资源中枢
        </button>
      </div>

      {mode === 'flow' && (
        <RevealGroup>
          <RevealItem className="resource-card">
            <LearningFlow
              kpId={kpId}
              kpName={kpName}
              level={level}
              lectureMarkdown={activeLecture}
              diagramChart={USE_REAL_API ? diagramChart : mermaidChart}
              questions={questions}
              kpStatus={kpStatus}
              onQuizResult={handleQuizResult}
              onGoCheck={() => goCheck(kpId)}
              onReview={handleReview}
              onNavigate={onNavigate}
            />
          </RevealItem>
        </RevealGroup>
      )}

      {mode === 'browse' && (
        <RevealGroup>
          {/* 学习内容 → 插画卡片网格（点击走 layoutId 过场展开详情）*/}
          <RevealItem className="rescard-grid">
            {RESOURCE_CARDS.map((c) => (
              <motion.button
                key={c.id}
                type="button"
                className="rescard"
                onClick={() => openCard(c.id)}
                whileHover={{ y: -5 }}
                whileTap={{ scale: 0.98 }}
              >
                <motion.span
                  className="rescard__illu"
                  layoutId={`res-illu-${c.id}`}
                  style={{ background: RESOURCE_META[c.id].theme }}
                >
                  <ResourceIllustration type={c.id} />
                </motion.span>
                <span className="rescard__meta">
                  <span className="rescard__title">{c.title}</span>
                  <span className="rescard__desc">{c.desc}</span>
                </span>
              </motion.button>
            ))}
          </RevealItem>

          {/* 阶段测试不再挂在资源中枢——它是有序学习流唯一的「终点 gate」（见 LearningFlow）。
             资源中枢仅用于自由浏览各形态资源，避免「看视频时却显示测试已完成」的跨资源串显。
             去测试请切到「🧭 有序学习」，走完学习步骤后在末尾解锁。 */}
          <RevealItem className="browse-hint">
            <span className="browse-hint__icon">🏁</span>
            <span className="browse-hint__text">
              阶段测试在「<button type="button" className="browse-hint__link" onClick={() => setMode('flow')}>🧭 有序学习</button>」流程末尾——
              走完视频 / 讲义 / 图解 / 笔记 / 费曼 / 实操后自动解锁，通过即点亮「已掌握」并推进进度。
            </span>
          </RevealItem>

          {/* 辅助项降级：次要小 chip 工具行（不与内容卡争视觉权重）*/}
          <RevealItem className="aux-chips">
            <span className="aux-chips__label">更多工具</span>
            <button type="button" className="aux-chip" onClick={() => openCard('tutor')}>
              💬 导学对话
            </button>
            <button type="button" className="aux-chip" onClick={() => openCard('external')}>
              🔗 资源推荐
            </button>
            {USE_REAL_API && (
              <button
                type="button"
                className="aux-chip"
                onClick={() => setRegenConfirm(true)}
                disabled={regenRunning || regenerating}
              >
                {regenRunning ? `⏳ 重新生成中 · ${regenPhase}…` : '🔄 重新生成讲义'}
              </button>
            )}
          </RevealItem>
        </RevealGroup>
      )}

      {/* 资源详情过场：layoutId 共享元素「长大」成详情头部，内容淡入；× / Esc / 点遮罩关闭 */}
      <AnimatePresence>
        {mode === 'browse' && openId && (
          <motion.div
            className="rescard-overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={closeCard}
            role="dialog"
            aria-modal="true"
            aria-label={RESOURCE_META[openId].title}
          >
            <motion.div className="rescard-detail" onClick={(e) => e.stopPropagation()}>
              {ILLUSTRATED.has(openId) ? (
                <motion.div
                  className="rescard-detail__head"
                  layoutId={`res-illu-${openId}`}
                  style={{ background: RESOURCE_META[openId].theme }}
                >
                  <ResourceIllustration type={openId as ResourceIllustrationType} />
                </motion.div>
              ) : (
                <motion.div
                  className="rescard-detail__head rescard-detail__head--plain"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  style={{ background: RESOURCE_META[openId].theme }}
                />
              )}
              <h3 className="rescard-detail__title">{RESOURCE_META[openId].title}</h3>
              <button
                type="button"
                className="rescard-detail__close"
                onClick={closeCard}
                autoFocus
                aria-label="关闭"
              >
                ×
              </button>

              <motion.div
                className="rescard-detail__body"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.12, duration: 0.25 }}
              >
                {renderBody(openId)}
              </motion.div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* B10：重新生成确认弹层（约需 20 秒提示） */}
      <AnimatePresence>
        {regenConfirm && (
          <motion.div
            className="regen-modal"
            role="dialog"
            aria-modal="true"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setRegenConfirm(false)}
          >
            <motion.div
              className="regen-modal__card"
              initial={{ opacity: 0, scale: 0.94, y: 12 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.94, y: 12 }}
              onClick={(e) => e.stopPropagation()}
            >
              <h4 className="regen-modal__title">重新生成讲义</h4>
              <p className="regen-modal__text">
                将调用<strong>多智能体工作流</strong>为「{kpName} · {level}」重新生成讲义
                （学情诊断 → 检索生成 → 内容审核），<strong>约需 20 秒</strong>。完成后讲义内容与
                溯源徽章将自动刷新。
              </p>
              <div className="regen-modal__actions">
                <button
                  type="button"
                  className="regen-modal__btn regen-modal__btn--ghost"
                  onClick={() => setRegenConfirm(false)}
                >
                  取消
                </button>
                <button
                  type="button"
                  className="regen-modal__btn regen-modal__btn--primary"
                  onClick={() => void confirmRegen()}
                >
                  确定生成
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
