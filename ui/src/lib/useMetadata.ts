import { useWorkflow } from "@llamaindex/ui";
import { useEffect, useRef, useState } from "react";

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
  const wf = useWorkflow("metadata");
  const [error, setError] = useState<string | undefined>(undefined);
  const [loading, setLoading] = useState(true);
  const [metadata, setMetadata] = useState<Metadata | undefined>(undefined);
  const strictModeWorkaround = useRef(false);
  useEffect(() => {
    if (strictModeWorkaround.current) {
      return;
    }
    strictModeWorkaround.current = true;
    setLoading(true);
    wf.runToCompletion({})
      .then((handler) => {
        if (handler.status === "completed") {
          const result = handler.result?.data as unknown as Metadata;
          setMetadata(result);
        } else {
          setError(
            handler.error || `Unexpected workflow status: ${handler.status}`,
          );
        }
      })
      .catch((error) => {
        setError(error instanceof Error ? error.message : String(error));
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  return { metadata, loading, error };
}
