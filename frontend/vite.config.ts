import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({plugins:[react()],optimizeDeps:{include:['@react-three/fiber','@react-three/drei/core/CameraControls','three']},server:{port:5173,proxy:{'/api':{target:'http://127.0.0.1:8000',changeOrigin:false}}}});
