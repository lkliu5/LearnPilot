import { useEffect, useRef, useState } from 'react'
import { openInstantTutor } from '../services/tutorBus'
import './InstantTutorExtras.css'

/**
 * 选中即问（B-2）：在讲义阅读区选中一段文字，就近浮出「就这段问 AI」。
 * 点击把选中的具体句子作为问题上下文发起即时辅导，让针对性具体到句子。
 * 仅当选区落在传入的容器内、且文本非空（≥4 字）时才弹；选空 / 另起选择即收起。
 */
interface Props {
  /** 监听选区的容器（讲义正文）；选区不在其中则不弹 */
  containerRef: React.RefObject<HTMLElement>
}

export default function SelectionAskBubble({ containerRef }: Props) {
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null)
  const textRef = useRef('')

  useEffect(() => {
    const onUp = () => {
      const sel = window.getSelection()
      const container = containerRef.current
      if (!sel || sel.isCollapsed || !sel.rangeCount || !container) {
        setPos(null)
        return
      }
      const text = sel.toString().trim()
      const anchor = sel.anchorNode
      const focus = sel.focusNode
      // 文本太短、或选区端点不在讲义容器内 → 不弹
      if (
        text.length < 4 ||
        !anchor ||
        !container.contains(anchor) ||
        (focus && !container.contains(focus))
      ) {
        setPos(null)
        return
      }
      const rect = sel.getRangeAt(0).getBoundingClientRect()
      if (!rect.width && !rect.height) {
        setPos(null)
        return
      }
      textRef.current = text
      setPos({ x: rect.left + rect.width / 2, y: rect.top })
    }
    // 另起一次按下（开始新选择 / 点击别处）先收起，避免气泡滞留
    const onDown = () => setPos(null)
    document.addEventListener('mouseup', onUp)
    document.addEventListener('mousedown', onDown)
    return () => {
      document.removeEventListener('mouseup', onUp)
      document.removeEventListener('mousedown', onDown)
    }
  }, [containerRef])

  if (!pos) return null

  const ask = () => {
    const t = textRef.current.replace(/\s+/g, ' ').slice(0, 120)
    openInstantTutor({
      question: `讲义里这句没太看懂：“${t}”，帮我把它讲清楚`,
      autoAsk: true,
    })
    setPos(null)
    window.getSelection()?.removeAllRanges()
  }

  return (
    <button
      type="button"
      className="sel-ask-bubble"
      style={{ left: pos.x, top: pos.y }}
      // 阻止默认 + 冒泡：点击气泡时不清除选区、不触发上面的收起逻辑
      onMouseDown={(e) => {
        e.preventDefault()
        e.stopPropagation()
      }}
      onClick={ask}
    >
      💡 就这段问 AI
    </button>
  )
}
