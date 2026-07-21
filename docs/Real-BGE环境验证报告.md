# Real BGE 环境验证报告

> 任务：TASK-003-C3-A Real BGE独立实验环境验证
> 基线提交：`522dcd0`
> 验证日期：2026-07-21
> 最终状态：`blocked`

## 1. 当前环境

- 操作系统：Windows 11，内核版本 `10.0.26200`，64位。
- 原环境Python：`3.12.13`，MSC v.1944，64位。
- 原解释器：Codex托管runtime中的Python。
- 独立环境：`backend/.bge-c3a-venv`，由同一Python 3.12.13创建，与项目业务环境隔离。
- 验证模型：`BAAI/bge-small-zh-v1.5`。
- 期望Embedding Profile：`sentence-transformers:baai_bge_small_zh_v1_5:d512`。
- 期望维度：512。
- 验证策略：只允许真实模型，脚本不存在hash或其他fallback路径。

## 2. Python、Torch与CUDA/CPU状态

原环境在读取Torch版本前即加载失败：

```text
PermissionError: [WinError 5] 拒绝访问
Error loading torch/lib/torch_python.dll or one of its dependencies
```

独立环境成功安装的wheel元数据：

```text
torch: 2.13.0+cpu
location: backend/.bge-c3a-venv/Lib/site-packages
CUDA build: none（CPU wheel）
target device: CPU
```

由于`import torch`失败，`torch.cuda.is_available()`无法在该进程中执行；不能伪造其运行值。安装包明确为官方CPU wheel，因此本次验证不依赖CUDA或GPU。

## 3. WinError 5定位结果

已确认：

1. `torch_python.dll`存在，大小约19.5MB，可读取。
2. 原runtime和独立venv中的DLL均无Mark-of-the-Web附加数据流。
3. 当前沙箱用户对原DLL具有Modify/Synchronize ACL，不是普通文件读取权限不足。
4. 系统存在`vcruntime140.dll`、`vcruntime140_1.dll`和`msvcp140.dll`。
5. 在独立venv中逐个使用Windows Loader加载：

| DLL | 结果 |
|---|---|
| `c10.dll` | loaded |
| `torch_cpu.dll` | loaded |
| `torch.dll` | loaded |
| `torch_global_deps.dll` | loaded |
| `torch_python.dll` | `PermissionError: WinError 5` |

同一错误在两个不同安装路径复现，且Torch的其他核心DLL可加载。因此可以排除：文件不存在、模型未下载、单一安装目录ACL、CUDA缺失、全部VC++运行库缺失。

当前证据将问题定位到`torch_python.dll`这一Python原生扩展的加载/执行环节。最可能原因是当前Codex托管沙箱或Windows应用控制策略阻止该DLL映射到Python进程。没有系统策略日志或管理员级事件查看权限，不能进一步断言具体是WDAC、AppLocker、防病毒软件还是另一种进程执行策略。

## 4. 修复尝试

1. 在原runtime直接执行`import torch`，稳定复现WinError 5。
2. 检查DLL存在性、ACL和附加文件流，未发现普通文件权限或下载阻止标记问题。
3. 在项目工作区创建全新venv，避免复用原runtime的site-packages。
4. 从PyTorch官方CPU索引安装`torch 2.13.0+cpu`，排除CUDA wheel不匹配。
5. 在新路径再次执行`import torch`，仍由`torch_python.dll`返回WinError 5。
6. 分别加载Torch核心DLL，确认只有`torch_python.dll`被拒绝。

未尝试且明确禁止：修改系统ACL、关闭安全软件、修改WDAC/AppLocker策略、替换系统DLL或在代码中写死本机路径。

## 5. 独立验证方式

验证脚本：`backend/scripts/validate_real_bge_environment.py`。脚本不导入`app`，不会访问Agent、Workflow或API，也没有fallback。

在具备正常DLL执行权限和网络/模型缓存的独立终端运行：

```powershell
cd backend
python -m venv .bge-c3a-venv
.\.bge-c3a-venv\Scripts\python.exe -m pip install --index-url https://download.pytorch.org/whl/cpu torch
.\.bge-c3a-venv\Scripts\python.exe -m pip install sentence-transformers
.\.bge-c3a-venv\Scripts\python.exe scripts\validate_real_bge_environment.py --cache-dir .bge-model-cache
```

已预先下载模型时可加`--local-files-only`。只有脚本输出`status: passed`，并同时满足`modelDimension=512`、`vectorDimension=512`及`profileMatches=true`，才算真实BGE验证通过。

本环境实测：

```text
status: blocked
failedStage: import_torch
error: PermissionError [WinError 5] on torch_python.dll
exit code: 2
```

## 6. 最终验证结果

结论：`blocked`。

- 真实BGE未能加载。
- 未产生512维真实BGE向量，因此不能声称与EmbeddingProfile完成运行时一致性验证。
- 未调用hash fallback，也未把任何fallback结果标记为BGE。
- 阻塞发生在Torch导入阶段，早于SentenceTransformer和模型权重加载。

建议下一步在非Codex沙箱的普通Windows终端或CI runner中运行同一脚本，并保留JSON输出。如果非沙箱环境通过，则可确认问题属于当前执行策略；若仍失败，再结合Windows事件查看器中的Code Integrity/AppLocker日志定位具体拦截策略。
