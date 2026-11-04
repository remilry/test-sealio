"use client";

import { useRef, useState, type DragEvent, type ReactNode } from "react";
import { UploadIcon } from "lucide-react";
import { cn } from "@/shared/lib/utils";

/**
 * An area files can be dropped on (from the desktop or a file manager). While files are dragged
 * over it, an overlay says what dropping does. Only file drags react: dragging text or a link
 * inside the page does nothing.
 */
export function FileDropArea({
  onFiles,
  overlay,
  disabled = false,
  className,
  children,
}: {
  onFiles: (files: File[]) => void;
  /** What dropping does, shown over the area during the drag. */
  overlay: string;
  disabled?: boolean;
  className?: string;
  children: ReactNode;
}) {
  const [dragging, setDragging] = useState(false);
  // dragenter / dragleave also fire on every child crossed: count them to know when it really left.
  const depth = useRef(0);

  const accepts = (event: DragEvent) => !disabled && event.dataTransfer.types.includes("Files");
  const reset = () => {
    depth.current = 0;
    setDragging(false);
  };

  return (
    <div
      className={cn("relative", className)}
      onDragEnter={(event) => {
        if (!accepts(event)) return;
        event.preventDefault();
        depth.current += 1;
        setDragging(true);
      }}
      onDragOver={(event) => {
        if (!accepts(event)) return;
        // Required for the drop to be allowed.
        event.preventDefault();
        event.dataTransfer.dropEffect = "copy";
      }}
      onDragLeave={(event) => {
        if (!accepts(event)) return;
        depth.current -= 1;
        if (depth.current <= 0) reset();
      }}
      onDrop={(event) => {
        if (!accepts(event)) return;
        // Otherwise the browser opens the file.
        event.preventDefault();
        reset();
        const files = Array.from(event.dataTransfer.files);
        if (files.length > 0) onFiles(files);
      }}
    >
      {children}
      {dragging && (
        <div
          role="status"
          className="pointer-events-none absolute inset-3 z-20 grid place-items-center rounded-xl border-2 border-dashed border-primary bg-primary/5 backdrop-blur-[1px]"
        >
          <p className="flex items-center gap-2 rounded-lg bg-card px-4 py-2.5 text-sm font-medium shadow-sm">
            <UploadIcon className="size-4 text-primary" aria-hidden />
            {overlay}
          </p>
        </div>
      )}
    </div>
  );
}
