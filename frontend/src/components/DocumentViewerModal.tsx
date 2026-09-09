'use client';
import React from 'react';
import { X, Download, RefreshCw, FileText, CheckCircle2, AlertCircle, ShieldCheck } from 'lucide-react';
import { useDocumentExtractedFields, useReprocessDocument } from '@/lib/api-client';

interface DocumentViewerModalProps {
  isOpen: boolean;
  onClose: () => void;
  document: {
    id: string;
    file_name: string;
    type: string;
    mime_type: string;
    size_bytes: number;
    ocr_status: string;
  } | null;
}

export const DocumentViewerModal: React.FC<DocumentViewerModalProps> = ({
  isOpen,
  onClose,
  document,
}) => {
  const { data: extractedFields, isLoading: isFieldsLoading } = useDocumentExtractedFields(document?.id);
  const reprocessMutation = useReprocessDocument();

  if (!isOpen || !document) return null;

  const isPdf = document.mime_type.includes('pdf') || document.file_name.toLowerCase().endsWith('.pdf');
  const isImage = document.mime_type.includes('image') || /\.(jpg|jpeg|png|webp)$/i.test(document.file_name);
  const previewUrl = `/api/v1/documents/${document.id}/preview`;
  const downloadUrl = `/api/v1/documents/${document.id}/download`;

  const handleReprocess = async () => {
    try {
      await reprocessMutation.mutateAsync(document.id);
      alert('Document queued for OCR re-extraction.');
    } catch (err: any) {
      alert('Failed to reprocess: ' + (err?.response?.data?.detail || err.message));
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-md animate-fade-in">
      <div className="glass-panel w-full max-w-5xl h-[85vh] p-6 relative border border-slate-700 shadow-2xl bg-slate-950 text-slate-100 rounded-2xl flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-slate-800 shrink-0">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
              <FileText className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white flex items-center gap-2">
                <span>{document.file_name}</span>
                <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700">
                  {document.type}
                </span>
                <span className={`text-xs px-2 py-0.5 rounded-full font-bold ${
                  document.ocr_status === 'COMPLETED'
                    ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                    : 'bg-amber-500/10 text-amber-400 border border-amber-500/30'
                }`}>
                  {document.ocr_status}
                </span>
              </h2>
              <p className="text-xs text-slate-400">
                {(document.size_bytes / 1024).toFixed(1)} KB • {document.mime_type}
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={handleReprocess}
              disabled={reprocessMutation.isPending}
              className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold flex items-center gap-1.5 transition-colors"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${reprocessMutation.isPending ? 'animate-spin' : ''}`} />
              <span>Reprocess OCR</span>
            </button>

            <a
              href={downloadUrl}
              download={document.file_name}
              className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center gap-1.5 transition-colors shadow-md"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Download</span>
            </a>

            <button
              onClick={onClose}
              className="p-2 text-slate-400 hover:text-white rounded-lg bg-slate-800/50 hover:bg-slate-800 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Content Body: Split Preview + Extracted Fields */}
        <div className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-4 pt-4 overflow-hidden">
          {/* Document Preview Frame */}
          <div className="lg:col-span-2 bg-slate-900/60 rounded-xl border border-slate-800 overflow-hidden flex items-center justify-center relative">
            {isPdf ? (
              <iframe
                src={previewUrl}
                className="w-full h-full border-0 rounded-xl"
                title={document.file_name}
              />
            ) : isImage ? (
              <div className="w-full h-full p-4 flex items-center justify-center overflow-auto">
                <img
                  src={previewUrl}
                  alt={document.file_name}
                  className="max-h-full max-w-full object-contain rounded-lg shadow-lg"
                />
              </div>
            ) : (
              <div className="text-center p-8 text-xs text-slate-400">
                <FileText className="w-12 h-12 mx-auto mb-2 text-slate-600" />
                <span>Binary preview not supported for this file type. Please use the Download button.</span>
              </div>
            )}
          </div>

          {/* Extracted Fields Panel */}
          <div className="bg-slate-900/60 rounded-xl border border-slate-800 p-4 flex flex-col overflow-hidden">
            <h3 className="text-xs font-bold text-white uppercase tracking-wider mb-3 flex items-center gap-1.5">
              <ShieldCheck className="w-4 h-4 text-indigo-400" />
              <span>Extracted Fields & OCR Provenance</span>
            </h3>

            <div className="flex-1 overflow-y-auto space-y-2.5 pr-1">
              {isFieldsLoading ? (
                <div className="text-center py-8 text-xs text-slate-500">
                  <RefreshCw className="w-4 h-4 animate-spin mx-auto mb-2" />
                  Loading extracted data...
                </div>
              ) : extractedFields && extractedFields.length > 0 ? (
                extractedFields.map((f: any) => (
                  <div
                    key={f.id}
                    className="p-3 rounded-lg bg-slate-950/80 border border-slate-800 space-y-1"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] font-semibold text-indigo-300 font-mono">
                        {f.field_name}
                      </span>
                      <span className={`text-[10px] px-1.5 py-0.5 rounded font-bold ${
                        f.validation_status === 'PASS' || f.validation_status === 'VALID'
                          ? 'bg-emerald-500/10 text-emerald-400'
                          : 'bg-amber-500/10 text-amber-400'
                      }`}>
                        {f.validation_status}
                      </span>
                    </div>

                    <div className="text-xs text-white font-medium break-all">
                      {f.field_value || <span className="text-slate-500 italic">None</span>}
                    </div>

                    <div className="flex items-center justify-between pt-1 text-[10px] text-slate-400 border-t border-slate-900">
                      <span>OCR: {f.ocr_confidence ? `${Math.round(f.ocr_confidence * 100)}%` : 'N/A'}</span>
                      <span>Extraction: {f.extraction_confidence ? `${Math.round(f.extraction_confidence * 100)}%` : 'N/A'}</span>
                      <span className="text-indigo-400 font-semibold">
                        Final: {f.final_confidence ? `${Math.round(f.final_confidence * 100)}%` : 'N/A'}
                      </span>
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-center py-12 text-xs text-slate-500">
                  No extracted fields found for this document yet. Click "Reprocess OCR" if extraction is pending.
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
