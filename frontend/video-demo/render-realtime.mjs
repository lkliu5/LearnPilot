import {spawn} from "node:child_process";
import {readdir, readFile, writeFile, mkdir} from "node:fs/promises";
import path from "node:path";
import {fileURLToPath} from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const sourceRoot = path.join(here, "realtime-2k");
const workRoot = path.join(here, "realtime-render");
const output = path.join(here, "智学中枢-2K实机操作演示-无配音.mp4");
const ffmpeg = path.join(
  here,
  "..",
  "node_modules",
  "@remotion",
  "compositor-win32-x64-msvc",
  "ffmpeg.exe",
);

const orderedSegments = [
  "01-home",
  "02-profile",
  "03-path",
  "04-resources-trust",
  "05-learning-methods",
  "06-instant-tutor",
  "06b-tutor-resources",
  "07-documents",
  "08-library",
  "09-agent-workflow-real",
  "10-graph-models",
];

const run = (args) =>
  new Promise((resolve, reject) => {
    const child = spawn(ffmpeg, args, {stdio: "inherit", windowsHide: true});
    child.on("error", reject);
    child.on("exit", (code) => {
      if (code === 0) resolve();
      else reject(new Error(`ffmpeg exited with code ${code}`));
    });
  });

const quoteConcatPath = (value) =>
  value.replaceAll("\\", "/").replaceAll("'", "'\\''");

await mkdir(workRoot, {recursive: true});
const rendered = [];

for (let i = 0; i < orderedSegments.length; i++) {
  const name = orderedSegments[i];
  const segmentRoot = path.join(sourceRoot, name);
  const manifest = JSON.parse(
    await readFile(path.join(segmentRoot, "manifest.json"), "utf8"),
  );

  const available = new Set(
    (await readdir(segmentRoot)).filter((entry) => entry.endsWith(".jpg")),
  );
  const frames = manifest.frames.filter((frame) => available.has(frame.file));
  if (frames.length < 2) {
    throw new Error(`${name} does not contain enough captured frames`);
  }

  const lines = ["ffconcat version 1.0"];
  for (let frameIndex = 0; frameIndex < frames.length; frameIndex++) {
    const frame = frames[frameIndex];
    const next = frames[frameIndex + 1];
    const fallbackMs =
      frameIndex > 0
        ? frame.timeMs - frames[frameIndex - 1].timeMs
        : 250;
    const durationMs = next
      ? Math.max(80, next.timeMs - frame.timeMs)
      : Math.max(400, manifest.durationMs - frame.timeMs, fallbackMs);
    const framePath = path.join(segmentRoot, frame.file);
    lines.push(`file '${quoteConcatPath(framePath)}'`);
    lines.push(`duration ${(durationMs / 1000).toFixed(6)}`);
  }
  lines.push(
    `file '${quoteConcatPath(path.join(segmentRoot, frames.at(-1).file))}'`,
  );

  const listPath = path.join(workRoot, `${name}.ffconcat`);
  const videoPath = path.join(
    workRoot,
    `${String(i + 1).padStart(2, "0")}-${name}.mp4`,
  );
  await writeFile(listPath, `${lines.join("\n")}\n`, "utf8");

  console.log(`[2K] 编码 ${i + 1}/${orderedSegments.length} ${name}`);
  await run([
    "-y",
    "-f",
    "concat",
    "-safe",
    "0",
    "-i",
    listPath,
    "-r",
    "30",
    "-c:v",
    "libx264",
    "-preset",
    "medium",
    "-crf",
    "15",
    "-pix_fmt",
    "yuv420p",
    "-an",
    videoPath,
  ]);
  rendered.push(videoPath);
}

const finalList = path.join(workRoot, "segments.ffconcat");
await writeFile(
  finalList,
  [
    "ffconcat version 1.0",
    ...rendered.map((videoPath) => `file '${quoteConcatPath(videoPath)}'`),
  ].join("\n") + "\n",
  "utf8",
);

console.log("[2K] 合并全部实机录制片段");
await run([
  "-y",
  "-f",
  "concat",
  "-safe",
  "0",
  "-i",
  finalList,
  "-c",
  "copy",
  "-movflags",
  "+faststart",
  output,
]);

console.log(`[2K] 完成：${output}`);
