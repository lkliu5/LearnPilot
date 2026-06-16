import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import LearningPathCard from '../components/LearningPathCard'
import PageHeader from '../components/PageHeader'
import { RevealGroup, RevealItem, revealItem } from '../components/Reveal'
import type { PageType } from '../App'
import { lessons } from '../data/learningPath'
import { useJourney } from '../store/journey'
import { useMastery } from '../store/mastery'
import { kpByLessonSeq } from '../data/knowledgePoints'
import { setResourceNav } from '../services/resourceNav'
import './LearningPath.css'

const milestones = [
  { id: 1, title: '机器学习入门', completed: true, date: '2026-05-15' },
  { id: 2, title: '神经网络实践', completed: true, date: '2026-05-20' },
  { id: 3, title: '深度学习进阶', completed: false, date: '预计 2026-06-10' }
]

export default function LearningPath({ onNavigate }: { onNavigate?: (page: PageType) => void }) {
  const [viewMode, setViewMode] = useState<'timeline' | 'cards'>('timeline')
  const [selectedTopic, setSelectedTopic] = useState<string | null>(null)
  const generatePath = useJourney((s) => s.generatePath)
  const masteryStatus = useMastery((s) => s.status)

  /* 课程状态由掌握度派生：通过测试→已完成；学习中/待检验→进行中；否则用种子 */
  const pathData = lessons.map((l) => {
    const kp = kpByLessonSeq(l.sequence)
    const ms = kp ? masteryStatus[kp.id] : undefined
    if (ms === 'passed') return { ...l, status: 'completed' as const, progress: 100 }
    if (ms === 'learning' || ms === 'pending-check')
      return { ...l, status: 'in_progress' as const, progress: l.progress >= 100 ? 55 : l.progress }
    return l
  })

  /* 弹窗按钮 → 资源页：经 resourceNav 通道携带该课程对应 kpId（Lesson.sequence ↔ lessonSeq 映射）。
     开始学习落默认「定制讲义」Tab；查看资源落「资源推荐」Tab，各司其职 */
  const openResource = (topic: string, entryTab?: string) => {
    const lesson = pathData.find((p) => p.topic === topic)
    const kp = lesson ? kpByLessonSeq(lesson.sequence) : undefined
    setResourceNav(kp?.id ?? '', entryTab)
    onNavigate?.('learning-resource')
  }

  /* 当前应学节点：按 sequence 顺序取第一个「未通过测试」的知识点（全部通过则取最后一节）。
     「去学习资源」据此跳转，不再写死第一节——学完一节标已掌握后自动跟进度推进（issue#4）。*/
  const currentKp = (() => {
    const ordered = [...lessons].sort((a, b) => a.sequence - b.sequence)
    for (const l of ordered) {
      const kp = kpByLessonSeq(l.sequence)
      if (kp && masteryStatus[kp.id] !== 'passed') return kp
    }
    const last = ordered[ordered.length - 1]
    return last ? kpByLessonSeq(last.sequence) : undefined
  })()

  const completedCount = pathData.filter(p => p.status === 'completed').length
  const inProgressCount = pathData.filter(p => p.status === 'in_progress').length
  const overallProgress = Math.round(
    pathData.reduce((sum, p) => sum + p.progress, 0) / pathData.length
  )

  return (
    <div className="learning-path-page">
      {/* 统一标题区：锚条 + 高亮 + 状态徽章组 */}
      <PageHeader
        title="个性化学习路径"
        highlight="学习路径"
        subtitle="基于您的学情诊断，为您量身定制的学习路线"
        badges={[
          { label: '已完成', value: completedCount },
          { label: '进行中', value: inProgressCount },
          { label: '总进度', value: `${overallProgress}%` },
        ]}
      />

      {/* View Toggle */}
      <div className="view-toggle">
        <button
          className={`view-toggle__btn ${viewMode === 'timeline' ? 'view-toggle__btn--active' : ''}`}
          onClick={() => setViewMode('timeline')}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="12" y1="2" x2="12" y2="22" />
            <circle cx="12" cy="6" r="3" />
            <circle cx="12" cy="12" r="3" />
            <circle cx="12" cy="18" r="3" />
          </svg>
          时间线视图
        </button>
        <button
          className={`view-toggle__btn ${viewMode === 'cards' ? 'view-toggle__btn--active' : ''}`}
          onClick={() => setViewMode('cards')}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="3" y="3" width="7" height="9" rx="1" />
            <rect x="14" y="3" width="7" height="9" rx="1" />
            <rect x="3" y="14" width="7" height="7" rx="1" />
            <rect x="14" y="14" width="7" height="7" rx="1" />
          </svg>
          卡片视图
        </button>
      </div>

      <div className="learning-path-content">
        <AnimatePresence mode="wait">
          {viewMode === 'timeline' ? (
            <motion.div
              key="timeline"
              className="timeline-view"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              {/* Timeline */}
              <RevealGroup className="timeline">
                {pathData.map((item) => (
                  <motion.div
                    key={item.sequence}
                    className={`timeline-item timeline-item--${item.status}`}
                    variants={revealItem}
                    onClick={() => setSelectedTopic(item.topic)}
                  >
                    <div className="timeline-item__marker">
                      {item.status === 'completed' ? (
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                          <polyline points="20 6 9 17 4 12" />
                        </svg>
                      ) : item.status === 'in_progress' ? (
                        <motion.div
                          className="timeline-item__pulse"
                          animate={{ scale: [1, 1.2, 1] }}
                          transition={{ duration: 1.5, repeat: Infinity }}
                        />
                      ) : (
                        <span>{item.sequence}</span>
                      )}
                    </div>
                    <div className="timeline-item__content">
                      <div className="timeline-item__header">
                        <h3 className="timeline-item__title">{item.topic}</h3>
                        <span className={`difficulty-badge difficulty-badge--${
                          item.difficulty === '入门' ? 'beginner' :
                          item.difficulty === '初级' ? 'elementary' :
                          item.difficulty === '中级' ? 'intermediate' :
                          item.difficulty === '高级' ? 'advanced' : 'expert'
                        }`}>
                          {item.difficulty}
                        </span>
                      </div>
                      <p className="timeline-item__desc">{item.description}</p>
                      {item.status === 'in_progress' && (
                        <div className="timeline-item__progress">
                          <div className="progress-bar">
                            <motion.div
                              className="progress-bar__fill"
                              initial={{ width: 0 }}
                              animate={{ width: `${item.progress}%` }}
                              transition={{ duration: 0.8, delay: 0.5 }}
                            />
                          </div>
                          <span className="progress-text">{item.progress}%</span>
                        </div>
                      )}
                      <span className={`status-badge status-badge--${item.status}`}>
                        {item.status === 'completed' ? '已完成' : item.status === 'in_progress' ? '进行中' : '待学习'}
                      </span>
                    </div>
                  </motion.div>
                ))}
              </RevealGroup>

              {/* Milestones Sidebar */}
              <div className="milestones-panel">
                <h3>学习里程碑</h3>
                <div className="milestones-list">
                  {milestones.map((milestone, index) => (
                    <motion.div
                      key={milestone.id}
                      className={`milestone ${milestone.completed ? 'milestone--completed' : ''}`}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: index * 0.15 }}
                    >
                      <div className="milestone__icon">
                        {milestone.completed ? (
                          <svg viewBox="0 0 24 24" fill="currentColor">
                            <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z" />
                          </svg>
                        ) : (
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <circle cx="12" cy="12" r="10" />
                            <path d="M12 6v6l4 2" />
                          </svg>
                        )}
                      </div>
                      <div className="milestone__info">
                        <span className="milestone__title">{milestone.title}</span>
                        <span className="milestone__date">{milestone.date}</span>
                      </div>
                    </motion.div>
                  ))}
                </div>
              </div>
            </motion.div>
          ) : (
            <motion.div
              key="cards"
              className="cards-view"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              <RevealGroup className="cards-grid">
                {pathData.map((item) => (
                  <RevealItem key={item.sequence}>
                    <LearningPathCard
                      sequence={item.sequence}
                      topic={item.topic}
                      difficulty={item.difficulty}
                      status={item.status}
                      progress={item.progress}
                    />
                  </RevealItem>
                ))}
              </RevealGroup>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* 主线衔接：路径已就绪 → 进入 ③ 学习资源 */}
      <div className="flow-next">
        <div className="flow-next__text">
          <span className="flow-next__step">下一步 · ③ 学习资源</span>
          <span className="flow-next__desc">
            {currentKp ? `进入「${currentKp.name}」获取 AI 讲义与练习` : '进入当前进度节点获取 AI 讲义与练习'}
          </span>
        </div>
        <button
          className="flow-next__btn"
          type="button"
          onClick={() => {
            generatePath()
            setResourceNav(currentKp?.id ?? '')
            onNavigate?.('learning-resource')
          }}
        >
          去学习资源 →
        </button>
      </div>

      {/* Topic Detail Modal */}
      <AnimatePresence>
        {selectedTopic && (
          <motion.div
            className="topic-modal-overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setSelectedTopic(null)}
          >
            <motion.div
              className="topic-modal"
              initial={{ opacity: 0, scale: 0.9, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.9, y: 20 }}
              onClick={e => e.stopPropagation()}
            >
              <button className="topic-modal__close" onClick={() => setSelectedTopic(null)}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
              <h2>{selectedTopic}</h2>
              <p>{pathData.find(p => p.topic === selectedTopic)?.description}</p>
              <div className="topic-modal__actions">
                <button
                  className="topic-modal__btn topic-modal__btn--primary"
                  onClick={() => openResource(selectedTopic)}
                >
                  开始学习
                </button>
                <button
                  className="topic-modal__btn topic-modal__btn--secondary"
                  onClick={() => openResource(selectedTopic, 'external')}
                >
                  查看资源
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}