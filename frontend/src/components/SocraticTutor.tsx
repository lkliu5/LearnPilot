import { useState, useRef } from 'react'
import { USE_REAL_API } from '../services/api'
import { tutorChatStream } from '../services/tutor'
import { getResourceKpId } from '../services/resourceNav'
import { suggestResources, type RemedialSuggestResult } from '../services/tutorResource'
import { KNOWLEDGE_POINTS } from '../data/knowledgePoints'
import TutorResourcePanel from './TutorResourcePanel'
import ChatPanel, { type ChatMsg as Msg } from './ChatPanel'

/* 苏格拉底式导学：用引导式提问而非直接喂答案。
   规则驱动的演示版（命中关键词走对应引导链；生产环境替换为 Agent 流式回复）。*/
const OPENING =
  '我是你的导学助手 🦉。学习「神经网络基础」时，我不会直接给答案，而是用提问引导你思考。先问你：你觉得一个神经元拿到输入后，第一步会做什么？'

interface Branch {
  match: RegExp
  reply: string
}

const branches: Branch[] = [
  { match: /加权|求和|相乘|权重|乘/, reply: '很好！加权求和之后，为了让神经元有「偏移」能力，通常还会加上一个量——你还记得它叫什么吗？（提示：让决策边界可平移）' },
  { match: /偏置|bias|b\b/i, reply: '没错，是偏置 b。那么加权求和再加偏置得到 z 之后，为什么不能直接把 z 当输出，而要再经过一个「激活函数」呢？想想如果全是线性运算会怎样？' },
  { match: /非线性|线性|拟合|复杂|表达/, reply: '正中要害——没有激活函数，多层网络叠起来仍等价于一个线性变换，无法拟合复杂模式。那你能说出一个最常用、且能缓解梯度消失的激活函数吗？' },
  { match: /relu|sigmoid|tanh|激活/i, reply: '👏 你已经把「加权求和 → 加偏置 → 激活」这条链路走通了！最后一个引导：网络是怎么知道该把权重往哪个方向调整的呢？（提示：和「损失」「梯度」有关）' },
  { match: /反向|梯度|backprop|损失|下降/, reply: '完美闭环 🎉 你已经独立推导出：前向传播得到输出 → 用损失衡量误差 → 反向传播算梯度 → 梯度下降更新权重。这正是神经网络学习的核心。要不要去「分阶测试」检验一下？' },
]

const fallback = '别急，换个角度想想：神经元的本质是把多个输入「汇总」成一个值。这个「汇总」最直接的数学操作是什么？（试试用「乘」和「加」描述）'

export default function SocraticTutor() {
  const [msgs, setMsgs] = useState<Msg[]>([{ role: 'agent', text: OPENING }])
  const [input, setInput] = useState('')
  const [typing, setTyping] = useState(false)

  const reply = (userText: string) => {
    const hit = branches.find((b) => b.match.test(userText))
    return hit ? hit.reply : fallback
  }

  /* B7-b 联调：8.7/15.4 SSE 流式（逐 delta 追加既有气泡，done 后刷新 suggestions chips）。
     首个 delta 前沿用打字三点动画；SSE 失败回退本地引导链（已渲染片段保留） */
  const sendLive = async (text: string) => {
    let acc = ''
    let started = false
    const appendDelta = (delta: string) => {
      acc += delta
      if (!started) {
        started = true
        setTyping(false)
        setMsgs((m) => [...m, { role: 'agent', text: acc }])
      } else {
        setMsgs((m) => [...m.slice(0, -1), { role: 'agent', text: acc }])
      }
    }
    try {
      const done = await tutorChatStream({
        kpId: getResourceKpId(),
        sessionId: sessionRef.current,
        message: text,
        onDelta: appendDelta,
      })
      sessionRef.current = done.sessionId
      if (done.suggestions.length) setChips(done.suggestions)
      setTyping(false)
      // 空流（无任何 delta）按失败处理，走本地引导链兜底
      if (!started) setMsgs((m) => [...m, { role: 'agent', text: reply(text) }])
    } catch (e) {
      console.error('[tutor] SSE 流式失败，回退本地引导链', e)
      setTyping(false)
      if (!started) setMsgs((m) => [...m, { role: 'agent', text: reply(text) }])
    }
  }

  /* 智能辅导·按需资源生成（8.8）：识别问题点 → 资源生成清单（学生勾选按需生成） */
  const [lastUser, setLastUser] = useState('')
  const [suggestion, setSuggestion] = useState<RemedialSuggestResult | null>(null)
  const [suggesting, setSuggesting] = useState(false)
  const askForHelp = async () => {
    if (suggesting) return
    setSuggesting(true)
    const kpId = getResourceKpId()
    const kpName = KNOWLEDGE_POINTS.find((k) => k.id === kpId)?.name ?? '当前知识点'
    const question = lastUser || '我没懂这个知识点，需要更直观的针对性资源'
    try {
      setSuggestion(await suggestResources(kpId, question, kpName))
    } catch (e) {
      console.error('[tutor] 资源建议失败', e)
    } finally {
      setSuggesting(false)
    }
  }

  const send = () => {
    const text = input.trim()
    if (!text || typing) return
    setLastUser(text)
    setMsgs((m) => [...m, { role: 'user', text }])
    setInput('')
    setTyping(true)
    if (USE_REAL_API) {
      void sendLive(text)
      return
    }
    const answer = reply(text)
    window.setTimeout(() => {
      setTyping(false)
      setMsgs((m) => [...m, { role: 'agent', text: answer }])
    }, 700)
  }

  const quick = ['先加权求和', '加上偏置 b', '因为要引入非线性', '反向传播+梯度下降']
  /* 联调：done 事件返回的 suggestions 覆盖快捷 chips（mock 模式恒为本地 quick，渲染零差异） */
  const [chips, setChips] = useState<string[]>(quick)
  const sessionRef = useRef<string | undefined>(undefined)

  return (
    <div className="socratic-wrap">
      <ChatPanel
        avatar="🦉"
        title="苏格拉底导学助手"
        subtitle="引导式提问 · 不直接给答案，帮你自己想通"
        msgs={msgs}
        typing={typing}
        chips={chips}
        onChip={setInput}
        input={input}
        onInput={setInput}
        onSend={send}
        placeholder="说说你的想法，我来引导你…"
        sending={typing}
      />

      {/* 智能辅导触发：卡住时一键识别问题点并给出针对性资源生成清单（8.8） */}
      <div className="socratic-help">
        <button className="socratic-help__btn" onClick={askForHelp} disabled={suggesting}>
          {suggesting ? '正在识别问题点…' : '💡 让 AI 答疑 · 生成针对性资源'}
        </button>
        {suggestion && <span className="socratic-help__hint">已根据你的问题识别盲区 ↓</span>}
      </div>

      {suggestion && <TutorResourcePanel suggestion={suggestion} />}
    </div>
  )
}
