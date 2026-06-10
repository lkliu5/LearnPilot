import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import Silk from '@/components/Silk/Silk'
import './Login.css'

interface LoginProps {
  onLogin: () => void
}

/* 绸缎背景的两套护眼配色：鼠尾草 → 低饱和鼠尾绿；墨纸 → 低饱和靛蓝灰 */
const SILK_COLORS = {
  sage: '#9FB3A6',
  ink: '#9DB1BC',
} as const

/** 观察 documentElement 的 data-theme，登录页随全局护眼主题实时联动 */
function useThemeName(): keyof typeof SILK_COLORS {
  const read = (): keyof typeof SILK_COLORS =>
    typeof document !== 'undefined' &&
    document.documentElement.getAttribute('data-theme') === 'ink'
      ? 'ink'
      : 'sage'

  const [theme, setTheme] = useState<keyof typeof SILK_COLORS>(read)

  useEffect(() => {
    const el = document.documentElement
    const obs = new MutationObserver(() => setTheme(read()))
    obs.observe(el, { attributes: true, attributeFilter: ['data-theme'] })
    return () => obs.disconnect()
  }, [])

  return theme
}

const features = [
  { icon: '◆', text: '多智能体协同 · 学情诊断' },
  { icon: '◇', text: 'RAG 检索增强 · 抑制幻觉' },
  { icon: '◈', text: '个性化学习路径动态规划' },
]

export default function Login({ onLogin }: LoginProps) {
  const [username, setUsername] = useState('学习者_001')
  const [password, setPassword] = useState('••••••••')
  const [loading, setLoading] = useState(false)
  const theme = useThemeName()

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (loading) return
    setLoading(true)
    // 模拟鉴权（前端演示），1s 后进入系统
    setTimeout(onLogin, 1000)
  }

  return (
    <div className="login">
      {/* 背景：Silk 丝绸波纹（WebGL）+ 暗化遮罩 */}
      <div className="login__bg">
        <div className="login__silk">
          <Silk speed={8} scale={1.1} color={SILK_COLORS[theme]} noiseIntensity={0.9} rotation={0.15} />
        </div>
        <div className="login__silk-scrim" />
      </div>

      <motion.div
        className="login__panel"
        initial={{ opacity: 0, y: 24, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.6, ease: [0.25, 0.8, 0.25, 1] }}
      >
        {/* 左：品牌展示（talizen 风）*/}
        <div className="login__brand">
          {/* 背景巨字虚影 */}
          <span className="login__ghost" aria-hidden="true">AI</span>

          <motion.div
            className="login__eyebrow"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.15 }}
          >
            <span className="login__brand-dot" />
            智学中枢 · 智能学习中枢
          </motion.div>

          <motion.div
            className="login__logo"
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.2, duration: 0.5 }}
          >
            <svg viewBox="0 0 40 40" fill="none">
              <defs>
                <linearGradient id="login-logo-grad" x1="0" y1="0" x2="40" y2="40">
                  <stop style={{ stopColor: 'var(--primary)' }} />
                  <stop offset="0.5" style={{ stopColor: 'var(--primary-d)' }} />
                  <stop offset="1" style={{ stopColor: 'var(--accent)' }} />
                </linearGradient>
              </defs>
              <circle cx="20" cy="20" r="18" stroke="url(#login-logo-grad)" strokeWidth="1.5" opacity="0.5" />
              <circle cx="20" cy="20" r="16" stroke="url(#login-logo-grad)" strokeWidth="2" />
              <circle cx="20" cy="14" r="4" fill="url(#login-logo-grad)">
                <animate attributeName="opacity" values="1;0.6;1" dur="2s" repeatCount="indefinite" />
              </circle>
              <circle cx="12" cy="26" r="3" fill="url(#login-logo-grad)" opacity="0.7" />
              <circle cx="28" cy="26" r="3" fill="url(#login-logo-grad)" opacity="0.7" />
              <line x1="20" y1="18" x2="12" y2="23" stroke="url(#login-logo-grad)" strokeWidth="1.5" opacity="0.7" />
              <line x1="20" y1="18" x2="28" y2="23" stroke="url(#login-logo-grad)" strokeWidth="1.5" opacity="0.7" />
              <path d="M12 26 Q20 30 28 26" stroke="url(#login-logo-grad)" strokeWidth="1" fill="none" opacity="0.4" />
            </svg>
          </motion.div>

          {/* talizen 签名：选择性渐变大标题 */}
          <motion.h1
            className="login__title"
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.32, duration: 0.6, ease: [0.25, 0.8, 0.25, 1] }}
          >
            诊断<span className="grad">学情</span>。<br />
            生成<span className="grad">每一课</span>。
          </motion.h1>
          <motion.p
            className="login__subtitle"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.6 }}
          >
            AI Learning Operating System
          </motion.p>

          <motion.ul
            className="login__features"
            initial="hidden"
            animate="visible"
            variants={{ visible: { transition: { staggerChildren: 0.12, delayChildren: 0.8 } } }}
          >
            {features.map((f) => (
              <motion.li
                key={f.text}
                variants={{ hidden: { opacity: 0, x: -12 }, visible: { opacity: 1, x: 0 } }}
              >
                <span className="login__feature-icon">{f.icon}</span>
                {f.text}
              </motion.li>
            ))}
          </motion.ul>
        </div>

        {/* 右：登录表单 */}
        <motion.div
          className="login__form-wrap"
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.4, duration: 0.5 }}
        >
          <h2 className="login__form-title">欢迎回来</h2>
          <p className="login__form-hint">登录以进入你的个性化学习空间</p>

          <form className="login__form" onSubmit={handleSubmit}>
            <label className="login__field">
              <span className="login__field-label">用户名</span>
              <input
                className="login__input"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
              />
            </label>

            <label className="login__field">
              <span className="login__field-label">密码</span>
              <input
                className="login__input"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
              />
            </label>

            <div className="login__row">
              <label className="login__remember">
                <input type="checkbox" defaultChecked /> 记住我
              </label>
              <a className="login__forgot" href="#">忘记密码？</a>
            </div>

            <button className={`login__submit ${loading ? 'login__submit--loading' : ''}`} type="submit">
              {loading ? '正在进入…' : '进入系统'}
            </button>

            <p className="login__demo-tip">演示模式 · 任意账号密码均可进入</p>
          </form>
        </motion.div>
      </motion.div>

      <motion.p
        className="login__copyright"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1.1 }}
      >
        软件杯 · 领域知识个性化资源生成和多智能体系统
      </motion.p>
    </div>
  )
}
