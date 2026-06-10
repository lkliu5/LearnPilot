import { Sandpack } from '@codesandbox/sandpack-react'

/* 可运行的 JS 神经元示例（Sandpack 在浏览器内运行 web 代码）*/
const neuronJs = `// 单个神经元的前向传播：加权求和 → 加偏置 → ReLU 激活
function relu(x) { return Math.max(0, x); }

function neuron(inputs, weights, bias) {
  const z = inputs.reduce((sum, x, i) => sum + x * weights[i], 0) + bias;
  return relu(z);
}

const x = [0.5, 0.8, 0.2];   // 输入
const w = [0.4, 0.7, 0.1];   // 权重
const b = 0.1;               // 偏置

const out = neuron(x, w, b);

// 渲染到页面，直观看到每一步
document.getElementById('app').innerHTML = \`
  <div style="font-family:system-ui;padding:16px;line-height:1.8">
    <h3 style="margin:0 0 8px">🧠 神经元前向传播</h3>
    <div>输入 x = [\${x.join(', ')}]</div>
    <div>权重 w = [\${w.join(', ')}]</div>
    <div>偏置 b = \${b}</div>
    <div>加权求和 z = \${(out>0? out-b : 0).toFixed(2)} + \${b} </div>
    <div style="margin-top:8px;font-weight:700;color:#2563eb">
      输出 = ReLU(z) = \${out.toFixed(2)}
    </div>
    <p style="color:#64748b;font-size:13px;margin-top:12px">
      ✏️ 试着改改 w / b / 激活函数，左侧实时运行看结果。
    </p>
  </div>
\`;
`

const htmlIndex = `<!DOCTYPE html>
<html><head><meta charset="utf-8"/></head>
<body><div id="app"></div><script src="index.js"></script></body>
</html>`

/** 可运行代码沙箱：学习者直接跑/改神经网络代码 */
export default function CodeSandbox() {
  return (
    <Sandpack
      template="static"
      theme="auto"
      files={{
        '/index.js': neuronJs,
        '/index.html': htmlIndex,
      }}
      options={{
        showLineNumbers: true,
        showTabs: true,
        editorHeight: 420,
      }}
    />
  )
}
