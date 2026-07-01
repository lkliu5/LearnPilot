import { useEffect, useRef, useState } from 'react'
import { Transformer } from 'markmap-lib'
import { Markmap } from 'markmap-view'
import { downloadSvg, downloadSvgAsPng } from '../utils/resourceExport'

const transformer = new Transformer()

/**
 * 思维导图：把 Markdown 大纲渲染成 markmap（SVG）。
 * 传入 downloadName 时，在导图上方显示「下载 SVG / PNG」工具条（导出当前已渲染的导图，不重新生成）。
 */
export default function MindMap({ markdown, downloadName }: { markdown: string; downloadName?: string }) {
  const svgRef = useRef<SVGSVGElement>(null)
  const mmRef = useRef<Markmap | null>(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    if (!svgRef.current) return
    const { root } = transformer.transform(markdown)
    if (!mmRef.current) {
      mmRef.current = Markmap.create(svgRef.current, {
        autoFit: true,
        duration: 400,
        spacingVertical: 12,
        spacingHorizontal: 64,
        paddingX: 24,
        fitRatio: 0.92,
        color: (node) => {
          // 按层级配品牌蓝紫
          const palette = ['#2563eb', '#7c3aed', '#0d9488', '#f59e0b', '#64748b']
          return palette[(node.state?.depth ?? 0) % palette.length]
        },
      })
    }
    mmRef.current.setData(root)
    // 等布局与容器尺寸就绪后再 fit，避免裁切/偏移
    requestAnimationFrame(() => {
      mmRef.current?.fit()
      setReady(true)
    })

    return () => {
      mmRef.current?.destroy()
      mmRef.current = null
      setReady(false)
    }
  }, [markdown])

  const svg = <svg ref={svgRef} className="mindmap-svg" />
  if (!downloadName) return svg

  return (
    <div className="resource-export-block">
      <div className="lecture-export">
        <span className="lecture-export__label">下载导图：</span>
        <button
          type="button"
          className="lecture-export__btn"
          onClick={() => {
            if (svgRef.current) downloadSvg(svgRef.current, downloadName, 'start')
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
            if (svgRef.current) void downloadSvgAsPng(svgRef.current, downloadName, 'start')
          }}
          disabled={!ready}
          title="导出为位图（.png，便于插入文档/分享）"
        >
          <span aria-hidden="true">🖼</span> PNG
        </button>
      </div>
      {svg}
    </div>
  )
}
