import { createContext, useContext, ReactNode, useMemo } from "react";
import { ApiProvider, ApiClients } from "@llamaindex/ui";
import { useMetadata, Metadata } from "./useMetadata";
import { createBaseWorkflowClient, createClients } from "./client";
import { Clock, XCircle } from "lucide-react";

interface MetadataContextValue {
  metadata: Metadata;
  clients: ApiClients;
}

const MetadataContext = createContext<MetadataContextValue | null>(null);

export function MetadataProvider({ children }: { children: ReactNode }) {
  const baseClients: ApiClients = useMemo(() => {
    return {
      workflowsClient: createBaseWorkflowClient(),
    } as ApiClients;
  }, []);
  return (
    <ApiProvider clients={baseClients}>
      <InnerMetadataProvider>{children}</InnerMetadataProvider>
    </ApiProvider>
  );
}

function InnerMetadataProvider({ children }: { children: ReactNode }) {
  const { metadata, loading, error } = useMetadata();
  const clients = useMemo(
    () => (metadata ? createClients(metadata) : undefined),
    [metadata],
  );

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="text-center">
          <Clock className="h-8 w-8 animate-spin mx-auto mb-2" />
          <div className="text-sm text-gray-500">Loading configuration...</div>
        </div>
      </div>
    );
  }

  if (error || !metadata || !clients) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="text-center">
          <XCircle className="h-8 w-8 text-red-500 mx-auto mb-2" />
          <div className="text-sm text-gray-500">
            Error loading configuration: {error || "Unknown error"}
          </div>
        </div>
      </div>
    );
  }

  return (
    <MetadataContext.Provider value={{ metadata, clients }}>
      <ApiProvider clients={clients}>{children}</ApiProvider>
    </MetadataContext.Provider>
  );
}

export function useMetadataContext() {
  const context = useContext(MetadataContext);
  if (!context) {
    throw new Error("useMetadataContext must be used within MetadataProvider");
  }
  return context;
}
