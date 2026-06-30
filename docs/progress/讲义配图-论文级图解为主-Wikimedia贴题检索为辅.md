# 讲义配图改进：论文级 Mermaid 图解为主 + Wikimedia 贴题检索为辅

> 目标：配图要「专业、贴题」，但**禁止扒论文图**（版权风险 + PDF 抽图不可行）。
> 改为「专业 mermaid 图解为**主力** + Wikimedia 优化检索为**辅**（确定贴题才插，否则不插）」。
> 不改既有接口签名（仍只作用于 `/resource/lecture` 返回的 `markdown` 内容）。

## 一、改动文件清单（3 个源文件 + 1 个测试）

| 文件 | 改动 |
| --- | --- |
| `backend/app/core/llm.py` | ① `nn` 图解模板升级为**论文级分层网络**（输入层→隐藏层→输出层，全连接 + 前向流 + 反向传播回路），取代旧单神经元计算图；② 真实 LLM 图解 prompt（`_deepseek_diagram`）强化为「论文级标准架构图」，按知识点点名标准结构（NN 分层 / CNN 卷积→池化→全连接 / Transformer 嵌入→自注意力→前馈），并显式禁止跨域跑题。 |
| `backend/app/core/lecture_media.py` | 重写配图检索：① 检索词一律**带领域限定**（deep learning / neural network / machine learning），删除裸歧义词；② 新增**贴题判定门**`_is_on_topic`（正向词命中且无跨域排除词 + 非示意性噪声过滤），**确定贴题才插，否则不插**（宁缺毋滥）。 |
| `backend/tests/test_b5b.py` | 更新 `_image_query_candidates` 阶梯测试（域限定查询优先）；新增 `test_image_relevance_gate_rejects_cross_domain` 覆盖贴题门（电力变压器/新闻台/乐器调音被拒、标准架构图被收）。 |

接口签名、路径、字段名、枚举值**均未改动**；前端 `src/` 未改一行（tsc 0 报错）。

## 二、6 知识点配图抽查结论（requirement ③）

下表为**实测**：图解走 mock 模板路径打印首行；Wikimedia 走**真实联网**检索 + 贴题门后的最终命中。

| KP | 图解（mermaid）专业贴题？ | Wikimedia 真实图（贴题/不插） |
| --- | --- | --- |
| `ml` 机器学习基础 | ✅ `flowchart LR` 训练闭环：数据→划分→特征→模型→损失→优化器→评估 | ✅ `Unraveling AI Complexity - A Comparative View of AI/ML/DL/GenAI.jpg`（CC BY-SA 4.0，AI/ML 概念对比图，贴题） |
| `nn` 神经网络基础 | ✅ **本次升级**：`flowchart LR` 分层网络（输入层 x→隐藏层 ReLU→输出层 ŷ，全连接 + 损失 + 反向传播 ∂L/∂w 回路）——即论文/教材里标准的多层感知机示意 | ✅ `Convolutional Neural Network NeuralNetworkFilter.gif`（CC BY-SA 4.0，神经网络可视化，贴题） |
| `dl` 深度学习原理 | ✅ `flowchart LR` 前向→损失→反向（链式法则）→梯度→优化器更新→迭代，含归一化/残差 | ✅ `Deep Learning.jpg`（CC BY-SA 4.0，贴题） |
| `cnn` CNN架构 | ✅ `flowchart TD` 输入图像 H×W×3→卷积→ReLU→池化→卷积×N→展平→全连接→Softmax | ✅ `Convolutional neural network, maxpooling.png`（CC BY 4.0，标准 CNN 架构图，贴题） |
| `transformer` Transformer架构 | ✅ `flowchart TD` 嵌入→位置编码→编码器块×N（多头自注意力 softmax(QKᵀ/√dₖ)V→Add&Norm→FFN→Add&Norm）→输出 | ✅ `The-Transformer-model-architecture.png`（CC BY-SA 3.0，**论文原版 Transformer 架构图**，贴题）——**此前裸词「Transformer」会命中电力变压器/变形金刚电影，现已彻底修正** |
| `finetune` 大模型微调技术 | ✅ `mindmap` 微调谱系：全参 / LoRA（冻结+低秩增量 BA）/ 指令微调 SFT / 对齐（RLHF·DPO） | ✅ `Transfer Learning.png`（CC0，迁移学习概念图，贴题） |

**结论**：6/6 知识点图解均专业贴题（其中 `nn` 本次升级为论文级分层结构）；6/6 Wikimedia 真实图均确定贴题、零版权（CC/CC0），且**不再出现任何跨域不相关图**（电力变压器/新闻台 CNN/乐器调音/玩梗周边图均被贴题门拦下，回落到真正的标准示意图或不插）。

## 三、贴题门设计（requirement ②）

`lecture_media.py` 新增 `_DOMAIN_RELEVANCE` 表，每个领域配 `(命中子串, 域限定查询阶梯, 正向词, 跨域排除词)`：

- **查询带领域限定**：如 Transformer 用 `Transformer deep learning architecture` / `Self-attention mechanism diagram`，不再用裸 `Transformer`；CNN 用 `Convolutional neural network`，不再用裸 `CNN`。
- **贴题判定**：命中图的「标题+描述」须含该领域**正向词**（architecture/attention/neural/convolution…）且**不含跨域排除词**（electric/voltage/movie/cable news/guitar/instrument…）才判「确定贴题」并插入。
- **非示意性噪声过滤**`_NOISE_OFFTOPIC`：玩梗/周边/极小众应用图（cookie/drone racing/sticker/logo…）即便含正向词也不插。
- **宁缺毋滥**：任一候选都判不出贴题图 → 返回 None → 上层只用 mermaid 图解，不插不相关真实图。
- URL 仍**一律取自图源结果**（防幻觉，绝不让 LLM 编造链接），并标注来源页 + 许可证。

## 四、验证结果

```text
# 后端全量测试（0 报错）
$ cd backend && python -m pytest -q
220 passed, 1 skipped, 1 warning

# 关键测试
tests/test_b5b.py::test_image_query_candidates_domain_qualified_ladder   PASSED
tests/test_b5b.py::test_image_relevance_gate_rejects_cross_domain        PASSED
tests/test_b7a.py::test_diagram_per_topic_via_llm                        PASSED  # nn/cnn 仍 flowchart 开头
tests/test_contract_snapshot.py::test_20_diagram                         PASSED

# 前端类型检查（0 报错）
$ cd frontend && npx tsc --noEmit   →  exit 0

# 6 知识点 Wikimedia 真实联网抽查（贴题门生效）：见上表，6/6 贴题、零跨域
```

- **既有链路无回归**：220 passed，含内容安全（`test_content_safety`）、防幻觉（grounding）、契约快照全绿。
- **内容安全/防幻觉未破**：配图 alt 文本仍过 `content_safety.guard`；URL 仍只取真实图源结果，禁止 AI 生成图片的红线不变。
- **缓存刷新**：`@deepseek` 真实缓存经 `scripts/regen_lectures.py batch` 重生成，使新图解 prompt + 贴题门对页面生效（mock 模式无 Key 亦可全链路跑通）。

## 五、红线自检

- [x] 一次只做本任务（讲义配图），未顺手改其它阶段。
- [x] 未改接口路径/字段名/枚举值；未改前端业务逻辑/store/路由。
- [x] Mock-first：mock 模式走确定性 SVG 占位 + 模板图解，无 Key 全链路可跑通。
- [x] 禁止 AI 生成图片：图解为 mermaid 源码、配图 URL 只取自真实图源，均非生成式图片。
- [x] 防幻觉：图片 URL 二次 http(s) 校验 + 只取图源结果；alt 文本过内容安全 guard。
- [x] 未重构已验收阶段无关代码；新增/改动集中在配图与图解两处。
