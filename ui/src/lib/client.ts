import {
  ApiClients,
  createWorkflowsClient,
  createWorkflowsConfig,
  configureCloudClient,
  getCloudClient,
  createAgentDataConfig,
} from "@llamaindex/ui";
import { AGENT_NAME } from "./config";
import type { Metadata } from "./useMetadata";

const platformToken = import.meta.env.VITE_LLAMA_CLOUD_API_KEY;
const apiBaseUrl = import.meta.env.VITE_LLAMA_CLOUD_BASE_URL;
const projectId = import.meta.env.VITE_LLAMA_DEPLOY_PROJECT_ID;

// Configure the cloud client
configureCloudClient({
  ...(apiBaseUrl && { baseURL: apiBaseUrl }),
  ...(platformToken && { apiKey: platformToken }),
  ...(projectId && { projectId }),
});

export function createBaseWorkflowClient(): ReturnType<
  typeof createWorkflowsClient
> {
  return createWorkflowsClient(
    createWorkflowsConfig({
      baseUrl: `/deployments/${AGENT_NAME}/`,
    }),
  );
}

export function createClients(metadata: Metadata): ApiClients {
  const workflowsClient = createBaseWorkflowClient();
  const agentDataConfig = createAgentDataConfig({
    windowUrl: typeof window !== "undefined" ? window.location.href : undefined,
    collection: metadata.extracted_data_collection,
  });

  return {
    workflowsClient,
    cloudApiClient: getCloudClient(),
    agentDataConfig,
  };
}
