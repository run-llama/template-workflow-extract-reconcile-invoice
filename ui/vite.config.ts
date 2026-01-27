import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

// https://vitejs.dev/config/
export default defineConfig(({}) => {
  const deploymentName = process.env.LLAMA_DEPLOY_DEPLOYMENT_NAME;
  const basePath = process.env.LLAMA_DEPLOY_DEPLOYMENT_BASE_PATH;
  const projectId = process.env.LLAMA_DEPLOY_PROJECT_ID;
  const port = process.env.PORT ? Number(process.env.PORT) : 3000;
  const serverPort = process.env.LLAMA_DEPLOY_SERVER_PORT;
  const baseUrl = process.env.LLAMA_CLOUD_BASE_URL;
  return {
    plugins: [react()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
    server: {
      port: port,
      host: true,
      hmr: {
        port: port,
        clientPort: serverPort ? parseInt(serverPort) : undefined,
      },
    },
    build: {
      outDir: "dist",
      sourcemap: true,
    },
    base: basePath,
    define: {
      // Primary define uses NAME
      "import.meta.env.VITE_LLAMA_DEPLOY_DEPLOYMENT_NAME": JSON.stringify(
        deploymentName
      ),
      "import.meta.env.VITE_LLAMA_DEPLOY_DEPLOYMENT_BASE_PATH": JSON.stringify(basePath),
      ...(projectId && {
        "import.meta.env.VITE_LLAMA_DEPLOY_PROJECT_ID":
          JSON.stringify(projectId),
      }),
      ...(baseUrl && {
        "import.meta.env.VITE_LLAMA_CLOUD_BASE_URL": JSON.stringify(baseUrl),
      }),
    },
  };
});
