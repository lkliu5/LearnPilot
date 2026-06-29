/* 每知识点的 mock 学习内容（讲义三档 / 测验 / 思维导图 / 知识图解）。
 *
 * 背景：mock 模式（无后端联调）下学习资源页此前只有「神经网络基础(nn)」一套内容，
 * 故曾把 kpId 写死为 nn——导致从学习路径点任意知识点都落到神经网络。这里为其余知识点
 * 补齐对应内容，使「点不同知识点 → 看对应内容」在纯 mock 下也成立；nn 仍沿用
 * LearningResource.tsx 内既有的精修常量（作为兜底/默认）。
 *
 * 联调模式（USE_REAL_API=true）不使用本文件，内容仍由后端按 kpId 真实生成。
 */
import type { QuizQuestion } from '../components/QuizRenderer'

export interface KpResourceContent {
  /** 难度自适应三档讲义（入门/初级/高级），与难度切换 UI 对齐 */
  lectureByLevel: Record<'入门' | '初级' | '高级', string>
  /** 分阶测试题（mock 本地判分） */
  quiz: QuizQuestion[]
  /** 思维导图大纲（markdown 标题层级） */
  mindmap: string
  /** 知识图解（mermaid flowchart） */
  diagram: string
}

/* ─────────────────────────── 机器学习基础 (ml) ─────────────────────────── */
const ml: KpResourceContent = {
  lectureByLevel: {
    入门: `# 机器学习基础（入门版）

> 本讲义由**领域知识生成 Agent**按「入门」难度生成——用最直白的话讲清「机器是怎么学的」。

## 一、机器学习在做什么

传统编程是人写规则；机器学习是**给机器大量例子，让它自己总结规律**。
比如给它很多「邮件 + 是否垃圾邮件」的例子，它就能学会判断新邮件。

## 二、三种常见类型

- **监督学习**：例子带答案（标签），学「输入→输出」的映射，如分类、回归。
- **无监督学习**：例子没答案，自己找结构，如聚类。
- **强化学习**：在环境中试错，靠奖励学策略。

> **一句话**：机器学习 = 从数据里自动找规律，再用规律预测新数据。`,

    初级: `# 机器学习基础（初级版）

> 本讲义由**领域知识生成 Agent**生成，难度已适配为「初级」，并经**内容审核 Agent** RAG 交叉校验。

## 一、什么是机器学习

机器学习（Machine Learning）让计算机从数据中**自动学习规律**，而非依赖人工编写的固定规则。其核心是用一个带参数的**模型**去拟合数据，再用它对新样本做预测。

## 二、监督学习的基本流程

1. 准备带标签的**训练集** \`(x, y)\`
2. 选择模型与**损失函数**（衡量预测与真值的差距）
3. 通过优化算法**最小化损失**，得到最优参数
4. 在**测试集**上评估泛化能力

\`\`\`python
from sklearn.linear_model import LogisticRegression
clf = LogisticRegression()
clf.fit(X_train, y_train)        # 训练：从数据学参数
acc = clf.score(X_test, y_test)  # 评估泛化
\`\`\`

## 三、过拟合与欠拟合

- **欠拟合**：模型太简单，训练/测试都差 → 提升模型复杂度。
- **过拟合**：训练好、测试差，把噪声也背了下来 → 正则化、增样本、早停。

> **小结**：数据 → 模型 → 损失 → 优化 → 评估，是一切监督学习任务的统一闭环。下一步建议学习「神经网络基础」。`,

    高级: `# 机器学习基础（高级版）

> 本讲义由**领域知识生成 Agent**按「高级」难度生成——侧重形式化与偏差/方差权衡。

## 一、学习问题的形式化

给定分布 \`D\` 上的样本 \`(x, y)\`，目标是找到假设 \`h\` 最小化期望风险：

\`\`\`
R(h) = E_{(x,y)~D}[ L(h(x), y) ]
\`\`\`

实践中只能最小化经验风险 \`R_emp(h) = (1/n) Σ L(h(x_i), y_i)\`。

## 二、偏差—方差分解

泛化误差 ≈ **偏差² + 方差 + 噪声**：

- 高偏差 → 欠拟合（模型容量不足）
- 高方差 → 过拟合（对训练集波动敏感）

正则化（L1/L2）、交叉验证、集成都是在这条权衡线上做取舍。

## 三、工程要点

- **特征工程 / 标准化**对线性模型影响显著
- **交叉验证**做无偏的超参选择
- **数据泄漏**是最常见、最隐蔽的坑

> **小结**：理解经验风险最小化与偏差/方差权衡，是调好任何模型的底层心法。下一步建议「神经网络基础 / 深度学习原理」。`,
  },
  quiz: [
    {
      question_id: 'ml_q1', question_type: 'single',
      question_text: '下列哪种任务属于监督学习？',
      options: [
        { option_id: 'a', option_text: '把无标签用户分成若干群体' },
        { option_id: 'b', option_text: '根据带标签的房屋数据预测房价' },
        { option_id: 'c', option_text: '让智能体在游戏中试错获取奖励' },
      ],
      correct_answer: 'b',
      explanation: '监督学习使用带标签数据学习输入到输出的映射；预测房价是典型的回归（监督学习）。',
    },
    {
      question_id: 'ml_q2', question_type: 'boolean',
      question_text: '过拟合的典型表现是训练集表现很好但测试集表现明显变差。',
      options: [{ option_id: 'true', option_text: '正确' }, { option_id: 'false', option_text: '错误' }],
      correct_answer: 'true',
      explanation: '过拟合即模型把训练集的噪声也学了进去，泛化能力下降，表现为训练好、测试差。',
    },
    {
      question_id: 'ml_q3', question_type: 'multiple',
      question_text: '以下哪些手段有助于缓解过拟合？（多选）',
      options: [
        { option_id: 'a', option_text: '增加正则化项' },
        { option_id: 'b', option_text: '增加训练数据' },
        { option_id: 'c', option_text: '提前停止训练（早停）' },
        { option_id: 'd', option_text: '一味增大模型复杂度' },
      ],
      correct_answer: ['a', 'b', 'c'],
      explanation: '正则化、增样本、早停都能抑制过拟合；盲目增大模型复杂度反而加剧过拟合。',
    },
    {
      question_id: 'ml_q4', question_type: 'single',
      question_text: '损失函数（loss）在训练中的作用是？',
      options: [
        { option_id: 'a', option_text: '衡量预测与真实值的差距，作为优化目标' },
        { option_id: 'b', option_text: '决定数据的存储格式' },
        { option_id: 'c', option_text: '随机打乱样本顺序' },
      ],
      correct_answer: 'a',
      explanation: '损失函数量化预测与真值的差距，优化算法通过最小化损失来更新模型参数。',
    },
  ],
  mindmap: `# 机器学习基础
## 学习范式
### 监督学习
### 无监督学习
### 强化学习
## 监督学习流程
### 训练集 (x,y)
### 损失函数
### 优化求参
### 测试集评估
## 模型困境
### 欠拟合
### 过拟合
#### 正则化
#### 早停
`,
  diagram: `flowchart LR
  D["训练数据 (x,y)"] --> M["模型 h(x;θ)"]
  M --> P["预测 ŷ"]
  P --> L{{"损失 L(ŷ,y)"}}
  L -. 反向优化更新 θ .-> M
  M --> E["测试集评估泛化"]
`,
}

/* ─────────────────────────── 深度学习原理 (dl) ─────────────────────────── */
const dl: KpResourceContent = {
  lectureByLevel: {
    入门: `# 深度学习原理（入门版）

> 本讲义由**领域知识生成 Agent**按「入门」难度生成——把「深」讲成「多搭几层」。

## 一、深度，深在哪

把很多层神经网络**叠起来**，就是深度学习。层数越多，能表达的规律越复杂——
浅层认边角，深层认整体。

## 二、为什么以前不流行

层一多就难训练：梯度会「消失」。后来有了 **ReLU 激活、更好的初始化、批归一化、
更大的数据和算力**，深层网络才真正跑起来。

> **一句话**：深度学习 = 多层网络 + 让它训得动的那些技巧。`,

    初级: `# 深度学习原理（初级版）

> 本讲义由**领域知识生成 Agent**生成，难度已适配为「初级」，并经**内容审核 Agent** RAG 交叉校验。

## 一、从浅层到深层

深度学习用**多层非线性变换**逐层提取特征：低层学边缘/纹理，高层学语义/概念。
层数带来的表达力，是它在图像、语音、文本上超越传统方法的关键。

## 二、训练深层网络的三大技巧

1. **激活函数 ReLU**：正区间梯度恒为 1，缓解梯度消失。
2. **批归一化（BatchNorm）**：稳定每层输入分布，加速收敛。
3. **残差连接（Residual）**：让梯度有「高速公路」直达浅层，可训练上百层。

\`\`\`python
import torch.nn as nn
block = nn.Sequential(
    nn.Linear(256, 256), nn.BatchNorm1d(256), nn.ReLU()
)
\`\`\`

## 三、正则化与优化

- **Dropout**：训练时随机丢弃神经元，抑制过拟合。
- **Adam**：自适应学习率，深层网络常用优化器。

> **小结**：深度 = 表达力，但要靠 ReLU / BN / 残差 / Dropout 才训得稳。下一步建议学习「CNN架构」。`,

    高级: `# 深度学习原理（高级版）

> 本讲义由**领域知识生成 Agent**按「高级」难度生成——侧重梯度流与归一化的数学动机。

## 一、梯度消失/爆炸

深层链式求导是连乘：\`∂L/∂a^(1) = Π_l W^(l)ᵀ diag(σ')\`。
若谱半径持续 <1 → 梯度消失；>1 → 爆炸。ReLU + He 初始化让方差逐层保持稳定。

## 二、残差网络的本质

\`y = x + F(x)\` 使雅可比含恒等项 \`I + ∂F/∂x\`，梯度可绕过非线性直接回传，
从而支持极深网络的优化。

## 三、归一化家族

- **BatchNorm**：按 batch 维归一，依赖较大 batch。
- **LayerNorm**：按特征维归一，序列模型/Transformer 首选。

> **小结**：深层可训练性 = 归一化稳分布 + 残差通梯度 + 自适应优化器。下一步建议「CNN / Transformer」。`,
  },
  quiz: [
    {
      question_id: 'dl_q1', question_type: 'single',
      question_text: '残差连接（y = x + F(x)）最主要解决的问题是？',
      options: [
        { option_id: 'a', option_text: '减少模型参数量' },
        { option_id: 'b', option_text: '缓解深层网络的梯度消失、便于优化' },
        { option_id: 'c', option_text: '对输入图像做数据增强' },
      ],
      correct_answer: 'b',
      explanation: '残差连接让梯度可经恒等路径直达浅层，缓解梯度消失，使极深网络可训练。',
    },
    {
      question_id: 'dl_q2', question_type: 'boolean',
      question_text: 'Dropout 通常在训练阶段随机丢弃部分神经元以抑制过拟合。',
      options: [{ option_id: 'true', option_text: '正确' }, { option_id: 'false', option_text: '错误' }],
      correct_answer: 'true',
      explanation: 'Dropout 在训练时随机置零部分神经元，减少协同适应，从而抑制过拟合；推理时关闭。',
    },
    {
      question_id: 'dl_q3', question_type: 'multiple',
      question_text: '以下哪些有助于训练更深的网络？（多选）',
      options: [
        { option_id: 'a', option_text: 'ReLU 激活函数' },
        { option_id: 'b', option_text: '批归一化 BatchNorm' },
        { option_id: 'c', option_text: '残差连接' },
        { option_id: 'd', option_text: '把所有权重初始化为 0' },
      ],
      correct_answer: ['a', 'b', 'c'],
      explanation: 'ReLU、BatchNorm、残差连接都利于深层训练；权重全 0 会破坏对称性、无法学习。',
    },
    {
      question_id: 'dl_q4', question_type: 'single',
      question_text: '深层网络中，高层特征相比低层特征通常更偏向于？',
      options: [
        { option_id: 'a', option_text: '边缘、纹理等底层细节' },
        { option_id: 'b', option_text: '语义、概念等高层抽象' },
        { option_id: 'c', option_text: '原始像素值' },
      ],
      correct_answer: 'b',
      explanation: '深层网络逐层抽象：低层捕捉边缘纹理，高层组合出语义/概念级特征。',
    },
  ],
  mindmap: `# 深度学习原理
## 为什么要深
### 逐层特征抽象
### 低层边缘→高层语义
## 可训练性技巧
### ReLU 激活
### 批归一化
### 残差连接
### Dropout
## 优化
### Adam 自适应
### 梯度消失/爆炸
`,
  diagram: `flowchart LR
  X["输入"] --> L1["层1: 边缘/纹理"]
  L1 --> L2["层2: 部件"]
  L2 --> L3["层3: 语义概念"]
  L3 --> Y["输出"]
  X -. 残差连接 .-> L2
  L1 -. 残差连接 .-> L3
`,
}

/* ─────────────────────────── CNN架构 (cnn) ─────────────────────────── */
const cnn: KpResourceContent = {
  lectureByLevel: {
    入门: `# CNN架构（入门版）

> 本讲义由**领域知识生成 Agent**按「入门」难度生成——用「滑动小窗口看图」来理解卷积。

## 一、CNN 在看什么

处理图像时，不必把每个像素都全连接。CNN 用一个**小窗口（卷积核）在图上滑动**，
每次只看一小块，找局部特征（边、角、纹理），再层层组合成完整物体。

## 二、三个关键词

- **卷积**：小窗口滑动提取局部特征。
- **池化**：缩小尺寸、保留主要信息，更抗位移。
- **权重共享**：同一个窗口走遍全图，参数少、效率高。

> **一句话**：CNN = 用滑动窗口高效地从图像里抽特征。`,

    初级: `# CNN架构（初级版）

> 本讲义由**领域知识生成 Agent**生成，难度已适配为「初级」，并经**内容审核 Agent** RAG 交叉校验。

## 一、卷积层

卷积核（如 3×3）在输入特征图上滑动，做**局部加权求和**得到输出特征图。
关键特性：**局部连接**与**权重共享**，大幅减少参数并保留空间结构。

\`\`\`python
import torch.nn as nn
conv = nn.Conv2d(in_channels=3, out_channels=16, kernel_size=3, padding=1)
# 输入 (N,3,H,W) → 输出 (N,16,H,W)
\`\`\`

## 二、池化层

**最大池化**取窗口内最大值，降采样、减少计算并增强平移不变性。

## 三、典型结构

\`[卷积 → ReLU → 池化] × N → 展平 → 全连接 → 分类\`。
经典网络 LeNet / AlexNet / VGG / ResNet 都遵循这一骨架并不断加深。

> **小结**：卷积抽局部特征、池化降维、全连接做决策——这就是 CNN 的图像处理范式。下一步建议学习「Transformer架构」。`,

    高级: `# CNN架构（高级版）

> 本讲义由**领域知识生成 Agent**按「高级」难度生成——侧重感受野与参数效率。

## 一、卷积的数学形式

输出特征图：\`Y[i,j] = Σ_{m,n} X[i+m, j+n] · K[m,n] + b\`。
输出尺寸：\`O = ⌊(W - F + 2P)/S⌋ + 1\`（W 输入、F 核、P 填充、S 步长）。

## 二、感受野

层层堆叠使深层每个神经元的**感受野**指数增大，从而「看到」更大范围的上下文。
空洞卷积（dilation）可在不增参数的情况下扩大感受野。

## 三、参数效率

权重共享 + 局部连接使卷积层参数量与图像尺寸**解耦**——这是 CNN 相对全连接网络
在视觉任务上高效的根本原因。1×1 卷积则用于跨通道信息融合与降维。

> **小结**：感受野决定「看多大」，权重共享决定「多省参数」。下一步建议「Transformer 架构」对比注意力机制。`,
  },
  quiz: [
    {
      question_id: 'cnn_q1', question_type: 'single',
      question_text: 'CNN 中「权重共享」带来的主要好处是？',
      options: [
        { option_id: 'a', option_text: '显著减少参数量并保留平移不变性' },
        { option_id: 'b', option_text: '让网络无法处理图像' },
        { option_id: 'c', option_text: '强制每个像素独立全连接' },
      ],
      correct_answer: 'a',
      explanation: '同一卷积核滑过全图（权重共享），参数量与图像大小解耦，并带来平移不变性。',
    },
    {
      question_id: 'cnn_q2', question_type: 'boolean',
      question_text: '最大池化（Max Pooling）能在降采样的同时增强一定的平移不变性。',
      options: [{ option_id: 'true', option_text: '正确' }, { option_id: 'false', option_text: '错误' }],
      correct_answer: 'true',
      explanation: '最大池化取局部窗口最大值，降低分辨率的同时使特征对小幅平移更鲁棒。',
    },
    {
      question_id: 'cnn_q3', question_type: 'single',
      question_text: '输入 32×32、卷积核 3×3、padding=1、stride=1，输出空间尺寸为？',
      options: [
        { option_id: 'a', option_text: '30×30' },
        { option_id: 'b', option_text: '32×32' },
        { option_id: 'c', option_text: '34×34' },
      ],
      correct_answer: 'b',
      explanation: 'O=(32-3+2×1)/1+1=32，padding=1 的 3×3 卷积保持空间尺寸不变。',
    },
    {
      question_id: 'cnn_q4', question_type: 'multiple',
      question_text: '关于卷积神经网络，下列说法正确的是？（多选）',
      options: [
        { option_id: 'a', option_text: '卷积层提取局部特征' },
        { option_id: 'b', option_text: '堆叠卷积层会增大感受野' },
        { option_id: 'c', option_text: '1×1 卷积可用于跨通道融合与降维' },
        { option_id: 'd', option_text: 'CNN 只能用于文本任务' },
      ],
      correct_answer: ['a', 'b', 'c'],
      explanation: '卷积抽局部特征、堆叠增大感受野、1×1 卷积做通道融合；CNN 主要用于视觉，也可用于其他网格数据，但「只能用于文本」错误。',
    },
  ],
  mindmap: `# CNN架构
## 卷积层
### 局部连接
### 权重共享
### 感受野
## 池化层
### 最大池化
### 降采样/平移不变
## 典型骨架
### 卷积→ReLU→池化
### 全连接分类
### LeNet/VGG/ResNet
`,
  diagram: `flowchart LR
  IMG["输入图像"] --> C1["卷积 + ReLU"]
  C1 --> P1["池化"]
  P1 --> C2["卷积 + ReLU"]
  C2 --> P2["池化"]
  P2 --> F["展平"]
  F --> FC["全连接"]
  FC --> O["分类输出"]
`,
}

/* ─────────────────────────── Transformer架构 (transformer) ─────────────────────────── */
const transformer: KpResourceContent = {
  lectureByLevel: {
    入门: `# Transformer架构（入门版）

> 本讲义由**领域知识生成 Agent**按「入门」难度生成——把「注意力」讲成「划重点」。

## 一、注意力是什么

读一句话时，理解某个词要参考句中**相关的其他词**。Transformer 让每个词都能
**主动去看**整句话里和自己最相关的部分，给它们更高权重——这就是「注意力」。

## 二、它强在哪

- 不像 RNN 逐词处理，Transformer **一次看全句**，可并行、训练快。
- 能捕捉**长距离**依赖（句首和句尾的关系也抓得住）。

> **一句话**：Transformer = 让每个词自动给全句「划重点」，再据此理解。`,

    初级: `# Transformer架构（初级版）

> 本讲义由**领域知识生成 Agent**生成，难度已适配为「初级」，并经**内容审核 Agent** RAG 交叉校验。

## 一、自注意力机制

每个 token 生成 **Query / Key / Value** 三个向量。用 Q 与所有 K 算相似度得到权重，
对 V 加权求和，得到融合了上下文的新表示：

\`\`\`
Attention(Q,K,V) = softmax(QKᵀ / √d_k) · V
\`\`\`

## 二、多头注意力

并行多组注意力（多个「头」），从不同子空间关注不同关系，再拼接——表达更丰富。

## 三、整体结构

\`输入嵌入 + 位置编码 → [多头注意力 + 前馈网络 + 残差&LayerNorm] × N\`。
因为没有循环结构，需用**位置编码**注入词序信息。

> **小结**：自注意力让全句信息一步交互，多头 + 位置编码 + 残差堆叠构成 Transformer。下一步建议学习「大模型微调技术」。`,

    高级: `# Transformer架构（高级版）

> 本讲义由**领域知识生成 Agent**按「高级」难度生成——侧重缩放点积与复杂度。

## 一、缩放点积注意力

\`softmax(QKᵀ/√d_k)V\` 中除以 \`√d_k\` 防止点积过大导致 softmax 饱和、梯度消失。
注意力矩阵 \`QKᵀ\` 大小为 \`n×n\`，复杂度 **O(n²·d)**，是长序列的主要瓶颈。

## 二、多头与子空间

\`head_i = Attention(QW_i^Q, KW_i^K, VW_i^V)\`，拼接后经 \`W^O\` 投影。
不同头可分别建模语法、指代、远距依赖等关系。

## 三、位置编码与变体

正弦位置编码 / 可学习位置 / 旋转位置编码（RoPE）。高效注意力（稀疏、线性、FlashAttention）
针对 O(n²) 瓶颈优化。

> **小结**：缩放点积稳梯度、多头扩表达、位置编码补序信息——这是大模型的统一底座。下一步建议「大模型微调技术」。`,
  },
  quiz: [
    {
      question_id: 'tr_q1', question_type: 'single',
      question_text: '缩放点积注意力中除以 √d_k 的主要作用是？',
      options: [
        { option_id: 'a', option_text: '防止点积过大使 softmax 饱和、梯度消失' },
        { option_id: 'b', option_text: '减少注意力头的数量' },
        { option_id: 'c', option_text: '把序列长度变为固定值' },
      ],
      correct_answer: 'a',
      explanation: '点积随维度增大而增大，除以 √d_k 做缩放可避免 softmax 进入饱和区、稳定梯度。',
    },
    {
      question_id: 'tr_q2', question_type: 'boolean',
      question_text: 'Transformer 没有循环结构，需要位置编码来注入词序信息。',
      options: [{ option_id: 'true', option_text: '正确' }, { option_id: 'false', option_text: '错误' }],
      correct_answer: 'true',
      explanation: '自注意力本身对顺序不敏感，必须通过位置编码引入 token 的次序信息。',
    },
    {
      question_id: 'tr_q3', question_type: 'multiple',
      question_text: '关于自注意力机制，下列正确的是？（多选）',
      options: [
        { option_id: 'a', option_text: '每个 token 生成 Q、K、V 三类向量' },
        { option_id: 'b', option_text: '可并行处理整个序列' },
        { option_id: 'c', option_text: '能捕捉长距离依赖' },
        { option_id: 'd', option_text: '其复杂度与序列长度无关' },
      ],
      correct_answer: ['a', 'b', 'c'],
      explanation: '自注意力用 Q/K/V、可并行、擅长长距离依赖；但注意力矩阵为 n×n，复杂度 O(n²) 与序列长度强相关。',
    },
    {
      question_id: 'tr_q4', question_type: 'single',
      question_text: '多头注意力相比单头的主要优势是？',
      options: [
        { option_id: 'a', option_text: '从多个子空间并行关注不同类型的关系' },
        { option_id: 'b', option_text: '彻底去掉前馈网络' },
        { option_id: 'c', option_text: '使模型无法并行' },
      ],
      correct_answer: 'a',
      explanation: '多头让模型在不同表示子空间并行学习不同关系（语法、指代、远距依赖等），表达更丰富。',
    },
  ],
  mindmap: `# Transformer架构
## 自注意力
### Query/Key/Value
### softmax(QKᵀ/√d_k)V
## 多头注意力
### 多子空间并行
### 拼接投影
## 整体结构
### 位置编码
### 前馈网络
### 残差 + LayerNorm
`,
  diagram: `flowchart LR
  E["输入嵌入 + 位置编码"] --> Q["Query"]
  E --> K["Key"]
  E --> V["Value"]
  Q --> A{{"softmax(QKᵀ/√d_k)"}}
  K --> A
  A --> Z["加权求和 · V"]
  V --> Z
  Z --> FFN["前馈网络 + 残差&LN"]
  FFN --> O["上下文表示"]
`,
}

/* ─────────────────────────── 大模型微调技术 (finetune) ─────────────────────────── */
const finetune: KpResourceContent = {
  lectureByLevel: {
    入门: `# 大模型微调技术（入门版）

> 本讲义由**领域知识生成 Agent**按「入门」难度生成——把微调讲成「在通才上补专业课」。

## 一、为什么要微调

大模型已经在海量数据上「读了万卷书」（预训练），但对你的**具体任务/领域**还不够专。
微调就是**用少量你的数据再训一训**，让它在你的场景上更好用。

## 二、省钱省力的做法

全部参数都重训太贵。**LoRA** 只训练很小一部分新增参数，效果接近、成本骤降，
是目前最常用的高效微调方法。

> **一句话**：微调 = 在预训练通才上，用少量数据补一门「专业课」。`,

    初级: `# 大模型微调技术（初级版）

> 本讲义由**领域知识生成 Agent**生成，难度已适配为「初级」，并经**内容审核 Agent** RAG 交叉校验。

## 一、为什么需要高效微调（PEFT）

大模型动辄数十亿参数，全量微调显存与算力开销巨大。**参数高效微调（PEFT）**只更新
极少量参数，即可让模型适配下游任务。

## 二、LoRA 原理

冻结原权重 \`W\`，在旁路注入低秩矩阵：\`W' = W + BA\`（\`B∈ℝ^{d×r}, A∈ℝ^{r×k}, r≪d\`）。
只训练 \`A、B\`，参数量从 \`d×k\` 降到 \`r×(d+k)\`。

\`\`\`python
from peft import LoraConfig, get_peft_model
cfg = LoraConfig(r=8, lora_alpha=16, target_modules=["q_proj", "v_proj"])
model = get_peft_model(base_model, cfg)  # 仅训练 LoRA 旁路
\`\`\`

## 三、其他方法

- **P-Tuning / Prompt-Tuning**：只训练少量「软提示」向量。
- **QLoRA**：4-bit 量化 + LoRA，单卡也能微调大模型。

> **小结**：冻结主干、只训小旁路，是大模型低成本落地的关键。这是路径的最后一步——恭喜你即将完成全程！`,

    高级: `# 大模型微调技术（高级版）

> 本讲义由**领域知识生成 Agent**按「高级」难度生成——侧重低秩假设与显存权衡。

## 一、低秩适配的假设

微调引起的权重更新 \`ΔW\` 往往是**低秩**的——LoRA 即用 \`ΔW = BA\`（秩 r）近似它。
推理时可将 \`BA\` 合并回 \`W\`，**不增加推理延迟**。

## 二、QLoRA 的关键

- **4-bit NF4 量化**冻结主干，显存大幅下降；
- 反传时**反量化**计算梯度，仅更新 LoRA 参数；
- **分页优化器**应对显存峰值。

## 三、选型权衡

\`r\` 越大表达力越强但参数/显存增加；\`lora_alpha\` 控制缩放。
全量微调效果上限更高，但 PEFT 在**成本/效果/可维护性**上往往更优。

> **小结**：低秩 + 量化把「微调大模型」从集群级拉到单卡级。至此你已走完从机器学习到大模型的完整路径。`,
  },
  quiz: [
    {
      question_id: 'ft_q1', question_type: 'single',
      question_text: 'LoRA 高效微调的核心思想是？',
      options: [
        { option_id: 'a', option_text: '冻结原权重，只训练注入的低秩旁路矩阵' },
        { option_id: 'b', option_text: '重新训练模型的全部参数' },
        { option_id: 'c', option_text: '删除模型的大部分层' },
      ],
      correct_answer: 'a',
      explanation: 'LoRA 冻结原权重 W，旁路注入低秩矩阵 BA 并只训练 A、B，大幅降低可训练参数量。',
    },
    {
      question_id: 'ft_q2', question_type: 'boolean',
      question_text: '相比全量微调，参数高效微调（PEFT）通常显著降低显存与算力开销。',
      options: [{ option_id: 'true', option_text: '正确' }, { option_id: 'false', option_text: '错误' }],
      correct_answer: 'true',
      explanation: 'PEFT 只更新极少量参数，冻结主干，因而显存与算力开销远低于全量微调。',
    },
    {
      question_id: 'ft_q3', question_type: 'multiple',
      question_text: '以下哪些属于参数高效微调方法？（多选）',
      options: [
        { option_id: 'a', option_text: 'LoRA' },
        { option_id: 'b', option_text: 'P-Tuning / Prompt-Tuning' },
        { option_id: 'c', option_text: 'QLoRA' },
        { option_id: 'd', option_text: '从零随机初始化重新训练整个模型' },
      ],
      correct_answer: ['a', 'b', 'c'],
      explanation: 'LoRA、P-Tuning、QLoRA 都是 PEFT；从零重训整个模型属于全量训练，不是高效微调。',
    },
    {
      question_id: 'ft_q4', question_type: 'single',
      question_text: 'QLoRA 相比普通 LoRA 的突出特点是？',
      options: [
        { option_id: 'a', option_text: '结合 4-bit 量化进一步降低显存，使单卡微调大模型成为可能' },
        { option_id: 'b', option_text: '必须使用上百张 GPU' },
        { option_id: 'c', option_text: '不需要任何训练数据' },
      ],
      correct_answer: 'a',
      explanation: 'QLoRA 用 4-bit 量化冻结主干并配合 LoRA，显存进一步下降，单卡即可微调大模型。',
    },
  ],
  mindmap: `# 大模型微调技术
## 为什么微调
### 预训练通才→领域专才
### 全量微调成本高
## 参数高效微调 PEFT
### LoRA 低秩旁路
### P-Tuning 软提示
### QLoRA 量化+LoRA
## 权衡
### 秩 r 与表达力
### 成本/效果
`,
  diagram: `flowchart LR
  PT["预训练大模型 (冻结 W)"] --> ADD["注入低秩旁路 BA"]
  DATA["少量领域数据"] --> ADD
  ADD --> TR["仅训练 A,B"]
  TR --> MERGE["合并 W + BA"]
  MERGE --> USE["领域适配模型 · 推理无额外延迟"]
`,
}

/** 知识点 id → mock 学习内容。nn 不在此表（沿用 LearningResource 内既有精修常量作默认）。 */
export const KP_RESOURCES: Record<string, KpResourceContent> = {
  ml,
  dl,
  cnn,
  transformer,
  finetune,
}
