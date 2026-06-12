import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import Sidebar from './components/Sidebar'
import Dashboard from './pages/Dashboard'
import ProfileBuilder from './pages/ProfileBuilder'
import LearningPath from './pages/LearningPath'
import AgentWorkflow from './pages/AgentWorkflow'
import LearningResource from './pages/LearningResource'
import KnowledgeGraph from './pages/KnowledgeGraph'
import AdminKB from './pages/admin/AdminKB'
import AdminPrompts from './pages/admin/AdminPrompts'
import AdminMetrics from './pages/admin/AdminMetrics'
import AdminUsers from './pages/admin/AdminUsers'
import Login from './pages/Login'
import Landing from './pages/Landing'
import { getUser } from './services/api'
import './styles/App.css'

export type PageType =
  | 'dashboard'
  | 'profile'
  | 'learning-path'
  | 'learning-resource'
  | 'workflow'
  | 'knowledge-graph'
  | 'admin-kb'
  | 'admin-prompts'
  | 'admin-metrics'
  | 'admin-users'
type Stage = 'landing' | 'login' | 'app'

/** B4-a 管理端：hash 深链 ↔ 页面映射（learner 直接敲 URL 时由守卫拦回首页） */
const ADMIN_HASH_TO_PAGE: Record<string, PageType> = {
  '#/admin/kb': 'admin-kb',
  '#/admin/prompts': 'admin-prompts',
  '#/admin/metrics': 'admin-metrics',
  '#/admin/users': 'admin-users',
}
const ADMIN_PAGE_TO_HASH: Partial<Record<PageType, string>> = {
  'admin-kb': '#/admin/kb',
  'admin-prompts': '#/admin/prompts',
  'admin-metrics': '#/admin/metrics',
  'admin-users': '#/admin/users',
}
const isAdminPage = (page: PageType) => page.startsWith('admin-')

function App() {
  const [stage, setStage] = useState<Stage>('landing')
  const [currentPage, setCurrentPage] = useState<PageType>('dashboard')
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  /** 登录响应 role（15.1）：admin 进管理端视图；mock 模式无登录态时按 learner 处理 */
  const [role, setRole] = useState<'learner' | 'admin'>('learner')
  const isAdmin = role === 'admin'

  /** 统一导航入口：非 admin 访问管理页一律拦回首页；管理页同步 hash 深链 */
  const navigate = (page: PageType) => {
    const target = isAdminPage(page) && !isAdmin ? 'dashboard' : page
    setCurrentPage(target)
    const hash = ADMIN_PAGE_TO_HASH[target]
    if (hash) {
      if (window.location.hash !== hash) window.location.hash = hash
    } else if (ADMIN_HASH_TO_PAGE[window.location.hash]) {
      // 离开管理页时清掉管理 hash，不触碰 learner 侧既有 URL 行为
      history.replaceState(null, '', window.location.pathname + window.location.search)
    }
  }

  /** 管理路由守卫：进入应用后监听 #/admin/* 直敲与变更，learner 拦截回首页 */
  useEffect(() => {
    if (stage !== 'app') return
    const applyHash = () => {
      const target = ADMIN_HASH_TO_PAGE[window.location.hash]
      if (!target) return
      if (isAdmin) {
        setCurrentPage(target)
      } else {
        history.replaceState(null, '', window.location.pathname + window.location.search)
        setCurrentPage('dashboard')
      }
    }
    applyHash()
    window.addEventListener('hashchange', applyHash)
    return () => window.removeEventListener('hashchange', applyHash)
  }, [stage, isAdmin])

  /** 登录/注册成功回调。注册新学习者时 toProfile=true → 直接进入画像诊断引导（B9）。 */
  const handleLogin = (opts?: { toProfile?: boolean }) => {
    const user = getUser()
    const nextRole = user?.role === 'admin' ? 'admin' : 'learner'
    setRole(nextRole)
    if (nextRole === 'admin') setCurrentPage('admin-kb')
    else setCurrentPage(opts?.toProfile ? 'profile' : 'dashboard')
    setStage('app')
  }

  const renderPage = () => {
    // 双保险：即使状态被直接置为管理页，learner 也渲染首页
    if (isAdminPage(currentPage) && !isAdmin) return <Dashboard onNavigate={navigate} />
    switch (currentPage) {
      case 'dashboard':
        return <Dashboard onNavigate={navigate} />
      case 'profile':
        return <ProfileBuilder onNavigate={navigate} />
      case 'learning-path':
        return <LearningPath onNavigate={navigate} />
      case 'learning-resource':
        return <LearningResource onNavigate={navigate} />
      case 'workflow':
        return <AgentWorkflow />
      case 'knowledge-graph':
        return <KnowledgeGraph onNavigate={navigate} />
      case 'admin-kb':
        return <AdminKB />
      case 'admin-prompts':
        return <AdminPrompts />
      case 'admin-metrics':
        return <AdminMetrics />
      case 'admin-users':
        return <AdminUsers />
      default:
        return <Dashboard onNavigate={navigate} />
    }
  }

  if (stage === 'landing') {
    return <Landing onEnter={() => setStage('login')} />
  }

  if (stage === 'login') {
    return (
      <AnimatePresence mode="wait">
        <Login key="login" onLogin={handleLogin} />
      </AnimatePresence>
    )
  }

  return (
    <div className="app">
      {/* Background Pattern */}
      <div className="app__background">
        <div className="app__gradient-orb app__gradient-orb--1" />
        <div className="app__gradient-orb app__gradient-orb--2" />
        <div className="app__gradient-orb app__gradient-orb--3" />
      </div>

      {/* Sidebar */}
      <Sidebar
        currentPage={currentPage}
        onPageChange={navigate}
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
        isAdmin={isAdmin}
      />

      {/* Main Content */}
      <main className={`app__main ${sidebarCollapsed ? 'app__main--expanded' : ''}`}>
        <AnimatePresence mode="wait">
          <motion.div
            key={currentPage}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            transition={{ duration: 0.3, ease: 'easeInOut' }}
            className="app__content"
          >
            {renderPage()}
          </motion.div>
        </AnimatePresence>
      </main>
    </div>
  )
}

export default App
