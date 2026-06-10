import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import Sidebar from './components/Sidebar'
import Dashboard from './pages/Dashboard'
import ProfileBuilder from './pages/ProfileBuilder'
import LearningPath from './pages/LearningPath'
import AgentWorkflow from './pages/AgentWorkflow'
import LearningResource from './pages/LearningResource'
import KnowledgeGraph from './pages/KnowledgeGraph'
import Login from './pages/Login'
import Landing from './pages/Landing'
import './styles/App.css'

export type PageType = 'dashboard' | 'profile' | 'learning-path' | 'learning-resource' | 'workflow' | 'knowledge-graph'
type Stage = 'landing' | 'login' | 'app'

function App() {
  const [stage, setStage] = useState<Stage>('landing')
  const [currentPage, setCurrentPage] = useState<PageType>('dashboard')
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)

  const renderPage = () => {
    switch (currentPage) {
      case 'dashboard':
        return <Dashboard onNavigate={setCurrentPage} />
      case 'profile':
        return <ProfileBuilder onNavigate={setCurrentPage} />
      case 'learning-path':
        return <LearningPath onNavigate={setCurrentPage} />
      case 'learning-resource':
        return <LearningResource onNavigate={setCurrentPage} />
      case 'workflow':
        return <AgentWorkflow />
      case 'knowledge-graph':
        return <KnowledgeGraph />
      default:
        return <Dashboard onNavigate={setCurrentPage} />
    }
  }

  if (stage === 'landing') {
    return <Landing onEnter={() => setStage('login')} />
  }

  if (stage === 'login') {
    return (
      <AnimatePresence mode="wait">
        <Login key="login" onLogin={() => setStage('app')} />
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
        onPageChange={setCurrentPage}
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
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