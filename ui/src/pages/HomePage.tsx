import {
  ItemCount,
  WorkflowTrigger,
  ExtractedDataItemGrid,
  HandlerState,
} from "@llamaindex/ui";
import type { TypedAgentData } from "llama-cloud-services/beta/agent";
import styles from "./HomePage.module.css";
import { useNavigate } from "react-router-dom";
import { useState } from "react";
import { WorkflowProgress } from "@/lib/WorkflowProgress";

export default function HomePage() {
  return <TaskList />;
}

function TaskList() {
  const navigate = useNavigate();
  const goToItem = (item: TypedAgentData) => {
    navigate(`/item/${item.id}`);
  };
  const [reloadSignal, setReloadSignal] = useState(0);
  const [handlers, setHandlers] = useState<HandlerState[]>([]);

  return (
    <div className={styles.page}>
      <main className={styles.main}>
        <div className={styles.grid}>
          <ItemCount title="Total Items" key={`total-items-${reloadSignal}`} />
          <ItemCount
            title="Reviewed"
            filter={{
              status: { includes: ["approved", "rejected"] },
            }}
            key={`reviewed-${reloadSignal}`}
          />
          <ItemCount
            title="Needs Review"
            filter={{
              status: { eq: "pending_review" },
            }}
            key={`needs-review-${reloadSignal}`}
          />
        </div>
        <div className={styles.commandBar}>
          <WorkflowProgress
            workflowName={["process-file", "index-contract"]}
            handlers={handlers}
            onWorkflowCompletion={() => {
              setReloadSignal(reloadSignal + 1);
            }}
          />
          <WorkflowTrigger
            workflowName="process-file"
            customWorkflowInput={(files) => {
              return {
                file_id: files[0].fileId,
              };
            }}
            title="Upload Invoice"
            onSuccess={(handler) => {
              setHandlers([...handlers, handler]);
            }}
          />
          <WorkflowTrigger
            workflowName="index-contract"
            customWorkflowInput={(files) => {
              return {
                file_id: files[0].fileId,
              };
            }}
            title="Upload Contract"
            onSuccess={(handler) => {
              setHandlers([...handlers, handler]);
            }}
          />
        </div>

        <ExtractedDataItemGrid
          key={reloadSignal}
          onRowClick={goToItem}
          builtInColumns={{
            fileName: true,
            status: true,
            createdAt: true,
            itemsToReview: true,
            actions: true,
          }}
        />
      </main>
    </div>
  );
}
