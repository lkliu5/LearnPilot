import { useEffect, useMemo, useRef, useState, useCallback } from 'react'
import { Player, type PlayerRef } from '@remotion/player'
import {
  LectureVideo,
  DEFAULT_SCENES,
  DEFAULT_TITLE,
  SCENE_FRAMES,
  VIDEO_FPS,
  VIDEO_W,
  VIDEO_H,
  type LectureScene,
} from '../remotion/LectureVideo'
import { USE_REAL_API } from '../services/api'
import { getVideo, type VideoNarrationLine } from '../services/resource'
import { getResourceKpId } from '../services/resourceNav'
import { ttsSpeak, ttsStop } from '../services/tts'
import './VideoLecture.css'

/* 由当前帧定位旁白段落索引 */
const segIndexAt = (frame: number, script: VideoNarrationLine[]) => {
  let idx = 0
  for (let i = 0; i < script.length; i++) if (frame >= script[i].from) idx = i
  return idx
}

/**
 * Remotion 讲解视频播放器（分镜脚本 → 参数化模板渲染 + 同步旁白/字幕）。
 *
 * 两种用法：
 * - 非受控（默认，主资源页讲解视频卡）：联调按当前知识点自取 8.3 分镜脚本，mock/失败回落默认；
 * - 受控（导学对话·按需生成视频）：外部直接传入已生成的 title/scenes，跳过自取，复用同一播放逻辑。
 */
export default function VideoLecture({
  title: propTitle,
  scenes: propScenes,
}: { title?: string; scenes?: LectureScene[] } = {}) {
  const playerRef = useRef<PlayerRef>(null)
  const [seg, setSeg] = useState(0)
  const [narration, setNarration] = useState(true)
  const spokenRef = useRef<number>(-1)

  /* 受控：外部已提供分镜脚本（如导学对话按需生成），直接渲染、不再自取。 */
  const controlled = !!propScenes?.length

  /* B7-b 联调 + 动态分镜：非受控时分镜脚本（标题/要点/旁白）改吃 8.3 POST /resource/video，
     画面与旁白随当前知识点动态生成；mock 模式 / 请求失败保持本地默认脚本（兜底占位），
     朗读与点击 seek 行为不变 */
  const [fetchedScenes, setFetchedScenes] = useState<LectureScene[]>(DEFAULT_SCENES)
  const [fetchedTitle, setFetchedTitle] = useState<string>(DEFAULT_TITLE)
  useEffect(() => {
    if (controlled || !USE_REAL_API) return
    // 难度固定「初级」：与讲义默认档一致
    getVideo(getResourceKpId(), '初级')
      .then((d) => {
        if (d.scenes?.length) {
          setFetchedScenes(d.scenes.map((s) => ({ title: s.title, points: s.points, narration: s.narration })))
          setFetchedTitle(d.title || DEFAULT_TITLE)
        }
      })
      .catch((e) => console.error('[video] 加载分镜脚本失败，使用本地默认脚本', e))
  }, [controlled])

  const scenes = controlled ? propScenes! : fetchedScenes
  const title = controlled ? propTitle || DEFAULT_TITLE : fetchedTitle

  /* 旁白脚本（侧栏字幕 + TTS）由分镜场景派生：场景 i 起始帧 = i × SCENE_FRAMES */
  const script = useMemo<VideoNarrationLine[]>(
    () => scenes.map((s, i) => ({ from: i * SCENE_FRAMES, text: s.narration })),
    [scenes]
  )
  const scriptRef = useRef(script)
  scriptRef.current = script
  const durationInFrames = scenes.length * SCENE_FRAMES

  /* 发声引擎：后端 edge-tts 自然语音（§8.9），失败/降级自动回落浏览器语音；
     时序/字幕/逐句同步逻辑不变——只换"发声引擎"。 */
  const speak = useCallback((text: string) => {
    void ttsSpeak(text)
  }, [])

  useEffect(() => {
    const p = playerRef.current
    if (!p) return
    const onFrame = (e: { detail: { frame: number } }) => {
      const idx = segIndexAt(e.detail.frame, scriptRef.current)
      setSeg(idx)
    }
    const onPause = () => ttsStop()
    p.addEventListener('frameupdate', onFrame)
    p.addEventListener('pause', onPause)
    p.addEventListener('ended', onPause)
    return () => {
      p.removeEventListener('frameupdate', onFrame)
      p.removeEventListener('pause', onPause)
      p.removeEventListener('ended', onPause)
      ttsStop() // 卸载/切换时停掉当前音频，避免串音
    }
  }, [])

  /* 当前旁白段（脚本切换瞬间防越界兜底） */
  const curLine = script[seg] ?? script[script.length - 1]

  // 进入新场景时朗读对应旁白（仅播放中 + 旁白开启）
  useEffect(() => {
    const p = playerRef.current
    if (!narration || !p || !p.isPlaying()) return
    if (spokenRef.current !== seg) {
      spokenRef.current = seg
      speak(curLine.text)
    }
  }, [seg, narration, speak, curLine])

  return (
    <div className="video-lecture">
      <div className="video-lecture__player">
        <Player
          ref={playerRef}
          component={LectureVideo}
          inputProps={{ title, scenes }}
          durationInFrames={durationInFrames}
          fps={VIDEO_FPS}
          compositionWidth={VIDEO_W}
          compositionHeight={VIDEO_H}
          controls
          style={{ width: '100%', borderRadius: 16, overflow: 'hidden', boxShadow: 'var(--shadow-glass)' }}
        />
        {/* 字幕 */}
        <div className="video-lecture__caption">{curLine.text}</div>
      </div>

      {/* 旁白脚本 + TTS 控制 */}
      <div className="video-lecture__side">
        <div className="video-lecture__side-head">
          <span>🎙️ AI 旁白脚本</span>
          <label className="video-lecture__toggle">
            <input type="checkbox" checked={narration} onChange={(e) => {
              setNarration(e.target.checked)
              if (!e.target.checked) ttsStop()
            }} />
            语音朗读
          </label>
        </div>
        <ol className="video-lecture__script">
          {script.map((n, i) => (
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
          视频由 Remotion（React 代码渲染）生成；旁白接入后端 edge-tts 自然语音（失败自动回落浏览器语音），生产环境可服务端渲染导出 MP4。
        </p>
      </div>
    </div>
  )
}
