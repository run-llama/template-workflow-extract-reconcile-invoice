import type {
  ExtractedData,
  TypedAgentData,
} from "llama-cloud-services/beta/agent";

/**
 * Downloads data as a JSON file
 */
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

  // Cleanup
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

/**
 * Downloads extracted data item as JSON
 */
export function downloadExtractedDataItem<T>(
  item: TypedAgentData<ExtractedData<T>>,
) {
  const fileName = item.data.file_name || "item";
  const timestamp = item.createdAt.toISOString().split("T")[0];
  const filename = `${fileName}-${timestamp}.json`;

  downloadJSON(item, filename);
}
