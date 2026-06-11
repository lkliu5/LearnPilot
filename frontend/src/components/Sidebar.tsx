import { motion } from 'framer-motion'
import type { PageType } from '../App'
import { useJourney } from '../store/journey'
import { useMastery } from '../store/mastery'
import { getUser } from '../services/api'
import './Sidebar.css'

interface SidebarProps {
  currentPage: PageType
  onPageChange: (page: PageType) => void
  collapsed: boolean
  onToggle: () => void
  /** B4-a：admin 登录时渲染「管理」分组，learner 不渲染 */
  isAdmin?: boolean
}

/* V3.0: 彩色渐变填充图标 */
const icons = {
  dashboard: (
    <svg viewBox="0 0 24 24" fill="none">
      <defs>
        <linearGradient id="icon-blue" x1="0" y1="0" x2="24" y2="24">
          <stop stopColor="#60a5fa" />
          <stop offset="1" stopColor="#2563eb" />
        </linearGradient>
      </defs>
      <rect x="3" y="3" width="7" height="7" rx="2" fill="url(#icon-blue)" opacity="0.9" />
      <rect x="14" y="3" width="7" height="7" rx="2" fill="url(#icon-blue)" opacity="0.7" />
      <rect x="3" y="14" width="7" height="7" rx="2" fill="url(#icon-blue)" opacity="0.7" />
      <rect x="14" y="14" width="7" height="7" rx="2" fill="url(#icon-blue)" opacity="0.5" />
    </svg>
  ),
  profile: (
    <svg viewBox="0 0 24 24" fill="none">
      <defs>
        <linearGradient id="icon-green" x1="0" y1="0" x2="24" y2="24">
          <stop stopColor="#34d399" />
          <stop offset="1" stopColor="#059669" />
        </linearGradient>
      </defs>
      <circle cx="12" cy="8" r="4" fill="url(#icon-green)" opacity="0.9" />
      <path d="M4 20c0-4 4-7 8-7s8 3 8 7" fill="url(#icon-green)" opacity="0.6" />
    </svg>
  ),
  knowledgeGraph: (
    <svg viewBox="0 0 24 24" fill="none">
      <defs>
        <linearGradient id="icon-amber" x1="0" y1="0" x2="24" y2="24">
          <stop stopColor="#fbbf24" />
          <stop offset="1" stopColor="#d97706" />
        </linearGradient>
      </defs>
      <circle cx="12" cy="5" r="3" fill="url(#icon-amber)" opacity="0.9" />
      <circle cx="5" cy="18" r="2.5" fill="url(#icon-amber)" opacity="0.7" />
      <circle cx="19" cy="18" r="2.5" fill="url(#icon-amber)" opacity="0.7" />
      <line x1="12" y1="8" x2="5" y2="15.5" stroke="url(#icon-amber)" strokeWidth="1.5" opacity="0.5" />
      <line x1="12" y1="8" x2="19" y2="15.5" stroke="url(#icon-amber)" strokeWidth="1.5" opacity="0.5" />
      <line x1="5" y1="18" x2="19" y2="18" stroke="url(#icon-amber)" strokeWidth="1" opacity="0.3" />
    </svg>
  ),
  learningPath: (
    <svg viewBox="0 0 24 24" fill="none">
      <defs>
        <linearGradient id="icon-purple" x1="0" y1="0" x2="24" y2="24">
          <stop stopColor="#a78bfa" />
          <stop offset="1" stopColor="#7c3aed" />
        </linearGradient>
      </defs>
      <path d="M3 12h4l3-9l3 18l3-9h4" stroke="url(#icon-purple)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="3" cy="12" r="2" fill="url(#icon-purple)" />
      <circle cx="21" cy="12" r="2" fill="url(#icon-purple)" />
    </svg>
  ),
  workflow: (
    <svg viewBox="0 0 24 24" fill="none">
      <defs>
        <linearGradient id="icon-rose" x1="0" y1="0" x2="24" y2="24">
          <stop stopColor="#fb7185" />
          <stop offset="1" stopColor="#e11d48" />
        </linearGradient>
      </defs>
      <circle cx="6" cy="6" r="3" fill="url(#icon-rose)" opacity="0.9" />
      <circle cx="18" cy="6" r="3" fill="url(#icon-rose)" opacity="0.7" />
      <circle cx="12" cy="18" r="3" fill="url(#icon-rose)" opacity="0.8" />
      <path d="M6 9v3a3 3 0 003 3h6a3 3 0 003-3V9" stroke="url(#icon-rose)" strokeWidth="1.5" opacity="0.4" />
    </svg>
  ),
  resource: (
    <svg viewBox="0 0 24 24" fill="none">
      <defs>
        <linearGradient id="icon-teal" x1="0" y1="0" x2="24" y2="24">
          <stop stopColor="#2dd4bf" />
          <stop offset="1" stopColor="#0d9488" />
        </linearGradient>
      </defs>
      <path d="M4 5a2 2 0 0 1 2-2h7l5 5v11a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V5z" fill="url(#icon-teal)" opacity="0.85" />
      <path d="M13 3v5h5" stroke="#fff" strokeWidth="1.2" opacity="0.7" />
      <line x1="8" y1="12" x2="14" y2="12" stroke="#fff" strokeWidth="1.4" opacity="0.8" strokeLinecap="round" />
      <line x1="8" y1="15.5" x2="13" y2="15.5" stroke="#fff" strokeWidth="1.4" opacity="0.6" strokeLinecap="round" />
    </svg>
  ),
  /* B4-a 管理分组图标：知识库（数据桶）/ Prompt（模板编辑）/ 指标（仪表） */
  adminKb: (
    <svg viewBox="0 0 24 24" fill="none">
      <defs>
        <linearGradient id="icon-cyan" x1="0" y1="0" x2="24" y2="24">
          <stop stopColor="#67e8f9" />
          <stop offset="1" stopColor="#0e7490" />
        </linearGradient>
      </defs>
      <ellipse cx="12" cy="5.5" rx="7" ry="2.8" fill="url(#icon-cyan)" opacity="0.9" />
      <path d="M5 5.5v6c0 1.55 3.13 2.8 7 2.8s7-1.25 7-2.8v-6" fill="url(#icon-cyan)" opacity="0.6" />
      <path d="M5 11.5v6c0 1.55 3.13 2.8 7 2.8s7-1.25 7-2.8v-6" fill="url(#icon-cyan)" opacity="0.35" />
    </svg>
  ),
  adminPrompt: (
    <svg viewBox="0 0 24 24" fill="none">
      <defs>
        <linearGradient id="icon-indigo" x1="0" y1="0" x2="24" y2="24">
          <stop stopColor="#a5b4fc" />
          <stop offset="1" stopColor="#4338ca" />
        </linearGradient>
      </defs>
      <rect x="3" y="4" width="18" height="14" rx="3" fill="url(#icon-indigo)" opacity="0.55" />
      <path d="M7 9l3 2.5L7 14" stroke="#fff" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" opacity="0.9" />
      <line x1="12.5" y1="14" x2="17" y2="14" stroke="#fff" strokeWidth="1.6" strokeLinecap="round" opacity="0.8" />
      <circle cx="18.5" cy="19.5" r="3" fill="url(#icon-indigo)" opacity="0.95" />
      <path d="M17.3 19.5l.9.9 1.5-1.8" stroke="#fff" strokeWidth="1.1" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  adminMetrics: (
    <svg viewBox="0 0 24 24" fill="none">
      <defs>
        <linearGradient id="icon-lime" x1="0" y1="0" x2="24" y2="24">
          <stop stopColor="#bef264" />
          <stop offset="1" stopColor="#4d7c0f" />
        </linearGradient>
      </defs>
      <path d="M4 17a8 8 0 1 1 16 0" stroke="url(#icon-lime)" strokeWidth="2.4" strokeLinecap="round" opacity="0.85" />
      <line x1="12" y1="17" x2="16" y2="11" stroke="url(#icon-lime)" strokeWidth="2" strokeLinecap="round" />
      <circle cx="12" cy="17" r="2" fill="url(#icon-lime)" />
    </svg>
  ),
}

interface MenuItem {
  id: PageType
  icon: JSX.Element
  label: string
  description: string
  seq?: number
  /** 进入该步骤的前置条件（用于软门控提示） */
  requires?: 'hasDiagnosed' | 'hasGeneratedPath'
  beta?: boolean
}

/** 学习主线（有先后依赖，标序号①②③）*/
const mainlineItems: MenuItem[] = [
  { id: 'profile', icon: icons.profile, label: '画像诊断', description: '知识能力评估', seq: 1 },
  { id: 'learning-path', icon: icons.learningPath, label: '学习路径', description: '个性化导航', seq: 2, requires: 'hasDiagnosed' },
  { id: 'learning-resource', icon: icons.resource, label: '学习资源', description: 'AI讲义·测试题', seq: 3, requires: 'hasGeneratedPath' },
]

/** 总览与工具（无先后顺序）*/
const toolItems: MenuItem[] = [
  { id: 'dashboard', icon: icons.dashboard, label: '学情概览', description: '首页 · 学习总览' },
  { id: 'workflow', icon: icons.workflow, label: 'Agent工作流', description: 'AI协同可视化' },
  { id: 'knowledge-graph', icon: icons.knowledgeGraph, label: '知识图谱', description: '可视化拓扑', beta: true },
]

/** 管理（仅 admin 渲染，B4 阶段）*/
const adminItems: MenuItem[] = [
  { id: 'admin-kb', icon: icons.adminKb, label: '知识库管理', description: '文档入库 · 检索测试' },
  { id: 'admin-prompts', icon: icons.adminPrompt, label: 'Prompt管理', description: 'Agent模板热更新' },
  { id: 'admin-metrics', icon: icons.adminMetrics, label: '指标看板', description: '幻觉率 · 适配 · 覆盖' },
]

export default function Sidebar({ currentPage, onPageChange, collapsed, onToggle, isAdmin = false }: SidebarProps) {
  const hasDiagnosed = useJourney((s) => s.hasDiagnosed)
  const hasGeneratedPath = useJourney((s) => s.hasGeneratedPath)
  const resetJourney = useJourney((s) => s.resetJourney)
  const resetMastery = useMastery((s) => s.reset)

  const isLocked = (item: MenuItem) => {
    if (item.requires === 'hasDiagnosed') return !hasDiagnosed
    if (item.requires === 'hasGeneratedPath') return !hasGeneratedPath
    return false
  }

  const renderItem = (item: MenuItem, index: number) => {
    const active = currentPage === item.id
    const locked = isLocked(item)
    return (
      <motion.button
        key={item.id}
        className={`sidebar__nav-item ${active ? 'sidebar__nav-item--active' : ''} ${locked ? 'sidebar__nav-item--locked' : ''}`}
        onClick={() => onPageChange(item.id)}
        title={locked ? '建议先完成前置步骤' : undefined}
        initial={{ opacity: 0, x: -20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ delay: index * 0.06, duration: 0.4 }}
        whileHover={{ x: collapsed ? 0 : 4, transition: { duration: 0.2 } }}
        whileTap={{ scale: 0.98 }}
      >
        <span className="sidebar__nav-icon">{item.icon}</span>
        {!collapsed && (
          <span className="sidebar__nav-content">
            <span className="sidebar__nav-label">
              {item.seq && <span className="sidebar__nav-seq">{item.seq}</span>}
              {item.label}
              {item.beta && <span className="sidebar__beta-tag">Beta</span>}
              {locked && (
                <svg className="sidebar__nav-lock" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="5" y="11" width="14" height="9" rx="2" />
                  <path d="M8 11V8a4 4 0 0 1 8 0v3" />
                </svg>
              )}
            </span>
            <span className="sidebar__nav-desc">{item.description}</span>
          </span>
        )}
        {active && (
          <motion.div
            className="sidebar__nav-indicator"
            layoutId="sidebar-active-indicator"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ type: 'spring', stiffness: 400, damping: 30 }}
          />
        )}
        {active && <div className="sidebar__nav-glow" />}
      </motion.button>
    )
  }

  return (
    <motion.aside
      className={`sidebar ${collapsed ? 'sidebar--collapsed' : ''}`}
      initial={{ x: -20, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      transition={{ duration: 0.4, ease: 'easeOut' }}
    >
      {/* Logo 区域 */}
      <div className="sidebar__header">
        <motion.div
          className="sidebar__logo"
          whileHover={{ scale: 1.02 }}
        >
          <div className="sidebar__logo-icon">
            <svg viewBox="0 0 40 40" fill="none">
              <defs>
                <linearGradient id="logo-grad" x1="0" y1="0" x2="40" y2="40">
                  <stop style={{ stopColor: 'var(--primary)' }} />
                  <stop offset="0.5" style={{ stopColor: 'var(--primary-d)' }} />
                  <stop offset="1" style={{ stopColor: 'var(--accent)' }} />
                </linearGradient>
                <linearGradient id="logo-glow" x1="0" y1="0" x2="40" y2="40">
                  <stop style={{ stopColor: 'var(--primary)', stopOpacity: 0.4 }} />
                  <stop offset="1" style={{ stopColor: 'var(--accent)', stopOpacity: 0.2 }} />
                </linearGradient>
              </defs>
              <circle cx="20" cy="20" r="18" stroke="url(#logo-glow)" strokeWidth="1.5" opacity="0.5" />
              <circle cx="20" cy="20" r="16" stroke="url(#logo-grad)" strokeWidth="2" />
              <circle cx="20" cy="14" r="4" fill="url(#logo-grad)">
                <animate attributeName="opacity" values="1;0.7;1" dur="2s" repeatCount="indefinite" />
              </circle>
              <circle cx="12" cy="26" r="3" fill="url(#logo-grad)" opacity="0.7" />
              <circle cx="28" cy="26" r="3" fill="url(#logo-grad)" opacity="0.7" />
              <line x1="20" y1="18" x2="12" y2="23" stroke="url(#logo-grad)" strokeWidth="1.5" opacity="0.7" />
              <line x1="20" y1="18" x2="28" y2="23" stroke="url(#logo-grad)" strokeWidth="1.5" opacity="0.7" />
              <path d="M12 26 Q20 30 28 26" stroke="url(#logo-grad)" strokeWidth="1" fill="none" opacity="0.4" />
            </svg>
          </div>
          {!collapsed && (
            <motion.div
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              className="sidebar__logo-text"
            >
              <span className="sidebar__logo-title">智学中枢</span>
              <span className="sidebar__logo-subtitle">AI Learning Platform</span>
            </motion.div>
          )}
        </motion.div>

        <button className="sidebar__toggle" onClick={onToggle} aria-label="折叠侧边栏">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            {collapsed ? (
              <path d="M9 18l6-6-6-6" />
            ) : (
              <path d="M15 18l-6-6 6-6" />
            )}
          </svg>
        </button>
      </div>

      {/* 导航区域 */}
      <nav className="sidebar__nav">
        {!collapsed && <p className="sidebar__nav-group-title">学习主线</p>}
        {mainlineItems.map((item, i) => renderItem(item, i))}

        <div className="sidebar__nav-divider" />

        {!collapsed && <p className="sidebar__nav-group-title">总览与工具</p>}
        {toolItems.map((item, i) => renderItem(item, mainlineItems.length + i))}

        {isAdmin && (
          <>
            <div className="sidebar__nav-divider" />
            {!collapsed && <p className="sidebar__nav-group-title">管理</p>}
            {adminItems.map((item, i) => renderItem(item, mainlineItems.length + toolItems.length + i))}
          </>
        )}
      </nav>

      {/* 用户资料区 - 毛玻璃卡片 */}
      {!collapsed && (
        <motion.div
          className="sidebar__user"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5, duration: 0.4 }}
          whileHover={{ y: -2 }}
        >
          <div className="sidebar__user-avatar">
            <span>{isAdmin ? '管' : '学'}</span>
            <div className="sidebar__user-avatar-glow" />
          </div>
          <div className="sidebar__user-info">
            <span className="sidebar__user-name">{getUser()?.displayName ?? '学习者_001'}</span>
            <span className="sidebar__user-level">{isAdmin ? '管理员 · 系统运营' : '中级 · AI领域'}</span>
          </div>
          <motion.svg
            className="sidebar__user-arrow"
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            whileHover={{ x: 2 }}
          >
            <path d="M9 18l6-6-6-6" />
          </motion.svg>
        </motion.div>
      )}

      {/* 演示用：重置闭环进度，回到新用户首屏引导 */}
      {!collapsed && (
        <button className="sidebar__reset" onClick={() => { resetJourney(); resetMastery() }} title="清除进度，回到新用户引导">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M3 12a9 9 0 1 0 9-9 9 9 0 0 0-6.7 3" />
            <path d="M3 3v5h5" />
          </svg>
          重置引导进度
        </button>
      )}
    </motion.aside>
  )
}
