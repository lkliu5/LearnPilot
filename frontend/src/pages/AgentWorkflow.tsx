import { useState, useRef, useLayoutEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { gsap } from 'gsap'
import { MotionPathPlugin } from 'gsap/MotionPathPlugin'
import { useGSAP } from '@gsap/react'
import AgentStatusCard from '../components/AgentStatusCard'
import CountUp from '../components/CountUp'
import PageHeader from '../components/PageHeader'
import { RevealGroup, RevealItem } from '../components/Reveal'
import './AgentWorkflow.css'

gsap.registerPlugin(useGSAP, MotionPathPlugin)

/* 连线定义：源节点 → 目标节点（用于测量真实坐标并生成曲线路径）*/
const EDGES = [
  { id: 'diagnosis', from: '.agent-node--orchestrator', to: '.agent-node--diagnosis' },
  { id: 'generation', from: '.agent-node--orchestrator', to: '.agent-node--generation' },
  { id: 'critic', from: '.agent-node--orchestrator', to: '.agent-node--critic' },
  { id: 'rag', from: '.agent-node--generation', to: '.agent-node--rag' },
]

type AgentStatus = 'idle' | 'running' | 'success' | 'error'
type WorkflowPhase = 'idle' | 'diagnosis' | 'generation' | 'validation' | 'complete'

interface AgentState {
  name: string
  status: AgentStatus
  lastAction: string
}

interface MessageLog {
  id: number
  from: string
  to: string
  message: string
  type: 'request' | 'response' | 'error'
  timestamp: Date
}

const agentConfig = [
  { id: 'diagnosis', name: '学情诊断Agent', icon: '🔍' },
  { id: 'generation', name: '领域知识生成Agent', icon: '📝' },
  { id: 'critic', name: '内容审核Agent', icon: '✓' }
]

export default function AgentWorkflow() {
  const [phase, setPhase] = useState<WorkflowPhase>('idle')
  const [agents, setAgents] = useState<AgentState[]>([
    { name: '学情诊断Agent', status: 'idle', lastAction: '等待用户输入' },
    { name: '领域知识生成Agent', status: 'idle', lastAction: '等待诊断结果' },
    { name: '内容审核Agent', status: 'idle', lastAction: '等待生成内容' }
  ])
  const [messages, setMessages] = useState<MessageLog[]>([])
  const [isRunning, setIsRunning] = useState(false)
  const [currentStep, setCurrentStep] = useState(0)

  /* GSAP G1：测量节点真实坐标 → 生成曲线连线路径 → 粒子沿路径流动 */
  const networkRef = useRef<HTMLDivElement>(null)
  const [edgePaths, setEdgePaths] = useState<{ id: string; d: string }[]>([])

  useLayoutEffect(() => {
    const net = networkRef.current
    if (!net) return
    const measure = () => {
      const base = net.getBoundingClientRect()
      const center = (sel: string) => {
        const el = net.querySelector(sel) as HTMLElement | null
        if (!el) return null
        const r = el.getBoundingClientRect()
        return { x: r.left - base.left + r.width / 2, y: r.top - base.top + r.height / 2 }
      }
      const curve = (a: { x: number; y: number }, b: { x: number; y: number }) => {
        const dx = b.x - a.x, dy = b.y - a.y
        const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2
        const k = 0.14 // 垂直方向轻微弧度
        const cx = mx - dy * k, cy = my + dx * k
        return `M ${a.x.toFixed(1)} ${a.y.toFixed(1)} Q ${cx.toFixed(1)} ${cy.toFixed(1)} ${b.x.toFixed(1)} ${b.y.toFixed(1)}`
      }
      const paths = EDGES
        .map((e) => ({ e, a: center(e.from), b: center(e.to) }))
        .filter((x) => x.a && x.b)
        .map((x) => ({ id: x.e.id, d: curve(x.a!, x.b!) }))
      setEdgePaths(paths)
    }
    measure()
    const ro = new ResizeObserver(measure)
    ro.observe(net)
    return () => ro.disconnect()
  }, [])

  /* 运行态：粒子沿每条连线路径流动（淡入 → 沿路径 → 淡出，循环）*/
  useGSAP(() => {
    const net = networkRef.current
    if (!net || !isRunning || edgePaths.length === 0) return
    const tls: gsap.core.Timeline[] = []
    edgePaths.forEach((p) => {
      const dots = net.querySelectorAll<SVGCircleElement>(`.msg-dot[data-edge="${p.id}"]`)
      dots.forEach((dot, di) => {
        const tl = gsap.timeline({ repeat: -1, delay: di * 0.85 })
        tl.set(dot, { opacity: 0 })
          .to(dot, { opacity: 1, duration: 0.25 }, 0)
          .to(dot, {
            duration: 1.7,
            ease: 'none',
            motionPath: { path: `#edge-path-${p.id}`, align: `#edge-path-${p.id}`, alignOrigin: [0.5, 0.5] },
          }, 0)
          .to(dot, { opacity: 0, duration: 0.25 }, 1.45)
        tls.push(tl)
      })
    })
    return () => tls.forEach((t) => t.kill())
  }, { dependencies: [isRunning, edgePaths], scope: networkRef })

  const simulateWorkflow = () => {
    setIsRunning(true)
    setPhase('diagnosis')
    setMessages([])

    // Phase 1: Diagnosis
    setAgents(prev => [
      { name: '学情诊断Agent', status: 'running', lastAction: '分析用户画像数据...' },
      prev[1],
      prev[2]
    ])
    setCurrentStep(1)

    setTimeout(() => {
      addMessage('用户', '学情诊断Agent', '提交学习者画像数据', 'request')
    }, 500)

    setTimeout(() => {
      addMessage('学情诊断Agent', '领域知识生成Agent', '诊断完成：识别知识盲区3处', 'response')
      setAgents(prev => [
        { name: '学情诊断Agent', status: 'success', lastAction: '诊断完成：识别3处盲区' },
        prev[1],
        prev[2]
      ])
    }, 2000)

    // Phase 2: Generation
    setTimeout(() => {
      setPhase('generation')
      setCurrentStep(2)
      setAgents(prev => [
        prev[0],
        { name: '领域知识生成Agent', status: 'running', lastAction: '生成个性化教学资源...' },
        prev[2]
      ])
      addMessage('领域知识生成Agent', 'RAG系统', '检索相关知识片段', 'request')
    }, 2500)

    setTimeout(() => {
      addMessage('RAG系统', '领域知识生成Agent', '返回12篇匹配文档', 'response')
    }, 3000)

    setTimeout(() => {
      addMessage('领域知识生成Agent', '内容审核Agent', '提交生成内容进行审核', 'response')
      setAgents(prev => [
        prev[0],
        { name: '领域知识生成Agent', status: 'success', lastAction: '生成讲义与测试题完成' },
        prev[2]
      ])
    }, 4000)

    // Phase 3: Validation
    setTimeout(() => {
      setPhase('validation')
      setCurrentStep(3)
      setAgents(prev => [
        prev[0],
        prev[1],
        { name: '内容审核Agent', status: 'running', lastAction: '验证内容准确性与合规性...' }
      ])
    }, 4500)

    setTimeout(() => {
      addMessage('内容审核Agent', '领域知识生成Agent', '交叉验证：内容通过审核', 'response')
      setAgents(prev => [
        prev[0],
        prev[1],
        { name: '内容审核Agent', status: 'success', lastAction: '审核通过：无幻觉风险' }
      ])
    }, 5500)

    // Complete
    setTimeout(() => {
      setPhase('complete')
      setCurrentStep(4)
      setIsRunning(false)
    }, 6000)
  }

  const addMessage = (from: string, to: string, message: string, type: 'request' | 'response' | 'error') => {
    setMessages(prev => [
      ...prev,
      {
        id: prev.length + 1,
        from,
        to,
        message,
        type,
        timestamp: new Date()
      }
    ])
  }

  const resetWorkflow = () => {
    setPhase('idle')
    setCurrentStep(0)
    setIsRunning(false)
    setAgents([
      { name: '学情诊断Agent', status: 'idle', lastAction: '等待用户输入' },
      { name: '领域知识生成Agent', status: 'idle', lastAction: '等待诊断结果' },
      { name: '内容审核Agent', status: 'idle', lastAction: '等待生成内容' }
    ])
    setMessages([])
  }

  const getPhaseLabel = () => {
    switch (phase) {
      case 'idle': return '等待启动'
      case 'diagnosis': return '学情诊断阶段'
      case 'generation': return '资源生成阶段'
      case 'validation': return '内容审核阶段'
      case 'complete': return '工作流完成'
    }
  }

  return (
    <div className="workflow-page">
      {/* 统一标题区：锚条 + 高亮 + 运行状态徽章 + 启动/重置 */}
      <PageHeader
        title="智能体协同调度大屏"
        highlight="协同调度"
        subtitle="实时查看多智能体工作流执行状态与决策逻辑"
        badges={[
          {
            label: '运行状态',
            value: isRunning ? '运行中' : phase === 'complete' ? '已完成' : '等待启动',
            tone: isRunning ? 'accent' : phase === 'complete' ? 'safe' : 'default',
          },
        ]}
        actions={
          <>
            <button
              className={`workflow-btn ${isRunning ? 'workflow-btn--disabled' : 'workflow-btn--primary'}`}
              onClick={simulateWorkflow}
              disabled={isRunning}
            >
              {isRunning ? '执行中...' : '启动演示'}
            </button>
            <button className="workflow-btn workflow-btn--secondary" onClick={resetWorkflow}>
              重置状态
            </button>
          </>
        }
      />

      <RevealGroup>
      {/* Phase Indicator */}
      <RevealItem className="workflow-phase">
        <div className="workflow-phase__steps">
          {['诊断', '生成', '审核', '完成'].map((step, index) => (
            <div
              key={step}
              className={`workflow-step ${currentStep > index ? 'workflow-step--completed' : currentStep === index + 1 ? 'workflow-step--active' : ''}`}
            >
              <div className="workflow-step__marker">
                {currentStep > index + 1 ? (
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                ) : (
                  <span>{index + 1}</span>
                )}
              </div>
              <span className="workflow-step__label">{step}</span>
            </div>
          ))}
        </div>
        <div className="workflow-phase__current">
          <motion.span
            key={phase}
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
          >
            {getPhaseLabel()}
          </motion.span>
        </div>
      </RevealItem>

      <RevealItem className="workflow-content">
        {/* Agent Network Visualization */}
        <div className="workflow-visualization">
          <div className="agent-network" ref={networkRef}>
            {/* Central Orchestration */}
            <div className="agent-node agent-node--orchestrator">
              <motion.div
                className="agent-node__icon"
                animate={isRunning ? { scale: [1, 1.05, 1] } : {}}
                transition={{ duration: 2, repeat: Infinity }}
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="3" />
                  <path d="M12 1v6M12 17v6M4.22 4.22l4.24 4.24M15.54 15.54l4.24 4.24M1 12h6M17 12h6M4.22 19.78l4.24-4.24M15.54 8.46l4.24-4.24" />
                </svg>
              </motion.div>
              <span className="agent-node__label">LangGraph编排器</span>
            </div>

            {/* Three Agents */}
            {agentConfig.map((agent, index) => {
              const state = agents[index]
              const isActive = state.status === 'running'

              return (
                <motion.div
                  key={agent.id}
                  className={`agent-node agent-node--${agent.id} agent-node--${state.status}`}
                  animate={isActive ? {
                    boxShadow: [
                      '0 0 0 0 rgba(37, 99, 235, 0)',
                      '0 0 24px 8px rgba(37, 99, 235, 0.28)',
                      '0 0 0 0 rgba(37, 99, 235, 0)'
                    ]
                  } : {}}
                  transition={{ duration: 1.5, repeat: Infinity }}
                >
                  <div className="agent-node__header">
                    <span className="agent-node__emoji">{agent.icon}</span>
                    <span className={`status-dot status-dot--${state.status}`} />
                  </div>
                  <span className="agent-node__name">{agent.name}</span>
                  <span className="agent-node__action">{state.lastAction}</span>
                </motion.div>
              )
            })}

            {/* RAG System */}
            <div className="agent-node agent-node--rag">
              <div className="agent-node__icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
                  <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
                  <line x1="8" y1="7" x2="16" y2="7" />
                  <line x1="8" y1="11" x2="16" y2="11" />
                </svg>
              </div>
              <span className="agent-node__label">RAG知识库</span>
            </div>

            {/* Connection Lines */}
            <div className="network-lines">
              <svg className={`network-svg ${isRunning ? 'network-svg--active' : ''}`}>
                <defs>
                  {/* 蓝紫流光渐变 + 发光滤镜 */}
                  <linearGradient id="flow-grad" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stopColor="#2563eb" />
                    <stop offset="100%" stopColor="#7c3aed" />
                  </linearGradient>
                  <filter id="line-glow" x="-50%" y="-50%" width="200%" height="200%">
                    <feGaussianBlur stdDeviation="2.5" result="blur" />
                    <feMerge>
                      <feMergeNode in="blur" />
                      <feMergeNode in="SourceGraphic" />
                    </feMerge>
                  </filter>
                </defs>
                {/* 连线路径（坐标由真实节点中心测量得到）*/}
                {edgePaths.map((p) => (
                  <path
                    key={p.id}
                    id={`edge-path-${p.id}`}
                    className={`network-line network-line--to-${p.id}`}
                    d={p.d}
                    fill="none"
                  />
                ))}
                {/* GSAP MotionPath 消息粒子（运行态沿连线流动）*/}
                {isRunning &&
                  edgePaths.map((p) =>
                    [0, 1].map((di) => (
                      <circle key={`${p.id}-${di}`} className="msg-dot" data-edge={p.id} r="3.5" />
                    ))
                  )}
              </svg>
            </div>
          </div>
        </div>

        {/* Agent Status List */}
        <div className="workflow-sidebar">
          <div className="sidebar-section">
            <h3>智能体状态</h3>
            <div className="agent-status-list">
              {agents.map((agent, index) => (
                <motion.div
                  key={index}
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: index * 0.1 }}
                >
                  <AgentStatusCard
                    name={agent.name}
                    status={agent.status}
                    lastAction={agent.lastAction}
                  />
                </motion.div>
              ))}
            </div>
          </div>

          <div className="sidebar-section">
            <h3>消息日志</h3>
            <div className="message-log">
              <AnimatePresence>
                {messages.map((msg) => (
                  <motion.div
                    key={msg.id}
                    className={`message-item message-item--${msg.type}`}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                  >
                    <div className="message-item__header">
                      <span className="message-item__from">{msg.from}</span>
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="message-item__arrow">
                        <path d="M5 12h14M12 5l7 7-7 7" />
                      </svg>
                      <span className="message-item__to">{msg.to}</span>
                    </div>
                    <span className="message-item__content">{msg.message}</span>
                  </motion.div>
                ))}
              </AnimatePresence>
              {messages.length === 0 && (
                <div className="message-log-empty">
                  <span>暂无消息记录</span>
                </div>
              )}
            </div>
          </div>

          <div className="sidebar-section">
            <h3>工作流统计</h3>
            <div className="workflow-stats">
              <div className="workflow-stat">
                <CountUp
                  className="workflow-stat__value"
                  value={agents.filter(a => a.status === 'success').length}
                  duration={0.6}
                />
                <span className="workflow-stat__label">已完成Agent</span>
              </div>
              <div className="workflow-stat">
                <CountUp className="workflow-stat__value" value={messages.length} duration={0.6} />
                <span className="workflow-stat__label">消息交互数</span>
              </div>
              <div className="workflow-stat">
                <CountUp
                  className="workflow-stat__value"
                  value={phase === 'complete' ? 100 : phase === 'idle' ? 0 : currentStep * 25}
                  suffix="%"
                  duration={0.6}
                />
                <span className="workflow-stat__label">工作流进度</span>
              </div>
            </div>
          </div>
        </div>
      </RevealItem>
      </RevealGroup>
    </div>
  )
}