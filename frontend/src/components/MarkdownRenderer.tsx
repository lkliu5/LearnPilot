import { lazy, Suspense, useState } from 'react'
import ReactMarkdown, { defaultUrlTransform } from 'react-markdown'
import remarkMath from 'remark-math'
import remarkGfm from 'remark-gfm'
import rehypeKatex from 'rehype-katex'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'
import 'katex/dist/katex.min.css'

// 讲义内嵌图解：```mermaid 围栏复用既有 MermaidDiagram 渲染（懒加载，避免无图解页引入 mermaid）。
const MermaidDiagram = lazy(() => import('./MermaidDiagram'))

/**
 * 讲义配图：图片渲染 + 来源标注（来源走紧随其后的 Markdown 段落）+ 裂图兜底。
 * 加载失败时优雅隐藏破图、显示占位（不显示浏览器默认破图标）。
 */
function MarkdownImage({ src, alt }: { src?: string; alt?: string }) {
  const [failed, setFailed] = useState(false)
  if (!src || failed) {
    return (
      <span className="md-image-fallback" role="img" aria-label={alt || '图片暂不可用'}>
        🖼️ 图片暂不可用
      </span>
    )
  }
  return (
    <img
      className="md-image"
      src={src}
      alt={alt || ''}
      loading="lazy"
      onError={() => setFailed(true)}
    />
  )
}

/**
 * Markdown 讲义渲染（react-markdown v9 + Prism 代码高亮 + KaTeX 数学公式）。
 * - remark-math 解析行内 $...$ 与块级 $$...$$，rehype-katex 渲染为公式；
 * - remark-gfm 解析 GFM 扩展（表格 | --- |、删除线 ~~、任务列表 - [ ]、自动链接）；
 * - ```mermaid 围栏走 MermaidDiagram（讲义内嵌结构 / 流程图解）；
 * - 图片走 MarkdownImage（来源标注 + 裂图兜底）；urlTransform 放行自包含 data:image 占位图。
 */
export default function MarkdownRenderer({ content }: { content: string }) {
  return (
    <div className="markdown-body">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        urlTransform={(url) => (url.startsWith('data:image/') ? url : defaultUrlTransform(url))}
        components={{
          code({ node: _node, className, children, ...props }) {
            const match = /language-(\w+)/.exec(className || '')
            if (match && match[1] === 'mermaid') {
              return (
                <Suspense fallback={<div className="mermaid-loading">图解加载中…</div>}>
                  <MermaidDiagram chart={String(children).replace(/\n$/, '')} />
                </Suspense>
              )
            }
            return match ? (
              <SyntaxHighlighter
                style={oneDark}
                language={match[1]}
                PreTag="div"
                customStyle={{ borderRadius: '12px', margin: '16px 0', fontSize: '13px' }}
              >
                {String(children).replace(/\n$/, '')}
              </SyntaxHighlighter>
            ) : (
              <code className="md-inline-code" {...props}>
                {children}
              </code>
            )
          },
          pre: ({ children }) => <div className="md-codeblock">{children}</div>,
          img: ({ src, alt }) => <MarkdownImage src={typeof src === 'string' ? src : undefined} alt={alt} />,
          h1: ({ children }) => <h1 className="resource-title">{children}</h1>,
          h2: ({ children }) => <h2 className="section-title">{children}</h2>,
          h3: ({ children }) => <h3 className="subsection-title">{children}</h3>,
          p: ({ children }) => <p className="content-paragraph">{children}</p>,
          ul: ({ children }) => <ul className="content-list">{children}</ul>,
          ol: ({ children }) => <ol className="ordered-list">{children}</ol>,
          blockquote: ({ children }) => <blockquote className="content-quote">{children}</blockquote>,
          // GFM 表格：包一层可横向滚动容器，宽表（如多列对比表）不撑破讲义布局。
          table: ({ children }) => (
            <div className="md-table-wrap">
              <table className="md-table">{children}</table>
            </div>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}
