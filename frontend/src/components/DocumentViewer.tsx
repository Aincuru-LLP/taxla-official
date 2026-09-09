"use client";

/**
 * Phase 11 — DocumentViewer.
 *
 * In-app preview for uploaded business documents (PAN card, Aadhaar, photo,
 * cancelled cheque, etc.). PDFs render inline via ``react-pdf``; images
 * render via plain ``<img>`` (we deliberately avoid ``next/image`` here so
 * we don't have to whitelist the API host).
 *
 * The viewer is content-agnostic — it fetches ``url`` via the existing
 * axios client so the HttpOnly auth cookie travels. Other backend streams
 * (the certificate at ``/applications/{id}/certificate``) can be plugged
 * in here without changes.
 *
 * Why a sidecar lazy-load for ``react-pdf``: pdfjs ships ~1 MB of worker
 * code. Keeping the import behind a state flag means the kanban board and
 * the login page never pay for it.
 */

import { useEffect, useState, type ReactNode } from "react";
import {
  FileText,
  Image as ImageIcon,
  Loader2,
  AlertTriangle,
} from "lucide-react";

import { cn } from "@/lib/utils";

const ACCEPTED_PDF = "application/pdf";
const ACCEPTED_IMAGE = /^image\/(png|jpe?g|webp|gif|bmp)$/i;

interface PdfPaneProps {
  url: string;
  pageNumber: number;
  onLoad?: (pages: number) => void;
}

/**
 * Lazily-loaded PDF renderer. We keep the dynamic import inside the file
 * so the rest of the app doesn't bundle pdfjs.
 */
function PdfPane({ url, pageNumber, onLoad }: PdfPaneProps) {
  const [mod, setMod] = useState<typeof import("react-pdf") | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [pageCount, setPageCount] = useState(0);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const lib = await import("react-pdf");
        const workerSrc = (
          await import("pdfjs-dist/build/pdf.worker.min.mjs?url")
        ).default;
        lib.pdfjs.GlobalWorkerOptions.workerSrc = workerSrc;
        if (!cancelled) setMod(lib);
      } catch (err) {
        if (!cancelled) {
          setLoadError(
            err instanceof Error ? err.message : "Failed to load PDF engine",
          );
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (loadError) {
    return (
      <div className="text-sm text-red-300 p-3 ring-1 ring-red-400/30 rounded-md flex items-center gap-2">
        <AlertTriangle className="w-4 h-4" /> {loadError}
      </div>
    );
  }

  if (!mod) {
    return (
      <div className="flex items-center gap-2 text-sm text-slate-400 p-4">
        <Loader2 className="w-4 h-4 animate-spin" /> Loading PDF engine…
      </div>
    );
  }

  const { Document, Page } = mod;

  return (
    <Document
      file={url}
      onLoadSuccess={(pdf: { numPages: number }) => {
        setPageCount(pdf.numPages);
        onLoad?.(pdf.numPages);
      }}
      loading={
        <div className="flex items-center gap-2 text-sm text-slate-400 p-4">
          <Loader2 className="w-4 h-4 animate-spin" /> Loading document…
        </div>
      }
      error={
        <div className="text-sm text-red-300 p-3 ring-1 ring-red-400/30 rounded-md flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" /> Failed to render PDF.
        </div>
      }
      className="flex justify-center"
    >
      <Page
        pageNumber={Math.min(Math.max(pageNumber, 1), Math.max(pageCount, 1))}
        width={600}
        renderAnnotationLayer={false}
        renderTextLayer={false}
      />
    </Document>
  );
}

export interface DocumentViewerProps {
  url: string | null;
  contentType?: string | null;
  fileName?: string | null;
  className?: string;
  /** Optional right-side caption slot (e.g. extracted data preview). */
  caption?: ReactNode;
  /** Force a specific render mode. Useful when the server didn't send a content-type. */
  forceType?: "pdf" | "image";
}

export function DocumentViewer({
  url,
  contentType,
  fileName,
  className,
  caption,
  forceType,
}: DocumentViewerProps) {
  const [page, setPage] = useState(1);
  const [pageCount, setPageCount] = useState(0);

  if (!url) {
    return (
      <div
        className={cn(
          "flex items-center justify-center text-sm text-slate-500 p-6 ring-1 ring-slate-700/40 rounded-md min-h-32",
          className,
        )}
      >
        No document uploaded.
      </div>
    );
  }

  const kind =
    forceType ??
    (contentType === ACCEPTED_PDF
      ? "pdf"
      : contentType && ACCEPTED_IMAGE.test(contentType)
        ? "image"
        : fileName?.toLowerCase().endsWith(".pdf")
          ? "pdf"
          : fileName?.match(/\.(png|jpe?g|webp|gif|bmp)$/i)
            ? "image"
            : null);

  return (
    <div className={cn("flex flex-col gap-2", className)}>
      <div className="flex items-center gap-2 text-xs text-slate-400">
        {kind === "pdf" ? (
          <FileText className="w-3.5 h-3.5" aria-hidden="true" />
        ) : (
          <ImageIcon className="w-3.5 h-3.5" aria-hidden="true" />
        )}
        <span className="truncate">{fileName ?? "document"}</span>
        {kind === "pdf" && pageCount > 1 && (
          <div className="ml-auto flex items-center gap-2">
            <button
              type="button"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              className="px-2 py-0.5 rounded bg-slate-700/50 hover:bg-slate-700 disabled:opacity-40"
            >
              Prev
            </button>
            <span className="tabular-nums">
              {page} / {pageCount}
            </span>
            <button
              type="button"
              disabled={page >= pageCount}
              onClick={() => setPage((p) => Math.min(pageCount, p + 1))}
              className="px-2 py-0.5 rounded bg-slate-700/50 hover:bg-slate-700 disabled:opacity-40"
            >
              Next
            </button>
          </div>
        )}
      </div>
      <div className="bg-slate-900/40 ring-1 ring-slate-700/40 rounded-md overflow-hidden flex items-center justify-center min-h-64">
        {kind === "pdf" && (
          <PdfPane url={url} pageNumber={page} onLoad={setPageCount} />
        )}
        {kind === "image" && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={url}
            alt={fileName ?? "Uploaded document"}
            className="max-w-full max-h-[70vh] object-contain"
          />
        )}
        {kind === null && (
          <div className="text-sm text-slate-400 p-4">
            Unsupported preview format.{" "}
            <a
              href={url}
              target="_blank"
              rel="noreferrer"
              className="text-violet-300 underline"
            >
              Open in new tab
            </a>
            .
          </div>
        )}
      </div>
      {caption}
    </div>
  );
}