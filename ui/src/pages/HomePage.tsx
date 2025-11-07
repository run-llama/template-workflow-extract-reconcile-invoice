import {
  ItemCount,
  WorkflowTrigger,
  WorkflowProgressBar,
  ExtractedDataItemGrid,
  useWorkflowHandlerList,
} from "@llamaindex/ui";
import type { TypedAgentData } from "llama-cloud-services/beta/agent";
import styles from "./HomePage.module.css";
import { useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";

export default function HomePage() {
  const { taskKey } = taskCompletedState();
  return <TaskList key={taskKey} />;
}

/**
 * Returns a key that increments when a task is completed, can be used to force a re-render of the task list
 */
function taskCompletedState() {
  const { handlers } = useWorkflowHandlerList("process-file");
  const runningTasks = handlers.filter(
    (handler) => handler.status === "running",
  );
  const [runningTaskCount, setRunningTaskCount] = useState(runningTasks.length);
  const [taskKey, setTaskKey] = useState(0);
  useEffect(() => {
    if (runningTasks.length < runningTaskCount) {
      // forcefully reload task list after a task is completed
      setTaskKey(taskKey + 1);
    }
    setRunningTaskCount(runningTasks.length);
  }, [runningTasks.length]);
  return { runningTaskCount, taskKey };
}

function TaskList() {
  const navigate = useNavigate();
  const goToItem = (item: TypedAgentData) => {
    navigate(`/item/${item.id}`);
  };
  return (
    <div className={styles.page}>
      <main className={styles.main}>
        <div className={styles.grid}>
          <ItemCount title="Total Items" />
          <ItemCount
            title="Reviewed"
            filter={{
              status: { eq: "approved" },
            }}
          />
          <ItemCount
            title="Needs Review"
            filter={{
              status: { eq: "pending_review" },
            }}
          />
        </div>
        <div className={styles.commandBar}>
          <WorkflowTrigger
            workflowName="process-file"
            customWorkflowInput={(files) => {
              return {
                file_id: files[0].fileId,
              };
            }}
            title="Upload Invoice"
          />
          <WorkflowTrigger
            workflowName="index-contract"
            customWorkflowInput={(files) => {
              return {
                file_id: files[0].fileId,
              };
            }}
            title="Upload Contract"
          />
        </div>
        <WorkflowProgressBar
          className={styles.progressBar}
          workflowName="process-file"
        />
        <ExtractedDataItemGrid
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
