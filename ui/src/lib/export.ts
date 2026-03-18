import type { AgentDataItem, ExtractedData } from "@llamaindex/ui";

export function downloadJSON<T>(
  data: T,
  filename: string = "extraction-results.json",
) {
  const jsonString = JSON.stringify(data, null, 2);
  const blob = new Blob([jsonString], { type: "application/json" });
  const url = URL.createObjectURL(blob);

  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();

  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

export function downloadExtractedDataItem(item: AgentDataItem) {
  const extractedData = item.data as ExtractedData<unknown>;
  const fileName = extractedData.file_name || "item";
  const timestamp = item.created_at
    ? new Date(item.created_at).toISOString().split("T")[0]
    : new Date().toISOString().split("T")[0];
  const filename = `${fileName}-${timestamp}.json`;

  downloadJSON(item, filename);
}
