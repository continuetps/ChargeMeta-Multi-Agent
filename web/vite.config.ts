import {defineConfig} from 'vite';import react from '@vitejs/plugin-react';
export default defineConfig({
  base:'/console/',
  plugins:[react()],
  server:{port:5173,proxy:{'/api':'http://127.0.0.1:8000'}},
  build:{rollupOptions:{output:{manualChunks:{react:['react','react-dom'],antd:['antd'],data:['@tanstack/react-query','axios'],icons:['lucide-react']}}}}
});
