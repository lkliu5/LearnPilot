# CC · 产物落库 + 资源库 CRUD（会话一）完成总结

> 目标：把「文档学习」生成产物落库，让「查看」直接读已存产物渲染（不再重跑 RAG+大模型 ~25s），
> 「重新生成」变显式可选；资源库补齐「改（重命名）/删（含归属）」CRUD。内置课程本就走
> ResourceCache 全局缓存（查看命中即读、0 重复生成），无需改造。**不改既有接口签名，仅追加。**

## 一、现状诊断（改造前）

| 链路 | 产物如何存 | 「查看」是否重复生成 |
|---|---|---|
| **内置课程**（`services/resource.py`） | 讲义/视频/图解写 `ResourceCache`（`payload` JSON，键 `kp+difficulty+kind`）；思维导图确定性即时产出 | **否**——`generate_*` 命中缓存直接返回，0 次 LLM/RAG（已是正确架构） |
| **文档学习**（`services/document_generation.py`） | 只 `generation_log.record_document()` 埋点（**无产物**） | **是**——每次 `/document/generate/*` 都重跑「专属集合检索→重排→生成 Agent→防幻觉」（~25s、内容可能不一致、部署后反复烧 API） |

- `GenerationLog`（「我的资源库」索引）此前字段：`user_id/kp_id/kind/difficulty/title/resource_ref/created_at` + 文档来源 `source/doc_id/doc_title`，**不含产物内容**。
- 前端资源库预览 `ResourceLibraryPreview.tsx`：内置资源查看走 `getLecture/getDiagram`（缓存命中、快）；**文档资源查看走 `/document/generate/*`**（现场重生成，仅有前端内存 in-flight 去重）。
- 视频：文档链路 `videoUrl` 恒为 `null`（无服务端渲染 → 前端 Remotion Player + TTS），产物即「分镜脚本 scenes/narration」；内置视频同口径。

**结论**：需落库的是**文档学习产物**；内置课程已由 ResourceCache 承载，统一为「读产物」即可。

## 二、产物存储设计

在 `GenerationLog` 上**扩展产物字段**（而非新建表）——资源库资产行本就按
`(user_id, kp_id/doc_id, kind, difficulty)` 唯一 upsert，产物 1:1 挂在资产行上，无需 join：

- 新增列 `artifact JSON`（完整响应体，即产物**实际内容**：讲义 markdown / 图解 mermaid /
  思维导图 markdown / 视频分镜 / 练习题 / 闪卡）+ `artifact_updated_at DATETIME`（产物刷新时间）。
- **文本类产物存 DB**；视频等大文件仍走文件系统 + URL（`artifact` 内 `videoUrl` 引用，文档链路暂无服务端渲染故为 null）。
- **内置课程行 `artifact=NULL`**（其产物由 `ResourceCache` 全局缓存承载、命中即读、本就 0 重复生成）；文档学习行落 `artifact`。
- 轻量迁移 `_migrate_genlog_artifact`（SQLite `ADD COLUMN`，幂等，既有行默认 NULL，向后兼容）。

**查看=读、重新生成=可选** 机制（`document_generation.generate_*`）：
- `regenerate=false`（默认，即查看）：先 `get_document_artifact()` 命中即返回原产物（**0 次 RAG/LLM**、内容逐字一致）；未命中才实时生成并落库。
- `regenerate=true`（显式「重新生成」）：强制重跑、覆盖旧产物、刷新 `created_at`/`artifact_updated_at`。
- 命中键 `(userId, docId=主文档, kind, difficulty)`；**归属由 user_id 过滤强约束**，不越权读他人产物。

## 三、改动文件清单（后端 8 改 + 1 新增测试；前端 2 服务层；文档 2）

**后端（均为追加式改动，不改任何既有签名）**
1. `app/models/entities.py` — `GenerationLog` 新增 `artifact` / `artifact_updated_at` 两列。
2. `app/core/init_db.py` — 新增 `_migrate_genlog_artifact()` 并接入 `init_db()`。
3. `app/services/generation_log.py` — `record_document(..., artifact=)` 落产物；新增
   `get_document_artifact()`（读产物）/ `rename()` / `delete()` / `delete_document_rows()` / `_row_to_item()`。
4. `app/services/document_generation.py` — 6 类 `generate_*` 加 `regenerate` 参数 + 「先读产物、命中即返回」+ 落 `artifact`。
5. `app/schemas/document.py` — `_DocGenBase` 加可选 `regenerate: bool=False`（6 类生成请求共用）。
6. `app/api/v1/document.py` — 6 个生成端点透传 `body.regenerate`。
7. `app/api/v1/resource_history.py` — 新增 `POST /resource/history/rename`、`DELETE /resource/history/{logId}`。
8. `app/services/document_store.py` — 删文档时旁路清理其资源库资产行（`removedResources` 计数）。
9. `backend/tests/test_resource_artifact.py`（**新增**）— 7 用例覆盖落库/查看 0 生成/重新生成/改/删/删文档清理/内置不回归。

**前端（仅 `src/services/` 数据获取层，additive，tsc 干净）**
10. `src/services/resourceHistory.ts` — 新增 `renameResource()` / `deleteResource()`。
11. `src/services/documentLearning.ts` — 6 类 `generate*` 加可选 `regenerate` 参数并入请求体（默认 false，向后兼容）。
    - **未改任何组件业务逻辑**：查看走原生成接口即自动读产物（后端已改为读产物、0 生成）；显式「重新生成」按钮 + 大预览框属**会话二**（前端工程）范畴。

**文档**
12. `docs/后端接口文档.md` — 新增 19.3 重命名 / 19.4 删除；20.5 增补「产物落库 + 查看直读 + `regenerate`」；20.4 补 `removedResources`。
13. `docs/progress/CC-artifact-persist-crud.md`（本文）。

## 四、接口文档增量

- **19.3** `POST /resource/history/rename` `{id,title}` → 返回重命名后条目；非本人/不存在 `1004`。
- **19.4** `DELETE /resource/history/{logId}` → `{id,deleted:true}`（连带产物）；非本人/不存在 `1004`。
- **20.4** 响应加 `removedResources`（删文档连带清理的资产行数）。
- **20.5 增补** 各生成接口请求加可选 `regenerate`：`false`=查看直读已落库产物（0 生成调用）、`true`=强制重生成覆盖并刷新时间。

## 五、验证结果（0 报错）

**pytest（mock provider，无 Key 全链路跑通）**
- `test_resource_artifact.py` + `test_resource_history.py` + `test_document_learning.py`：**29 passed**。
- **全量：`pytest -q` → 251 passed, 1 skipped, 0 failed（195s）。**
- 关键断言（`test_view_reads_artifact_zero_generation_and_regenerate_reruns`）：生成后二次查看
  `retrieve/run_generator` 调用计数 **== 0**、`markdown`/`sources` 与首次逐字一致；`regenerate=true` 时计数 ≥1（真正重跑）。

**前端**：`npx tsc --noEmit` → **exit 0（干净）**。

**live curl（实测回包，port 8199，真实 dev 库）**
- 启动即跑迁移 → dev 库无报错、`/health` code 0（迁移在真实库生效）。
- rename happy-path（python urllib 正常 UTF-8）→ `code 0` 返回完整重命名条目（文档 diagram 行 id=21，含 source/docId/docTitle 契约字段）。
- rename 越权（admin 改 learner 资产）→ `1004`；delete → `code 0 {deleted:true}` 且列表已消失。
- openapi 确认 `/resource/history/rename`、`/resource/history/{log_id}` 已注册，`DocLectureRequest.regenerate` 在 schema 中。
- 备注：dev 服务器上直接用 Git-Bash `curl -d '{...初级...}'` 触发内置讲义返回 `1001 There was an error parsing the body`——系 **Windows Git-Bash 对请求体中文 UTF-8 的转义问题**（改用 python urllib 即 code 0），**非本次代码问题**；内置生成链路由 pytest（mock）全绿佐证。

## 六、红线自检

- ✅ 不改既有接口签名——仅**追加** rename/delete 端点、可选 `regenerate` 字段、`GenerationLog` 新列；既有生成/埋点接口路径与字段不变。
- ✅ 不动内置画像/诊断/路径/掌握度；向量库隔离不变（文档专属集合逻辑未触）。
- ✅ Mock 兜底：无任何 Key 下 251 用例全绿，产物确定性、查看 0 生成。
- ✅ DB 产物大小合理：文本类存 `artifact` JSON；视频等大文件仍走文件系统 + URL。
- ✅ 未在未被要求时重构已验收代码（`list_history` 保持原样，仅新增 `_row_to_item` 供 rename 用）。
- ✅ 前端仅动 `src/services/` 数据层（additive）、未改组件业务逻辑/store/路由；tsc 干净。
- ✅ 归属校验：读产物 / rename / delete 均按 `user_id` 强约束，越权 `1004`。

## 七、遗留 / 交接会话二（前端体验，本会话不做）

- 文档学习右栏「重新生成」按钮：调 `generate*(..., regenerate=true)`（服务层已就绪）。
- 大预览框 + 框内下载/重新生成/重命名（`renameResource` 已就绪）：读会话一已落库产物，不重生成。
- 生成进度/状态反馈。
