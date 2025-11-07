import { ExtractedData } from "llama-cloud-services/beta/agent";
import {
  ApiClients,
  createWorkflowsClient,
  createWorkflowsConfig,
  createCloudAgentClient,
  cloudApiClient,
} from "@llamaindex/ui";
import { AGENT_NAME } from "./config";
import type { Metadata } from "./useMetadata";

const platformToken = import.meta.env.VITE_LLAMA_CLOUD_API_KEY;
const apiBaseUrl = import.meta.env.VITE_LLAMA_CLOUD_BASE_URL;
const projectId = import.meta.env.VITE_LLAMA_DEPLOY_PROJECT_ID;

// Configure the platform client
cloudApiClient.setConfig({
  ...(apiBaseUrl && { baseUrl: apiBaseUrl }),
  headers: {
    // optionally use a backend API token scoped to a project. For local development,
    ...(platformToken && { authorization: `Bearer ${platformToken}` }),
    // This header is required for requests to correctly scope to the agent's project
    // when authenticating with a user cookie
    ...(projectId && { "Project-Id": projectId }),
  },
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
  const agentClient = createCloudAgentClient<ExtractedData<any>>({
    client: cloudApiClient,
    windowUrl: typeof window !== "undefined" ? window.location.href : undefined,
    collection: metadata.extracted_data_collection,
  });

  return {
    workflowsClient,
    cloudApiClient,
    agentDataClient: agentClient,
  } as ApiClients;
}
