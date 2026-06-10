import { useEffect, useRef, useState } from 'react'
import mermaid from 'mermaid'

mermaid.initialize({
  startOnLoad: false,
  theme: 'base',
  themeVariables: {
    primaryColor: '#eff6ff',
    primaryBorderColor: '#2563eb',
    primaryTextColor: '#1e293b',
    lineColor: '#94a3b8',
    fontFamily: 'inherit',
  },
})

let idSeq = 0

/** Mermaid 图解渲染（流程图 / 架构图等）*/
export default function MermaidDiagram({ chart }: { chart: string }) {
  const ref = useRef<HTMLDivElement>(null)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    const id = `mmd-${idSeq++}`
    mermaid
      .render(id, chart)
      .then(({ svg }) => {
        if (!cancelled && ref.current) ref.current.innerHTML = svg
      })
      .catch((e) => !cancelled && setErr(String(e?.message || e)))
    return () => {
      cancelled = true
    }
  }, [chart])

  if (err) return <div className="mermaid-error">图解渲染失败：{err}</div>
  return <div className="mermaid-diagram" ref={ref} />
}
