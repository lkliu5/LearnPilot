import ReactMarkdown from 'react-markdown'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'

/**
 * Markdown 讲义渲染（react-markdown v9 + Prism 代码高亮）。
 * 注：v9 的 code 组件不再提供 inline 形参，改用是否带 language-* class 判定块级代码。
 */
export default function MarkdownRenderer({ content }: { content: string }) {
  return (
    <div className="markdown-body">
      <ReactMarkdown
        components={{
          code({ node: _node, className, children, ...props }) {
            const match = /language-(\w+)/.exec(className || '')
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
          h1: ({ children }) => <h1 className="resource-title">{children}</h1>,
          h2: ({ children }) => <h2 className="section-title">{children}</h2>,
          h3: ({ children }) => <h3 className="subsection-title">{children}</h3>,
          p: ({ children }) => <p className="content-paragraph">{children}</p>,
          ul: ({ children }) => <ul className="content-list">{children}</ul>,
          ol: ({ children }) => <ol className="ordered-list">{children}</ol>,
          blockquote: ({ children }) => <blockquote className="content-quote">{children}</blockquote>,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}
