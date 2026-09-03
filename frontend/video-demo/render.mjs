import { bundle } from '@remotion/bundler'
import { renderMedia, selectComposition } from '@remotion/renderer'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const scenes = JSON.parse(readFileSync(path.join(here, 'generated-scenes.json'), 'utf8'))
const inputProps = { scenes }
const browserExecutable = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
const output = path.join(here, '智学中枢-6分钟演示-女声字幕.mp4')

const start = Date.now()
const serveUrl = await bundle({
  entryPoint: path.join(here, 'index.ts'),
  publicDir: path.join(here, 'public'),
})
console.log(`[render] bundle ${((Date.now() - start) / 1000).toFixed(1)}s`)

const composition = await selectComposition({
  serveUrl,
  id: 'ZhixueDemo',
  inputProps,
  browserExecutable,
})
console.log(
  `[render] ${composition.width}x${composition.height} ${composition.durationInFrames / composition.fps}s`,
)

await renderMedia({
  composition,
  serveUrl,
  codec: 'h264',
  audioCodec: 'aac',
  inputProps,
  browserExecutable,
  outputLocation: output,
  crf: 20,
  concurrency: 4,
})
console.log(`[render] 完成 ${((Date.now() - start) / 1000).toFixed(1)}s -> ${output}`)

