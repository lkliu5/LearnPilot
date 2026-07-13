import { useEffect, useRef, useState } from 'react'
import ChatPanel, { type ChatMsg } from './ChatPanel'
import SourceTrace from './SourceTrace'
import { streamDocChat } from '../services/documentChat'
import type { SourceRef } from './SourceTrace'
import './DocumentChat.css'

/**
 * 和文档对话（NotebookLM 式中栏主交互区，接口文档 20.8）。
 *
 * 就选中的一篇或多篇文档「即问即答」：流式逐字回答、**严格基于文档内容**、标出处溯源。
 * 复用站内通用对话面板 ChatPanel（`.socratic` 设计令牌 + SSE 增量渲染节奏）与 SourceTrace
 * 溯源组件；问答历史保留在本组件状态。切换选中范围（docIds）→ 重置会话上下文，历史另起。
 *
 * 与右栏「基于文档生成资源」相互独立：这里是「理解文档」，不生成资源。
 */
const CHIPS = ['这篇文档主要讲了什么？', '核心概念/定理有哪些？', '帮我总结关键要点', '有哪些需要重点理解的地方？']

interface DocumentChatProps {
  /** 问答范围：勾选的文档 id（首个为主文档）。为空时禁用输入。 */
  docIds: string[]
  /** 与 docIds 对应的标题（用于副标题展示范围）。 */
  docTitles: string[]
}

export default function DocumentChat({ docIds, docTitles }: DocumentChatProps) {
  const [msgs, setMsgs] = useState<ChatMsg[]>([])
  const [input, setInput] = useState('')
  const [typing, setTyping] = useState(false)
  const [sending, setSending] = useState(false)
  const [sessionId, setSessionId] = useState<string | undefined>(undefined)
  /** 每轮回答的溯源（展示在最新回答下方，标出处）。 */
  const [answerSources, setAnswerSources] = useState<Record<number, SourceRef[]>>({})

  /** 溯源默认收起：答案正文为主，参考文献作为可选查看的辅助（点击展开）。 */
  const [srcOpen, setSrcOpen] = useState(false)

  const control = useRef({ cancelled: false })
  const scopeKey = docIds.join(',')

  /* 切换问答范围 → 中止进行中的流、另起会话上下文（历史清零，避免跨文档串味）。 */
  useEffect(() => {
    control.current.cancelled = true
    control.current = { cancelled: false }
    setSessionId(undefined)
    setMsgs([])
    setAnswerSources({})
    setTyping(false)
    setSending(false)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scopeKey])

  /* 卸载即中止流式读取。 */
  useEffect(() => () => {
    control.current.cancelled = true
  }, [])

  const disabled = docIds.length === 0
  const scopeLabel = disabled
    ? '先在左侧勾选文档，再开始提问'
    : docTitles.length === 1
      ? `正在就《${docTitles[0]}》对话 · 严格基于文档、标注出处`
      : `正在就 ${docTitles.length} 篇文档对话 · 严格基于所选文档、标注出处`

  const send = async (text: string) => {
    const q = text.trim()
    if (!q || disabled || sending) return
    setInput('')
    // 记录本轮 agent 气泡的索引（user 之后），用于把溯源挂到该条回答下
    let agentIdx = -1
    setMsgs((m) => {
      agentIdx = m.length + 1
      return [...m, { role: 'user', text: q }]
    })
    setTyping(true)
    setSending(true)
    control.current.cancelled = false

    let acc = ''
    let started = false
    const appendDelta = (d: string) => {
      acc += d
      if (!started) {
        started = true
        setTyping(false)
        setMsgs((m) => [...m, { role: 'agent', text: acc }])
      } else {
        setMsgs((m) => [...m.slice(0, -1), { role: 'agent', text: acc }])
      }
    }

    try {
      const done = await streamDocChat(
        { documentIds: docIds, sessionId, message: q, onDelta: appendDelta },
        control.current
      )
      if (control.current.cancelled) return
      if (done.sessionId) setSessionId(done.sessionId)
      if (done.sources.length && agentIdx >= 0) {
        setAnswerSources((prev) => ({ ...prev, [agentIdx]: done.sources }))
      }
    } catch (e) {
      console.error('[doc-chat] 回答失败', e)
      if (!started) setMsgs((m) => [...m, { role: 'agent', text: '抱歉，本次回答生成失败，请稍后重试。' }])
    } finally {
      setTyping(false)
      setSending(false)
    }
  }

  /* 把最新回答的溯源渲染在对话区与输入区之间的常驻插槽（belowChat）。 */
  const latestAgentIdx = (() => {
    for (let i = msgs.length - 1; i >= 0; i--) if (msgs[i].role === 'agent') return i
    return -1
  })()
  const latestSources = latestAgentIdx >= 0 ? answerSources[latestAgentIdx] : undefined

  /* 每轮新回答到来 → 溯源自动收起，保证用户先看清答案正文，再按需展开来源。 */
  useEffect(() => {
    setSrcOpen(false)
  }, [latestAgentIdx])

  return (
    <ChatPanel
      className="docchat"
      avatar="📄"
      title="和文档对话"
      subtitle={scopeLabel}
      msgs={msgs}
      emptySlot={
        /* NotebookLM 式大文档卡（纯展示空状态）：大图标 + 大标题 + 来源数 + 欢迎语；有消息后自动让位给气泡流 */
        <div className="docchat-hero">
          <span className="docchat-hero__wm" aria-hidden="true">
            〜
          </span>
          <span className="docchat-hero__icon" aria-hidden="true">
            {disabled ? '📄' : '📘'}
          </span>
          <h2 className="docchat-hero__title">
            {disabled ? '和文档对话' : docTitles.length === 1 ? docTitles[0] : `${docTitles.length} 篇文档 · 合并对话`}
          </h2>
          <div className="docchat-hero__meta">
            {disabled
              ? '在左栏上传并勾选文档后，即可开始提问'
              : `${docIds.length} 个来源 · 就绪 · 严格基于文档作答并标注出处`}
          </div>
          <p className="docchat-hero__welcome">
            {disabled
              ? '你好！左侧勾选一篇或多篇文档后，就可以在这里向我提问，我会严格根据文档内容回答并标注出处。'
              : '你好！我已读取所选文档。问我任何关于它的问题，我会严格基于文档内容作答，并在末尾标注出处来源。'}
          </p>
        </div>
      }
      typing={typing}
      chips={disabled ? [] : CHIPS}
      onChip={(t) => void send(t)}
      input={input}
      onInput={setInput}
      onSend={() => void send(input)}
      placeholder={disabled ? '请先在左侧勾选文档…' : '就这篇/这些文档提问，例如：核心概念是什么？'}
      sendLabel="提问"
      sending={sending}
      locked={disabled}
      belowChat={
        latestSources && latestSources.length ? (
          <div className={`docchat__src${srcOpen ? ' docchat__src--open' : ''}`}>
            <button
              type="button"
              className="docchat__src-toggle"
              onClick={() => setSrcOpen((v) => !v)}
              aria-expanded={srcOpen}
            >
              <span className="docchat__src-caret" aria-hidden="true">
                {srcOpen ? '▾' : '▸'}
              </span>
              <span className="docchat__src-icon" aria-hidden="true">
                🛡
              </span>
              {srcOpen ? '收起来源' : `查看来源 [${latestSources.length} 篇]`}
            </button>
            {srcOpen && <SourceTrace sources={latestSources} />}
          </div>
        ) : null
      }
    />
  )
}
