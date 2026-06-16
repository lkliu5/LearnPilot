# fix：讲解视频分镜随知识点动态生成

## 背景
原 `LectureVideo.tsx` 的 5 个场景（画面 + 旁白）是神经网络硬编码，与所学知识点无关。
本次让 `/resource/video` 返回**结构化分镜脚本**（标题 + 3-5 场景，每场景含要点文本 + 旁白），
前端 Remotion 改为**参数化通用模板**，画面随脚本渲染。

## 改动文件清单

### 后端
- `backend/app/core/llm.py`
  - 新增 `LLMClient.generate_video_script()` + `_mock_video_script` / `_deepseek_video_script` /
    `_clean_video_script` / `_video_scene`，及常量 `_VIDEO_SCRIPT_NN`、模块 logger。
  - mock：确定性主题脚本（nn 与前端原 5 场景逐字对齐，其余知识点参数化，**绝不固定为神经网络**）；
    deepseek：真实生成 + 契约清洗（场景数 3-5、要点 1-4 条、标题/旁白非空），解析失败回落主题脚本。
- `backend/app/services/resource.py`
  - 重写 `generate_video()`：经 `generate_video_script` 取脚本 → 按 `_SCENE_FRAMES=180` 均匀铺帧
    （`scenes[].frame` / `narration[].frame`）→ `durationInFrames = 场景数×180`；写 `ResourceCache`
    （kind=`video` / `video@<provider>`）命中即返回（避免真实模式重复触发 LLM）。
  - 删除旧硬编码 `_NARRATION_NN` / `_NARRATION_FRAMES` / `_VIDEO_DURATION_FRAMES`。

### 前端
- `frontend/src/remotion/LectureVideo.tsx`：改为参数化通用模板 `LectureVideo({title, scenes})`，
  导出 `LectureScene` 类型、`SCENE_FRAMES`、`DEFAULT_SCENES`/`DEFAULT_TITLE`（兜底占位）；
  通用 `SceneCard` 按数据渲染场景标题/要点（任意场景数、任意要点条数），保留渐变/动画/进度点。
- `frontend/src/components/VideoLecture.tsx`：拉取 `getVideo` 的 `scenes`/`title` 注入 `Player.inputProps`，
  旁白侧栏与 TTS 由场景派生，`durationInFrames` 随场景数自适应；无脚本/请求失败回落默认脚本。
- `frontend/src/services/resource.ts`：`VideoData` 增 `title` / `scenes`（`VideoScene` 类型）。

### 契约 / 测试 / 文档
- `docs/后端接口文档.md` 8.3：新增 `title` / `scenes`（含 frame/title/points/narration）字段说明。
- `backend/tests/test_contract_snapshot.py` test_18、`backend/tests/test_b7a.py` 两个 video 用例：
  断言新字段与「画面随知识点变化」。

## 接口文档增量（8.3 响应新增）
- `title`：视频标题（= 知识点名）。
- `scenes[]`：分镜脚本，每项 `{ frame, title, points[], narration }`，3-5 个场景，要点 1-4 条。
- `narration[]` 保留（= `scenes[].{frame,narration}`，向后兼容 TTS）；`durationInFrames` = 场景数×180。

## 验证

### 自动化（mock provider，0 报错）
```
pytest tests/test_b7a.py tests/test_contract_snapshot.py -q  → 56 passed
npx tsc --noEmit                                              → 0 error
```

### 真实模型对比（LLM_PROVIDER=deepseek，两个差异明显的知识点）
| | Transformer 注意力机制 | 二叉树遍历 |
|---|---|---|
| 视频标题 | Transformer 注意力机制详解 | 二叉树遍历入门 |
| 场景标题 | 为什么需要注意力机制 / 自注意力 / 多头注意力 / 位置编码 / 小结 | 什么是二叉树遍历 / 前序遍历 / 中序遍历 / 后序与层序 / 小结对比 |
| 要点示例 | 查询Q、键K、值V三矩阵；Softmax 归一化得到权重 | 前序：根→左→右；层序使用队列实现 |
| 旁白示例 | 「自注意力通过 Q、K、V 矩阵计算每个词与其他词的关联权重…」 | 「中序遍历按左根右顺序，在二叉搜索树中能得到有序序列。」 |

→ 两主题的画面标题、要点、旁白**内容完全不同、各自对应主题，均不再是神经网络**。
