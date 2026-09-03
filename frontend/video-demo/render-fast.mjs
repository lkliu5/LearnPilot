import { bundle } from '@remotion/bundler'
import { renderStill, selectComposition } from '@remotion/renderer'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawnSync } from 'node:child_process'

const here = path.dirname(fileURLToPath(import.meta.url))
const publicDir = path.join(here, 'public')
const workDir = path.join(here, '.render-fast')
const stillDir = path.join(workDir, 'stills')
const clipDir = path.join(workDir, 'clips')
mkdirSync(stillDir, { recursive: true })
mkdirSync(clipDir, { recursive: true })

const scenes = JSON.parse(readFileSync(path.join(here, 'generated-scenes.json'), 'utf8'))
const browserExecutable = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
const ffmpeg = path.resolve(
  here,
  '..',
  'node_modules',
  '@remotion',
  'compositor-win32-x64-msvc',
  'ffmpeg.exe',
)
const output = path.join(here, '智学中枢-6分钟演示-女声字幕.mp4')

const splitCaption = (text) => {
  const sentences = text
    .split(/(?<=[。！？；])/)
    .map((s) => s.trim())
    .filter(Boolean)
  const chunks = []
  for (const sentence of sentences) {
    if (sentence.length <= 30) {
      chunks.push(sentence)
      continue
    }
    const parts = sentence.split(/(?<=[，、：])/)
    let line = ''
    for (const part of parts) {
      if (line && line.length + part.length > 30) {
        chunks.push(line)
        line = part
      } else {
        line += part
      }
    }
    if (line) chunks.push(line)
  }
  return chunks.length ? chunks : [text]
}

const startTime = Date.now()
const serveUrl = await bundle({
  entryPoint: path.join(here, 'index.ts'),
  publicDir,
})
console.log(`[fast] bundle ${((Date.now() - startTime) / 1000).toFixed(1)}s`)

const clipPaths = []
let clipIndex = 0
for (let sceneIndex = 0; sceneIndex < scenes.length; sceneIndex += 1) {
  const scene = scenes[sceneIndex]
  const captions = splitCaption(scene.narration)
  const sceneDuration = scene.durationInFrames / 30
  const audioDuration = scene.audioSeconds
  for (let captionIndex = 0; captionIndex < captions.length; captionIndex += 1) {
    clipIndex += 1
    const key = String(clipIndex).padStart(3, '0')
    const clipDuration = sceneDuration / captions.length
    const audioStart = (audioDuration * captionIndex) / captions.length
    const audioEnd = (audioDuration * (captionIndex + 1)) / captions.length
    const localFrame = Math.min(
      scene.durationInFrames - 1,
      Math.max(0, Math.round(((captionIndex + 0.5) / captions.length) * scene.durationInFrames)),
    )
    const oneScene = { ...scene, durationInFrames: scene.durationInFrames }
    const inputProps = { scenes: [oneScene] }
    const composition = await selectComposition({
      serveUrl,
      id: 'ZhixueDemo',
      inputProps,
      browserExecutable,
    })
    const stillPath = path.join(stillDir, `${key}.png`)
    await renderStill({
      composition,
      serveUrl,
      inputProps,
      browserExecutable,
      output: stillPath,
      frame: localFrame,
      imageFormat: 'png',
    })

    const audioPath = path.join(publicDir, scene.audio)
    const clipPath = path.join(clipDir, `${key}.mp4`)
    const ff = spawnSync(
      ffmpeg,
      [
        '-y',
        '-hide_banner',
        '-loglevel',
        'error',
        '-loop',
        '1',
        '-framerate',
        '30',
        '-i',
        stillPath,
        '-i',
        audioPath,
        '-filter_complex',
        `[1:a]atrim=start=${audioStart.toFixed(4)}:end=${audioEnd.toFixed(4)},asetpts=PTS-STARTPTS,apad=pad_dur=1[a]`,
        '-map',
        '0:v:0',
        '-map',
        '[a]',
        '-t',
        clipDuration.toFixed(4),
        '-c:v',
        'libx264',
        '-preset',
        'veryfast',
        '-crf',
        '20',
        '-pix_fmt',
        'yuv420p',
        '-r',
        '30',
        '-c:a',
        'aac',
        '-ar',
        '48000',
        '-ac',
        '2',
        '-movflags',
        '+faststart',
        clipPath,
      ],
      { encoding: 'utf8' },
    )
    if (ff.status !== 0) throw new Error(`FFmpeg clip ${key} 失败：${ff.stderr}`)
    clipPaths.push(clipPath)
    console.log(
      `[fast] ${key} 场景 ${sceneIndex + 1}/${scenes.length} 字幕 ${captionIndex + 1}/${captions.length}`,
    )
  }
}

const concatPath = path.join(workDir, 'concat.txt')
writeFileSync(
  concatPath,
  clipPaths.map((p) => `file '${p.replaceAll('\\', '/').replaceAll("'", "'\\''")}'`).join('\n'),
  'utf8',
)
const concat = spawnSync(
  ffmpeg,
  [
    '-y',
    '-hide_banner',
    '-loglevel',
    'error',
    '-f',
    'concat',
    '-safe',
    '0',
    '-i',
    concatPath,
    '-c',
    'copy',
    '-movflags',
    '+faststart',
    output,
  ],
  { encoding: 'utf8' },
)
if (concat.status !== 0) throw new Error(`FFmpeg concat 失败：${concat.stderr}`)
console.log(`[fast] 完成 ${((Date.now() - startTime) / 1000).toFixed(1)}s -> ${output}`)

