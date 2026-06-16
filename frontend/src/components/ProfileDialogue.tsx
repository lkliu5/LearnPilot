import { useEffect, useRef, useState } from 'react'
import ChatPanel, { type ChatMsg } from './ChatPanel'
import StudentPortraitPanel from './StudentPortraitPanel'
import ProfileConfirmModal from './ProfileConfirmModal'
import {
  CANONICAL_DIMS,
  getStudentPortrait,
  profileDialogueStream,
  type PortraitDimension,
} from '../services/profileDialogue'
import { usePortrait } from '../store/portrait'
import './ProfileDialogue.css'

/**
 * 对话式学习画像诊断主路径（接口文档 17.1 + 17.2/17.3）。
 * 左：复用 ChatPanel 对话 UI（与 SocraticTutor 同款气泡 / 打字动画 / chip / SSE 逐 token）；
 * 右：StudentPortraitPanel 随 event:portrait 增量实时刷新异质 6 维。
 * 摒弃繁琐表单——对话为主路径；表单 / 材料上传由父级降级为次要入口。
 */
const OPENING =
  '你好，我是你的学习画像助手 ✦。咱们用聊天的方式——我边问你边了解情况，右侧画像会随对话实时「长」出来，不用填表。先聊聊：你现在的专业或职业背景是什么？平时接触编程 / AI 多吗？'

const OPENING_CHIPS = ['计算机本科，会点 Python', '非科班，自学中', '有工作经验想转 AI']

interface Props {
  /** 诊断完成后的衔接：沿用既有 completeDiagnosis + 导航流程 */
  onFinish: () => void
  context?: { major?: string; goal?: string }
}

export default function ProfileDialogue({ onFinish, context }: Props) {
  const [msgs, setMsgs] = useState<ChatMsg[]>([{ role: 'agent', text: OPENING }])
  const [input, setInput] = useState('')
  const [typing, setTyping] = useState(false)
  const [sending, setSending] = useState(false)
  const [chips, setChips] = useState<string[]>(OPENING_CHIPS)
  const [complete, setComplete] = useState(false)

  /** 异质画像维度（按 key 索引，event:portrait 增量合并） */
  const [dims, setDims] = useState<Record<string, PortraitDimension>>({})
  const [portraitTs, setPortraitTs] = useState<string | undefined>(undefined)
  const sessionRef = useRef<string | undefined>(undefined)

  /** 「学情概况确认」弹窗：诊断完成且满 6 维才弹（防止确认到不足维度的画像） */
  const [showConfirm, setShowConfirm] = useState(false)
  const setPortrait = usePortrait((s) => s.setPortrait)

  const filledCount = CANONICAL_DIMS.filter((c) => dims[c.key]).length
  const allDimsFilled = filledCount >= CANONICAL_DIMS.length

  // 满 6 维 + diagnosisComplete 才自动弹确认弹窗（dims 异步落定后由本 effect 触发，避免时序竞态）
  useEffect(() => {
    if (complete && allDimsFilled) setShowConfirm(true)
  }, [complete, allDimsFilled])

  // 确认画像：落快照（学情概览据此合成）→ 走既有完成流程（completeDiagnosis + 解锁学习路径）
  const handleConfirm = () => {
    setPortrait(Object.values(dims), portraitTs)
    setShowConfirm(false)
    onFinish()
  }

  // 进页拉取当前画像（联调时可能已有历史维度；mock 返回空画像）
  useEffect(() => {
    let cancelled = false
    getStudentPortrait()
      .then((p) => {
        if (cancelled) return
        if (p.dimensions.length) {
          setDims(Object.fromEntries(p.dimensions.map((d) => [d.key, d])))
          setPortraitTs(p.updatedAt)
        }
      })
      .catch((e) => console.error('[profile-dialogue] 拉取画像失败', e))
    return () => {
      cancelled = true
    }
  }, [])

  const applyPortrait = (updates: PortraitDimension[]) => {
    if (!updates.length) return
    setDims((prev) => {
      const next = { ...prev }
      for (const u of updates) next[u.key] = u
      return next
    })
    setPortraitTs(updates[updates.length - 1].updatedAt ?? new Date().toISOString())
  }

  /* 17.1 SSE：逐 delta 追加既有 agent 气泡；event:portrait 实时刷右栏；done 后刷新 chips + 完成态。
     首个 delta 前沿用打字三点动画；失败保留已渲染片段与已抽取维度（17.1 约定）。 */
  const send = async () => {
    const text = input.trim()
    if (!text || sending) return
    setMsgs((m) => [...m, { role: 'user', text }])
    setInput('')
    setTyping(true)
    setSending(true)

    let acc = ''
    let started = false
    const appendDelta = (delta: string) => {
      acc += delta
      if (!started) {
        started = true
        setTyping(false)
        setMsgs((m) => [...m, { role: 'agent', text: acc }])
      } else {
        // 仅当末条确为正在流式的 agent 气泡时才改写其文本；否则追加新气泡，
        // 杜绝误把用户气泡覆盖成 agent（修正气泡 role 归属，issue#2）。
        setMsgs((m) => {
          const last = m[m.length - 1]
          return last && last.role === 'agent'
            ? [...m.slice(0, -1), { role: 'agent', text: acc }]
            : [...m, { role: 'agent', text: acc }]
        })
      }
    }

    try {
      const done = await profileDialogueStream({
        sessionId: sessionRef.current,
        message: text,
        context: sessionRef.current ? undefined : context, // 仅首轮带冷启动 context
        onDelta: appendDelta,
        onPortrait: applyPortrait,
      })
      sessionRef.current = done.sessionId
      if (done.suggestions.length) setChips(done.suggestions)
      if (done.diagnosisComplete) setComplete(true)
      // 空流兜底（无任何 delta）
      if (!started) setMsgs((m) => [...m, { role: 'agent', text: '（已记录你的回答）' }])
    } catch (e) {
      console.error('[profile-dialogue] SSE 失败', e)
      if (!started) setMsgs((m) => [...m, { role: 'agent', text: '抱歉，我刚才没接上话，要不你再说一次？' }])
    } finally {
      setTyping(false)
      setSending(false)
    }
  }

  return (
    <div className="pd">
      <div className="pd__chat profile-builder__card">
        <ChatPanel
          avatar="🎓"
          title="学习画像助手"
          subtitle="自然语言对话 · 自动抽取特征 · 摒弃繁琐表单"
          msgs={msgs}
          typing={typing}
          chips={chips}
          onChip={(q) => (q.startsWith('生成') ? setShowConfirm(true) : setInput(q))}
          input={input}
          onInput={setInput}
          onSend={send}
          placeholder="用自己的话说说你的情况…"
          sending={sending}
        />
      </div>

      <aside className="pd__aside">
        {/* 完成态（内嵌按钮）同样以「满 6 维」为门槛，点击打开确认弹窗而非直接跳转 */}
        <StudentPortraitPanel
          dims={dims}
          updatedAt={portraitTs}
          complete={complete && allDimsFilled}
          onFinish={() => setShowConfirm(true)}
        />
      </aside>

      <ProfileConfirmModal
        open={showConfirm}
        dims={dims}
        updatedAt={portraitTs}
        onConfirm={handleConfirm}
        onClose={() => setShowConfirm(false)}
      />
    </div>
  )
}
