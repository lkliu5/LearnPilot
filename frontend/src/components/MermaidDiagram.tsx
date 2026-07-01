import { useEffect, useRef, useState } from 'react'
import mermaid from 'mermaid'
import { downloadSvg, downloadSvgAsPng } from '../utils/resourceExport'
import { sanitizeMermaid } from '../utils/mermaidSanitize'

mermaid.initialize({
  startOnLoad: false,
  theme: 'base',
  // 关键：解析 / 渲染失败时**不要**把 mermaid 自带的报错图（"error in text … version 11.x"）
  // 注入进 DOM——否则该错误图会漏到页面背景形成满屏「串图」。失败一律走本组件兜底 UI。
  suppressErrorRendering: true,
  themeVariables: {
    primaryColor: '#eff6ff',
    primaryBorderColor: '#2563eb',
    primaryTextColor: '#1e293b',
    lineColor: '#94a3b8',
    fontFamily: 'inherit',
  },
})

let idSeq = 0

/**
 * Mermaid 图解渲染（流程图 / 架构图等）。
 * 传入 downloadName 时，在图解上方显示「下载 SVG / PNG」工具条（导出当前已渲染的图，不重新生成）；
 * 不传则保持原样（讲义内嵌图解等场景零变化）。
 */
export default function MermaidDiagram({ chart, downloadName }: { chart: string; downloadName?: string }) {
  const ref = useRef<HTMLDivElement>(null)
  const [err, setErr] = useState<string | null>(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    let cancelled = false
    setReady(false)
    setErr(null)
    const id = `mmd-${idSeq++}`
    // 渲染前清洗节点标签特殊字符（数学公式 / <、>、() 、[] 等），降低 Parse error；
    // 再用 mermaid.parse(suppressErrors) 先行校验——非法语法只返回 false、绝不注入报错图，
    // 从而任何失败都被本组件兜底 UI 收住，绝不漏到页面背景。
    const run = async () => {
      try {
        const src = sanitizeMermaid(chart)
        const ok = await mermaid.parse(src, { suppressErrors: true })
        if (ok === false) throw new Error('图解语法无法解析')
        const { svg } = await mermaid.render(id, src)
        if (!cancelled && ref.current) {
          ref.current.innerHTML = svg
          setReady(true)
        }
      } catch (e) {
        if (!cancelled) setErr(String((e as Error)?.message || e))
      }
    }
    void run()
    return () => {
      cancelled = true
    }
  }, [chart])

  if (err) return <div className="mermaid-error">图解渲染失败：{err}</div>

  const diagram = <div className="mermaid-diagram" ref={ref} />
  if (!downloadName) return diagram

  const getSvg = () => ref.current?.querySelector('svg') as SVGSVGElement | null

  return (
    <div className="resource-export-block">
      <div className="lecture-export">
        <span className="lecture-export__label">下载图解：</span>
        <button
          type="button"
          className="lecture-export__btn"
          onClick={() => {
            const svg = getSvg()
            if (svg) downloadSvg(svg, downloadName, 'middle')
          }}
          disabled={!ready}
          title="下载矢量图（.svg，可无损缩放）"
        >
          <span aria-hidden="true">⬇</span> SVG
        </button>
        <button
          type="button"
          className="lecture-export__btn lecture-export__btn--pdf"
          onClick={() => {
            const svg = getSvg()
            if (svg) void downloadSvgAsPng(svg, downloadName, 'middle')
          }}
          disabled={!ready}
          title="导出为位图（.png，便于插入文档/分享）"
        >
          <span aria-hidden="true">🖼</span> PNG
        </button>
      </div>
      {diagram}
    </div>
  )
}
