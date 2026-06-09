import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'
import ElementPlus from 'unplugin-element-plus/vite'

export default defineConfig({
  plugins: [
    vue(),
    AutoImport({
      resolvers: [ElementPlusResolver()],
    }),
    Components({
      resolvers: [ElementPlusResolver()],
    }),
    ElementPlus({}),
  ],
  server: {
    port: 5173,
    // 端口被占用时让 vite 自动跳到下一个;启动脚本会另起一层 pick_port 兜底,
    // 这里显式声明意图,避免有人误改成 true 后导致用户启动失败
    strictPort: false,
  },
  build: {
    chunkSizeWarningLimit: 1200,
    rollupOptions: {
      onwarn(warning, warn) {
        if (
          warning.code === 'INVALID_ANNOTATION'
          && typeof warning.id === 'string'
          && warning.id.includes('@vueuse/core')
        ) {
          return
        }
        warn(warning)
      },
      output: {
        manualChunks: {
          vue: ['vue', 'vue-router'],
        },
      },
    },
  },
})
