"use client";

import { createContext, use, useRef, useState, type DragEvent, type ReactNode } from "react";
import { cn } from "@/shared/lib/utils";

const DraggingFiles = createContext(false);

/** Whether files are being dragged over the enclosing `FileDropArea` (to highlight a drop zone). */
export function useDraggingFiles() {
  return use(DraggingFiles);
}

/**
 * An area files can be dropped on (from the desktop or a file manager). It draws nothing itself:
 * a visible drop zone inside it reads `useDraggingFiles()` to light up during the drag. Only file
 * drags react: dragging text or a link inside the page does nothing.
 */
export function FileDropArea({
  onFiles,
  disabled = false,
  className,
  children,
}: {
  onFiles: (files: File[]) => void;
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
      <DraggingFiles value={dragging}>{children}</DraggingFiles>
    </div>
  );
}
