import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import type { Highlight } from "@llamaindex/ui";
import type { FieldCitation } from "llama-cloud-services/beta/agent";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function convertBoundingBoxesToHighlights(
  citations: FieldCitation[] | undefined,
): Highlight[] {
  if (!citations || citations.length === 0) return [];

  const highlights: Highlight[] = [];

  for (const citation of citations) {
    const page = citation.page ?? 1;
    const boundingBoxes = citation.bounding_boxes;

    if (boundingBoxes && boundingBoxes.length > 0) {
      for (const bbox of boundingBoxes) {
        highlights.push({
          page,
          x: bbox.x,
          y: bbox.y,
          width: bbox.w,
          height: bbox.h,
        });
      }
    } else if (citation.page !== undefined) {
      highlights.push({
        page,
        x: 0,
        y: 0,
        width: 0,
        height: 0,
      });
    }
  }

  return highlights;
}
