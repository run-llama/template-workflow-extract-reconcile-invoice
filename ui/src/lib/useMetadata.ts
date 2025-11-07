import { useWorkflowHandler, useWorkflowRun } from "@llamaindex/ui";
import { useEffect, useState } from "react";

export interface Metadata {
  json_schema: any;
  extracted_data_collection: string;
}

export interface UseMetadataResult {
  metadata: Metadata;
  loading: boolean;
  error: string | undefined;
}

export function useMetadata() {
  const run = useWorkflowRun();
  const [handlerId, setHandlerId] = useState<string | undefined>(undefined);
  const handler = useWorkflowHandler(handlerId ?? "");
  const [error, setError] = useState<string | undefined>(undefined);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    run
      .runWorkflow("metadata", {})
      .then((handlerSummary) => {
        setHandlerId(handlerSummary.handler_id);
      })
      .catch((error) => {
        setError(error.message);
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);
  const stopEvent = handler.events.find((event) =>
    event.type.endsWith("MetadataResponse"),
  );
  const metadata = stopEvent?.data as Metadata | undefined;
  return { metadata, loading, error };
}
