import {
  useHandlers,
  WorkflowEvent,
  StreamOperation,
  HandlerState,
} from "@llamaindex/ui";
import { useEffect, useRef, useState } from "react";
import { Loader2 } from "lucide-react";
import { cn } from "./utils";

interface StatusMessage {
  type: "Status";
  data: {
    level: "info" | "warning" | "error";
    message: string;
  };
}
/**
 * Given a workflow type, keeps track of the number of running handlers and the maximum number of running handlers.
 * Has hooks to notify when a workflow handler is completed.
 */
export const WorkflowProgress = ({
  workflowName,
  onWorkflowCompletion,
  handlers = [],
  sync = true,
}: {
  workflowName: string[];
  onWorkflowCompletion?: (handlerIds: string[]) => void;
  handlers?: HandlerState[]; // specific handlers to track, e.g. after triggering a workflow run
  sync?: boolean; // whether to sync the handlers with the query on mount
}) => {
  const handlersService = useHandlers({
    query: { workflow_name: workflowName, status: ["running"] },
    sync: sync,
  });
  const seenHandlers = useRef<Set<string>>(new Set());
  useEffect(() => {
    for (const handler of handlers) {
      if (!seenHandlers.current.has(handler.handler_id)) {
        seenHandlers.current.add(handler.handler_id);
        handlersService.setHandler(handler);
      }
    }
  }, [handlers, handlersService]);

  const subscribed = useRef<Record<string, StreamOperation<WorkflowEvent>>>({});

  const [statusMessage, setStatusMessage] = useState<
    StatusMessage["data"] | undefined
  >();
  const [statusVisible, setStatusVisible] = useState(false);
  const hideTimerRef = useRef<number | undefined>(undefined);
  const clearTimerRef = useRef<number | undefined>(undefined);
  const [hasHadRunning, setHasHadRunning] = useState(false);

  const runningHandlers = Object.values(handlersService.state.handlers).filter(
    (handler) => handler.status === "running",
  );
  const runningHandlersKey = runningHandlers
    .map((handler) => handler.handler_id)
    .sort()
    .join(",");
  // subscribe to all running handlers and disconnect when they complete
  useEffect(() => {
    for (const handler of runningHandlers) {
      if (!subscribed.current[handler.handler_id]) {
        handlersService.actions(handler.handler_id).subscribeToEvents({
          onComplete() {
            subscribed.current[handler.handler_id]?.disconnect();
            delete subscribed.current[handler.handler_id];
          },
          onData(data) {
            if (data.type === "Status") {
              setStatusMessage(data.data as StatusMessage["data"]);
            }
          },
        });
      }
    }
  }, [runningHandlersKey]);
  const lastHandlers = useRef<string[]>([]);
  useEffect(() => {
    const newRunningHandlers = runningHandlers.map(
      (handler) => handler.handler_id,
    );
    const anyRemoved = lastHandlers.current.some(
      (handler) => !newRunningHandlers.includes(handler),
    );
    if (anyRemoved) {
      onWorkflowCompletion?.(lastHandlers.current);
    }
    lastHandlers.current = newRunningHandlers;
  }, [runningHandlersKey]);

  // unsubscribe on unmount
  useEffect(() => {
    return () => {
      for (const [key, handler] of Object.entries(subscribed.current)) {
        handler.disconnect();
        delete subscribed.current[key];
      }
      if (hideTimerRef.current !== undefined) {
        clearTimeout(hideTimerRef.current);
        hideTimerRef.current = undefined;
      }
      if (clearTimerRef.current !== undefined) {
        clearTimeout(clearTimerRef.current);
        clearTimerRef.current = undefined;
      }
    };
  }, []);

  // Animate in on new messages and auto-hide after 15s
  useEffect(() => {
    if (!statusMessage) {
      return;
    }
    if (hideTimerRef.current !== undefined) {
      clearTimeout(hideTimerRef.current);
      hideTimerRef.current = undefined;
    }
    if (clearTimerRef.current !== undefined) {
      clearTimeout(clearTimerRef.current);
      clearTimerRef.current = undefined;
    }
    setStatusVisible(false);
    requestAnimationFrame(() => {
      setStatusVisible(true);
    });
    hideTimerRef.current = window.setTimeout(() => {
      setStatusVisible(false);
      clearTimerRef.current = window.setTimeout(() => {
        setStatusMessage(undefined);
      }, 300);
    }, 15000);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusMessage?.level, statusMessage?.message]);

  // Track if we've ever had any running workflows in this session
  useEffect(() => {
    if (runningHandlers.length > 0 && !hasHadRunning) {
      setHasHadRunning(true);
    }
  }, [runningHandlers.length, hasHadRunning]);

  if (!runningHandlers.length && !hasHadRunning) {
    return null;
  }
  return (
    <div className="relative w-full rounded-full bg-muted text-muted-foreground border border-border px-4 py-2 flex items-center gap-1 text-xs overflow-hidden shadow-sm">
      <span
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 rounded-full z-0 [box-shadow:inset_0_1px_0_rgba(255,255,255,0.6)] dark:[box-shadow:inset_0_1px_0_rgba(0,0,0,0.35)]"
      />
      <span
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 rounded-full z-0 opacity-60 dark:opacity-25 [background:linear-gradient(to_bottom,rgba(255,255,255,0.55),rgba(255,255,255,0.15))] dark:[background:linear-gradient(to_bottom,rgba(255,255,255,0.08),rgba(255,255,255,0.02))]"
      />
      <div className="relative z-10 flex items-center gap-1">
        {runningHandlers.length > 0 ? (
          <>
            <Loader2
              className="h-3 w-3 animate-spin shrink-0"
              aria-hidden="true"
            />
            <span>
              {runningHandlers.length} running workflow
              {runningHandlers.length === 1 ? "" : "s"}
            </span>
          </>
        ) : (
          <span>all workflows completed</span>
        )}
        {statusMessage && (
          <span
            className={cn(
              "ml-2 transition-all duration-300",
              statusVisible
                ? "opacity-100 translate-x-0"
                : "opacity-0 translate-x-2",
              statusMessage.level === "error"
                ? "text-red-500"
                : statusMessage.level === "warning"
                  ? "text-yellow-600"
                  : undefined,
            )}
          >
            {statusMessage.message}
          </span>
        )}
      </div>
    </div>
  );
};
