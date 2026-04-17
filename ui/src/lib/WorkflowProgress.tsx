import {
  useHandlers,
  WorkflowEvent,
  StreamOperation,
  HandlerState,
} from "@llamaindex/ui";
import { useEffect, useMemo, useRef, useState } from "react";
import { Loader2, X } from "lucide-react";
import { cn } from "./utils";

interface StatusMessage {
  type: "Status";
  data: {
    level: "info" | "warning" | "error";
    message: string;
  };
}

type FailedHandler = {
  handler_id: string;
  error: string;
  started_at: string;
};

/**
 * Tracks running handlers for a workflow and surfaces any that fail in this
 * session as dismissible cards. Without this, a pipeline crash before the
 * agent_data write is completely invisible in the UI.
 */
export const WorkflowProgress = ({
  workflowName,
  onWorkflowCompletion,
  handlers = [],
  sync = true,
}: {
  workflowName: string[];
  onWorkflowCompletion?: (handlerIds: string[]) => void;
  handlers?: HandlerState[];
  sync?: boolean;
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
  const [dismissed, setDismissed] = useState<Set<string>>(() => new Set());
  // useHandlers syncs to `status: ["running"]` and evicts terminal handlers,
  // so failed handlers have to be snapshotted locally on SSE onError.
  const [failed, setFailed] = useState<Map<string, FailedHandler>>(
    () => new Map(),
  );

  const allHandlers = Object.values(handlersService.state.handlers);
  const runningHandlers = allHandlers.filter(
    (handler) => handler.status === "running",
  );
  const failedHandlers = useMemo(
    () =>
      Array.from(failed.values())
        .filter((h) => !dismissed.has(h.handler_id))
        .sort(
          (a, b) =>
            new Date(b.started_at).getTime() - new Date(a.started_at).getTime(),
        ),
    [failed, dismissed],
  );

  const runningHandlersKey = runningHandlers
    .map((handler) => handler.handler_id)
    .sort()
    .join(",");
  // subscribe to all running handlers and disconnect when they complete
  useEffect(() => {
    for (const handler of runningHandlers) {
      if (!subscribed.current[handler.handler_id]) {
        const handlerId = handler.handler_id;
        const startedAt = handler.started_at;
        subscribed.current[handlerId] = handlersService
          .actions(handlerId)
          .subscribeToEvents({
            onError(error) {
              // SSE onError is the only reliable terminal signal for a failed
              // handler: GET /handlers/{id} returns 500 for failed handlers,
              // so sync() cannot retrieve the state.
              setFailed((prev) => {
                if (prev.has(handlerId)) return prev;
                const next = new Map(prev);
                next.set(handlerId, {
                  handler_id: handlerId,
                  error: error.message,
                  started_at: startedAt,
                });
                return next;
              });
              subscribed.current[handlerId]?.disconnect();
              delete subscribed.current[handlerId];
            },
            onComplete() {
              subscribed.current[handlerId]?.disconnect();
              delete subscribed.current[handlerId];
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

  const dismiss = (handlerId: string) => {
    setDismissed((prev) => {
      const next = new Set(prev);
      next.add(handlerId);
      return next;
    });
  };

  const showProgressPill = runningHandlers.length > 0 || hasHadRunning;

  if (!showProgressPill && failedHandlers.length === 0) {
    return null;
  }
  return (
    <div className="flex flex-col gap-2 w-full">
      {showProgressPill && (
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
      )}
      {failedHandlers.map((handler) => (
        <div
          key={handler.handler_id}
          data-testid="workflow-failure-card"
          className="relative w-full rounded-md border border-red-300 dark:border-red-900 bg-red-50 dark:bg-red-950 px-3 py-2 text-xs text-red-900 dark:text-red-100 flex items-start gap-2 shadow-sm"
        >
          <div className="flex-1 min-w-0">
            <div className="font-medium">Workflow failed</div>
            <div className="mt-0.5 break-words opacity-90">
              {handler.error || "No error message available."}
            </div>
          </div>
          <button
            type="button"
            aria-label="Dismiss error"
            className="shrink-0 opacity-60 hover:opacity-100 transition"
            onClick={() => dismiss(handler.handler_id)}
          >
            <X className="h-3.5 w-3.5" aria-hidden="true" />
          </button>
        </div>
      ))}
    </div>
  );
};
