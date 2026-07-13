import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
    // 强制 React 单实例，修复 @react-three/fiber 预打包导致的 "Invalid hook call"
    dedupe: ['react', 'react-dom'],
  },
  optimizeDeps: {
    include: [
      'react', 'react-dom', 'react/jsx-runtime', '@react-three/fiber', 'three',
      // 多模态重型库预打包，避免懒加载首访时 Vite 重新优化触发整页刷新
      'react-syntax-highlighter', 'mermaid', 'markmap-lib', 'markmap-view',
      'remotion', '@remotion/player',
    ],
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        // 接口 28 的 WS 路径在 /api/v1/ws/ 下，代理需支持 WebSocket 升级
        ws: true
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true
      }
    }
  }
})