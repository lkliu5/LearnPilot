# 讲义真实配图改用免版权图源（可插拔图片 Provider · Wikimedia Commons）

## 现状说明（改动前的问题）

讲义图文增强（`enrich_lecture`）此前在真实模式下复用 **Tavily 图片搜索**（`web_search.search_images`，
`include_images`）取真实配图。Tavily 返回的图片多是带**防盗链 / 会过期**的 CDN 直链（如
`byteimg` 这类），前端 `<img>` 加载时被对方拒绝（防盗链）或链接已失效（过期），
结果几乎总是触发前端裂图兜底「🖼️ 图片暂不可用」——真实图基本看不到。

> 注意：受影响的只有**讲义配图**这一路；资源推荐用的 Tavily **文本**搜索（接口文档 8.6）
> 是另一条链路，本次**完全不动**。

## 图源 Provider 设计说明

新增**面向讲义配图**的可插拔「图片搜索 Provider」抽象（`backend/app/services/image_search.py`），
设计与既有 `web_search` Provider 一致（Protocol + 多实现 + `get_provider()` 选择），但单独成层、
专走**免版权、URL 稳定、可标注来源**的图源：

| Provider | 说明 | 在线条件 |
| --- | --- | --- |
| `none` | 无图源能力，`search_images()` 恒返回 `[]`（上层不插真实图） | 永远 offline |
| `wikimedia`（**默认**） | Wikimedia Commons（MediaWiki API，`generator=search` + File 命名空间）。免版权/可商用，图片取 `imageinfo.thumburl`（`upload.wikimedia.org` 稳定缩略图，**不防盗链、加载快**），记录文件标题 + Commons 文件页链接 + 许可（如 `CC BY-SA 4.0`）用于标注 | 免密钥，联网即在线 |
| `pexels`（**预留兜底**） | Pexels Photo API（免版权摄影图，CDN 稳定）。接口已留好，配 `PEXELS_API_KEY` 即在线 | 需 Key |

- **组合兜底**：`get_provider()` 在主源为 `wikimedia` 且另配了 `PEXELS_API_KEY` 时，自动组合为
  `_CompositeProvider([wikimedia, pexels])`——Wikimedia 没命中再试 Pexels。默认（无 Pexels Key）即纯 Wikimedia，
  没命中就不插图（**宁缺毋滥**），符合本次「先不强接 Pexels」。
- **防幻觉**：图片 URL 一律取自图源结果，绝不由 LLM 编造；上层 `lecture_media._search_real_image`
  再做 http(s) 二次校验后才嵌入。
- **失败不致命 / 幂等**：任何网络/解析异常都 `try/except` 回 `[]`（实测连续高频请求触发
  `ConnectionReset` 时，配图块直接返回 `None`，讲义本身照常产出，无崩溃、无破图）；`enrich_lecture`
  末尾 `<!-- media:enriched -->` 标记保证幂等。
- **相关性**：搜图关键词直接用知识点名（Commons 按相关性排序；附加英文/泛词反而拉低中文命中相关性）。
- **mock 不发真实请求**：mock 由 `lecture_media`（`llm.is_mock`）在调用图源前拦截，走确定性内联 SVG 占位，
  **根本不会触达本模块**，无任何真实请求。

## 改动文件清单

### 后端（新增 1 + 追加 2，接口签名不变）
- `backend/app/services/image_search.py`（**新增**）：`ImageProvider` 协议 + `_OfflineProvider` /
  `_WikimediaProvider` / `_PexelsProvider` / `_CompositeProvider` + `get_provider()`。
- `backend/app/core/lecture_media.py`（**改**）：`_search_real_image` 改用 `image_search.get_provider()`
  （原走 `web_search`）；`_image_block` 来源标注改为指向图源**来源页**（Wikimedia 文件页链接）并附许可；
  头部 docstring 同步更新。**`enrich_lecture` 签名不变。**
- `backend/app/core/config.py`（**追加**）：`image_provider`(默认 `wikimedia`) / `wikimedia_api_url` /
  `pexels_api_key` / `pexels_base_url` / `image_search_timeout_seconds` / `image_search_max_results`。

### 前端
- **无改动**。既有 `MarkdownRenderer` 的 `MarkdownImage` 已支持外链 http(s) 图片
  （`defaultUrlTransform` 放行）并自带 `onError` 裂图兜底，无需任何修改（遵守「禁止改 frontend/src」纪律）。

### 文档
- `docs/后端接口文档.md` 8.2：增量说明更新（配图改 Wikimedia 免版权图源 + 可插拔 Provider + 配置项；
  字段/路径/契约不变）。

### 测试
- **无需改测试**：mock 路径（`data:image/svg+xml` 占位）完全不变，`test_b5b.py` 断言照常通过。

## 启动命令

```bash
# 后端（mock 全链路，无需任何 Key；不会触达图源）
cd backend && set LLM_PROVIDER=mock&& uvicorn app.main:app --port 8000
# 后端（真实 LLM + Wikimedia 免版权配图，默认即开，无需 Key，仅需联网）
cd backend && set LLM_PROVIDER=deepseek&& set DEEPSEEK_API_KEY=...&& uvicorn app.main:app --port 8000
# 可选：开启 Pexels 兜底
#   set PEXELS_API_KEY=...
```

## 验证结果（实测）

### 单测 / 类型
- `cd backend && pytest -q` → **208 passed, 1 skipped**（0 报错，无回归）。
- `cd frontend && npx tsc --noEmit` → **exit 0**（tsc 干净）。

### 图源实测（真实 Wikimedia Commons API）
中文/英文关键词均命中相关图、URL 为稳定 `upload.wikimedia.org` 缩略图：

| 关键词 | 命中 | 首图 | 许可 |
| --- | --- | --- | --- |
| 神经网络 | 5 | `.../卷积神经网络.png/960px-...` | CC BY-SA 4.0 |
| Neural network | 5 | `.../Neural_network_-_Midjourney_and_Grok.png/960px-...` | Public domain |
| 梯度下降 | 5 | `.../Gradient_descent_with_momentum.svg/960px-...` | CC0 |
| 卷积神经网络 | 5 | `.../卷积神经网络.png/960px-...` | CC BY-SA 4.0 |

后端产出的真实配图块（`_image_block`，非 mock）：
```markdown
![The overall structure of convolutional neural networks](https://upload.wikimedia.org/wikipedia/commons/thumb/2/25/%E5%8D%B7%E7%A7%AF%E7%A5%9E%E7%BB%8F%E7%BD%91%E7%BB%9C.png/960px-%E5%8D%B7%E7%A7%AF%E7%A5%9E%E7%BB%8F%E7%BD%91%E7%BB%9C.png)

*图片来源：[Wikimedia Commons](https://commons.wikimedia.org/wiki/File:...卷积神经网络.png)（CC BY-SA 4.0）*
```

### 浏览器实测（Playwright，单次干净请求）
- **真实图正常加载显示**：CNN 结构图 `complete=true`、`naturalWidth=960`、`naturalHeight=332`、
  host=`upload.wikimedia.org`——不再「图片暂不可用」，且与知识点（卷积神经网络）相关。
- **来源标注**：图下 caption「图片来源：Wikimedia Commons（CC BY-SA 4.0）」，链接指向 Commons 文件页。
- **裂图兜底**：故意置坏 URL → 破图 `<img>` 从 DOM 移除、替换为「🖼️ 图片暂不可用」占位，**不显破图**
  （唯一 console error 即该故意 404，是 `onError` 的触发源）。
- 截图：`lecture-wikimedia-real-image.png`（项目根目录）。

### 防幻觉/失败兜底实测
- 连续高频请求触发 Wikimedia `ConnectionReset` 时，`_image_block` 返回 `None`，讲义正文照常产出，
  **无异常、无破图**（搜图失败不影响讲义本身）。

## 红线自检
- ✅ **不改既有接口签名/路径/字段/枚举**：`enrich_lecture` 签名不变；图源为新增内部模块；
  `web_search.search_images` 保留不动；8.2 仅追加增量说明。
- ✅ **免版权 + URL 稳定 + 可标注来源**：Wikimedia Commons（`upload.wikimedia.org` 不防盗链），
  标注文件页链接 + 许可；替换掉防盗链/过期的 Tavily 图片直链。
- ✅ **防幻觉**：图片 URL 只取自图源结果并二次校验 http(s)，绝不由 LLM 编造。
- ✅ **禁止 AI 生成图片**：图解=Mermaid 复用，真实图=Wikimedia 搜索，占位=确定性 SVG，无生成式画图。
- ✅ **内容安全不绕过**：外部图片描述 alt 另过 `content_safety.guard`。
- ✅ **Mock-first**：mock 模式走确定性占位、不触达图源、不发任何真实请求；无任何 Key 跑通全链路。
- ✅ **mermaid 图解仍正常**：图解路未改动。
- ✅ **既有链路无回归**：资源推荐的 Tavily 文本搜索不受影响；208 passed / tsc 0 / 0 真实 console error。
- ✅ **未改 frontend/src**：前端零改动（既有外链图片支持 + 裂图兜底已满足需求）。
