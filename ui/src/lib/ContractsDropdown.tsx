import { useState, useEffect, useCallback } from "react";
import {
  paginatedListPipelineDocumentsApiV1PipelinesPipelineIdDocumentsPaginatedGet,
  deletePipelineDocumentApiV1PipelinesPipelineIdDocumentsDocumentIdDelete,
  readFileContentApiV1FilesIdContentGet,
} from "llama-cloud-services/api";
import {
  Button,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
  ScrollArea,
} from "@llamaindex/ui";
import type { CloudDocument } from "llama-cloud-services/api";
import { Trash2, ChevronDown, Loader2 } from "lucide-react";
import { useMetadata } from "./useMetadata";

const LIMIT = 20;

interface UseContractsLoaderResult {
  contracts: CloudDocument[];
  total: number | null;
  loading: boolean;
  hasMore: boolean;
  loadMore: () => void;
  handleScroll: (event: React.UIEvent<HTMLDivElement>) => void;
  removeContract: (id: string) => void;
}

function useContractsLoader(
  pipelineId: string | undefined,
  isOpen: boolean,
): UseContractsLoaderResult {
  const [contracts, setContracts] = useState<CloudDocument[]>([]);
  const [total, setTotal] = useState<number | null>(null);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);
  const [hasMore, setHasMore] = useState(true);

  const loadContracts = useCallback(
    async (reset = false) => {
      if (!pipelineId || loading) return;

      setLoading(true);
      try {
        const currentOffset = reset ? 0 : offset;
        const response =
          await paginatedListPipelineDocumentsApiV1PipelinesPipelineIdDocumentsPaginatedGet(
            {
              path: {
                pipeline_id: pipelineId,
              },
              query: {
                offset: currentOffset,
                limit: LIMIT,
              },
            },
          );

        if (response.data) {
          setTotal(response.data.total_count);
          setContracts((prev) =>
            reset
              ? response.data!.documents
              : [...prev, ...response.data!.documents],
          );
          setOffset(currentOffset + response.data.documents.length);
          setHasMore(
            currentOffset + response.data.documents.length <
              response.data.total_count,
          );
        }
      } catch (error) {
        console.error("Failed to load contracts:", error);
      } finally {
        setLoading(false);
      }
    },
    [pipelineId, offset, loading],
  );

  useEffect(() => {
    if (isOpen && pipelineId && contracts.length === 0) {
      loadContracts(true);
    }
  }, [isOpen, pipelineId]);

  const handleScroll = useCallback(
    (event: React.UIEvent<HTMLDivElement>) => {
      if (!hasMore || loading) return;

      const target = event.currentTarget;
      const { scrollTop, scrollHeight, clientHeight } = target;
      if (scrollTop + clientHeight >= scrollHeight - 50) {
        loadContracts();
      }
    },
    [hasMore, loading, loadContracts],
  );

  const removeContract = useCallback((id: string) => {
    setContracts((prev) => prev.filter((doc) => doc.id !== id));
    setTotal((prev) => (prev !== null ? prev - 1 : null));
  }, []);

  return {
    contracts,
    total,
    loading,
    hasMore,
    loadMore: loadContracts,
    handleScroll,
    removeContract,
  };
}

interface UseDeleteContractResult {
  deleteConfirmId: string | null;
  deletingId: string | null;
  showDeleteConfirm: (id: string) => void;
  cancelDelete: () => void;
  confirmDelete: (id: string) => Promise<void>;
}

function useDeleteContract(
  pipelineId: string | undefined,
  onSuccess?: () => void,
): UseDeleteContractResult {
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const confirmDelete = useCallback(
    async (documentId: string) => {
      if (!pipelineId) return;

      setDeletingId(documentId);
      try {
        await deletePipelineDocumentApiV1PipelinesPipelineIdDocumentsDocumentIdDelete(
          {
            path: {
              pipeline_id: pipelineId,
              document_id: documentId,
            },
          },
        );

        setDeleteConfirmId(null);
        onSuccess?.();
      } catch (error) {
        console.error("Failed to delete contract:", error);
        alert("Failed to delete contract. Please try again.");
      } finally {
        setDeletingId(null);
      }
    },
    [pipelineId, onSuccess],
  );

  return {
    deleteConfirmId,
    deletingId,
    showDeleteConfirm: setDeleteConfirmId,
    cancelDelete: () => setDeleteConfirmId(null),
    confirmDelete,
  };
}

interface ContractsDropdownProps {
  onDeleteSuccess?: () => void;
}

export function ContractsDropdown({ onDeleteSuccess }: ContractsDropdownProps) {
  const { metadata, loading: metadataLoading } = useMetadata();
  const [isOpen, setIsOpen] = useState(false);

  const { contracts, total, loading, handleScroll, removeContract } =
    useContractsLoader(metadata?.contracts_pipeline_id, isOpen);

  const {
    deleteConfirmId,
    deletingId,
    showDeleteConfirm,
    cancelDelete,
    confirmDelete,
  } = useDeleteContract(metadata?.contracts_pipeline_id, onDeleteSuccess);

  const handleDelete = async (documentId: string) => {
    await confirmDelete(documentId);
    removeContract(documentId);
  };

  const handleDownload = async (contract: CloudDocument) => {
    const fileId = contract.metadata?.file_id as string;
    if (!fileId) {
      console.error("No file_id found in contract metadata");
      alert("Cannot download: file information not available");
      return;
    }

    try {
      const response = await readFileContentApiV1FilesIdContentGet({
        path: { id: fileId },
      });

      if (response.data?.url) {
        // Create a temporary link and trigger download
        const link = document.createElement("a");
        link.href = response.data.url;
        link.download = (contract.metadata?.filename as string) || "contract";
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      }
    } catch (error) {
      console.error("Failed to download contract:", error);
      alert("Failed to download contract. Please try again.");
    }
  };

  if (metadataLoading) {
    return null;
  }

  return (
    <DropdownMenu open={isOpen} onOpenChange={setIsOpen}>
      <DropdownMenuTrigger asChild>
        <Button
          variant="default"
          size="icon"
          className="cursor-pointer bg-black hover:bg-black/90 text-white"
          aria-label="View contracts"
        >
          <ChevronDown className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>

      <DropdownMenuContent className="w-96" align="end">
        {total !== null && (
          <>
            <div className="px-2 py-1.5 text-sm font-semibold">
              Total Contracts: {total}
            </div>
            <DropdownMenuSeparator />
          </>
        )}

        <ScrollArea className="h-96" onScrollCapture={handleScroll}>
          {contracts.length === 0 && !loading ? (
            <div className="p-4 text-center text-sm text-muted-foreground">
              No contracts found
            </div>
          ) : (
            <div>
              {contracts.map((contract, index) => (
                <div key={contract.id}>
                  {deleteConfirmId === contract.id ? (
                    <div className="flex flex-col gap-2 px-4 py-3 bg-accent/50">
                      <p className="text-sm font-medium">
                        Delete "
                        {(contract.metadata?.filename as string) || "Untitled"}
                        "?
                      </p>
                      <div className="flex items-center gap-2">
                        <Button
                          onClick={() => handleDelete(contract.id)}
                          disabled={deletingId === contract.id}
                          variant="destructive"
                          size="sm"
                          className="flex-1 cursor-pointer"
                          aria-label={`Confirm delete ${(contract.metadata?.filename as string) || "Untitled"}`}
                        >
                          {deletingId === contract.id
                            ? "Deleting..."
                            : "Confirm"}
                        </Button>
                        <Button
                          onClick={cancelDelete}
                          disabled={deletingId === contract.id}
                          variant="outline"
                          size="sm"
                          className="flex-1 cursor-pointer"
                          aria-label="Cancel delete"
                        >
                          Cancel
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <div className="flex items-center justify-between gap-2 px-2 py-2 hover:bg-accent group">
                      <button
                        className="flex-1 min-w-0 cursor-pointer px-2 py-1 text-left bg-transparent border-none outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 rounded"
                        onClick={() => handleDownload(contract)}
                        aria-label={`Download ${(contract.metadata?.filename as string) || "Untitled"}`}
                        type="button"
                      >
                        <p className="text-sm font-medium truncate group-hover:text-primary">
                          {(contract.metadata?.filename as string) ||
                            "Untitled"}
                        </p>
                      </button>

                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 flex-shrink-0 text-muted-foreground hover:text-destructive cursor-pointer"
                        onClick={(e) => {
                          e.stopPropagation();
                          showDeleteConfirm(contract.id);
                        }}
                        aria-label={`Delete ${(contract.metadata?.filename as string) || "Untitled"}`}
                        type="button"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  )}
                  {index < contracts.length - 1 && <DropdownMenuSeparator />}
                </div>
              ))}
            </div>
          )}

          {loading && (
            <div className="flex justify-center items-center gap-2 p-4 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>Loading...</span>
            </div>
          )}
        </ScrollArea>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
