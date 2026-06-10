import { useEffect, useRef } from 'react'
import { Transformer } from 'markmap-lib'
import { Markmap } from 'markmap-view'

const transformer = new Transformer()

/** 思维导图：把 Markdown 大纲渲染成 markmap（SVG）*/
export default function MindMap({ markdown }: { markdown: string }) {
  const svgRef = useRef<SVGSVGElement>(null)
  const mmRef = useRef<Markmap | null>(null)

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
    requestAnimationFrame(() => mmRef.current?.fit())

    return () => {
      mmRef.current?.destroy()
      mmRef.current = null
    }
  }, [markdown])

  return <svg ref={svgRef} className="mindmap-svg" />
}
