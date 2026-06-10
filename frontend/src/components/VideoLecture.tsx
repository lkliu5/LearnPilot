import { useEffect, useRef, useState, useCallback } from 'react'
import { Player, type PlayerRef } from '@remotion/player'
import {
  LectureVideo,
  NARRATION,
  VIDEO_FPS,
  VIDEO_W,
  VIDEO_H,
  VIDEO_DURATION,
} from '../remotion/LectureVideo'

/* 由当前帧定位旁白段落索引 */
const segIndexAt = (frame: number) => {
  let idx = 0
  for (let i = 0; i < NARRATION.length; i++) if (frame >= NARRATION[i].from) idx = i
  return idx
}

export default function VideoLecture() {
  const playerRef = useRef<PlayerRef>(null)
  const [seg, setSeg] = useState(0)
  const [narration, setNarration] = useState(true)
  const spokenRef = useRef<number>(-1)

  const speak = useCallback((text: string) => {
    if (!('speechSynthesis' in window)) return
    window.speechSynthesis.cancel()
    const u = new SpeechSynthesisUtterance(text)
    u.lang = 'zh-CN'
    u.rate = 1.05
    window.speechSynthesis.speak(u)
  }, [])

  useEffect(() => {
    const p = playerRef.current
    if (!p) return
    const onFrame = (e: { detail: { frame: number } }) => {
      const idx = segIndexAt(e.detail.frame)
      setSeg(idx)
    }
    const onPause = () => window.speechSynthesis?.cancel()
    p.addEventListener('frameupdate', onFrame)
    p.addEventListener('pause', onPause)
    p.addEventListener('ended', onPause)
    return () => {
      p.removeEventListener('frameupdate', onFrame)
      p.removeEventListener('pause', onPause)
      p.removeEventListener('ended', onPause)
      window.speechSynthesis?.cancel()
    }
  }, [])

  // 进入新场景时朗读对应旁白（仅播放中 + 旁白开启）
  useEffect(() => {
    const p = playerRef.current
    if (!narration || !p || !p.isPlaying()) return
    if (spokenRef.current !== seg) {
      spokenRef.current = seg
      speak(NARRATION[seg].text)
    }
  }, [seg, narration, speak])

  return (
    <div className="video-lecture">
      <div className="video-lecture__player">
        <Player
          ref={playerRef}
          component={LectureVideo}
          durationInFrames={VIDEO_DURATION}
          fps={VIDEO_FPS}
          compositionWidth={VIDEO_W}
          compositionHeight={VIDEO_H}
          controls
          style={{ width: '100%', borderRadius: 16, overflow: 'hidden', boxShadow: 'var(--shadow-glass)' }}
        />
        {/* 字幕 */}
        <div className="video-lecture__caption">{NARRATION[seg].text}</div>
      </div>

      {/* 旁白脚本 + TTS 控制 */}
      <div className="video-lecture__side">
        <div className="video-lecture__side-head">
          <span>🎙️ AI 旁白脚本</span>
          <label className="video-lecture__toggle">
            <input type="checkbox" checked={narration} onChange={(e) => {
              setNarration(e.target.checked)
              if (!e.target.checked) window.speechSynthesis?.cancel()
            }} />
            语音朗读
          </label>
        </div>
        <ol className="video-lecture__script">
          {NARRATION.map((n, i) => (
            <li
              key={i}
              className={`video-lecture__line ${i === seg ? 'video-lecture__line--active' : ''}`}
              onClick={() => playerRef.current?.seekTo(n.from)}
            >
              <span className="video-lecture__ts">{String(Math.floor(n.from / VIDEO_FPS)).padStart(2, '0')}s</span>
              {n.text}
            </li>
          ))}
        </ol>
        <p className="video-lecture__note">
          视频由 Remotion（React 代码渲染）生成；旁白用浏览器语音合成演示，生产环境可接 TTS 服务并服务端渲染导出 MP4。
        </p>
      </div>
    </div>
  )
}
