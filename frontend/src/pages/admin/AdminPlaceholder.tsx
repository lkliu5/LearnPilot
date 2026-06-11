import { motion } from 'framer-motion'
import PageHeader from '../../components/PageHeader'
import './admin.css'

interface AdminPlaceholderProps {
  title: string
  highlight?: string
  subtitle?: string
  /** 占位说明：该页在哪个阶段交付、对应哪个接口 */
  note: string
}

/** B4-a 占位页：Prompt 管理 / 指标看板（B4-b 实装） */
export default function AdminPlaceholder({ title, highlight, subtitle, note }: AdminPlaceholderProps) {
  return (
    <div className="akb">
      <PageHeader title={title} highlight={highlight} subtitle={subtitle} />
      <motion.div
        className="akb__placeholder glass-card"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: 'easeOut' }}
      >
        <div className="akb__placeholder-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="9" />
            <path d="M12 7v5l3 3" />
          </svg>
        </div>
        <h3>建设中</h3>
        <p>{note}</p>
      </motion.div>
    </div>
  )
}
