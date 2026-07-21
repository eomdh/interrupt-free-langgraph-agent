import path from 'node:path';

import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig, loadEnv } from 'vite';

// 개발 서버는 백엔드(:8000)로 프록시한다 — same-origin이라 CORS가 필요 없다.
// 운영 데모는 FastAPI가 빌드된 dist를 직접 서빙하므로, 이 프록시는 dev 전용이다.
// 백엔드 엔드포인트는 /threads/* 와 /health 뿐이다(백엔드 api.py).
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const target = env.VITE_API_URL || 'http://localhost:8000';

  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      proxy: {
        '/threads': { target, changeOrigin: true },
        '/health': { target, changeOrigin: true },
      },
    },
  };
});
