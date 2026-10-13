import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: "./",
  server: {
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8507",
        changeOrigin: true,
        configure(proxy) {
          proxy.on("proxyReq", (outgoing, request) => {
            // Preserve the local API's origin contract through the development proxy.
            if (request.headers.origin === `http://${request.headers.host}`) {
              outgoing.setHeader("Origin", "http://127.0.0.1:8507");
            }
          });
        },
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: { charts: ["echarts"], react: ["react", "react-dom"] },
      },
    },
  },
});
