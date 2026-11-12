'use client';

import { useState, useRef, FormEvent, KeyboardEvent, ChangeEvent } from 'react';
import { Send, Loader2, Paperclip, X, FileText, Image as ImageIcon } from 'lucide-react';
import { FileAttachment } from '@/types';

// The logo's gradient: the same stops, at the same angle, as public/logo-mark.png
const LOGO_GRADIENT =
  'linear-gradient(135deg, #5d78c5 0%, #ffce31 27%, #e25063 50%, #ffce31 73%, #e25063 100%)';

const ACCEPTED_TYPES = 'image/png,image/jpeg,image/gif,image/webp,application/pdf';
const MAX_FILES = 3;
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      // Strip the data URL prefix (e.g., "data:image/png;base64,")
      const base64 = result.split(',')[1];
      resolve(base64);
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

interface ChatInputProps {
  onSend: (message: string, attachments?: FileAttachment[]) => void;
  isLoading: boolean;
  placeholder?: string;
}

export function ChatInput({ onSend, isLoading, placeholder = 'Ask about NZ law...' }: ChatInputProps) {
  const [input, setInput] = useState('');
  const [attachments, setAttachments] = useState<FileAttachment[]>([]);
  const [fileError, setFileError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = async (e: ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;

    setFileError(null);

    const remaining = MAX_FILES - attachments.length;
    if (remaining <= 0) {
      setFileError(`Maximum ${MAX_FILES} files allowed`);
      return;
    }

    const newFiles = Array.from(files).slice(0, remaining);

    for (const file of newFiles) {
      if (file.size > MAX_FILE_SIZE) {
        setFileError(`${file.name} exceeds 10MB limit`);
        continue;
      }

      try {
        const data = await fileToBase64(file);
        const preview_url = file.type.startsWith('image/')
          ? URL.createObjectURL(file)
          : undefined;

        setAttachments((prev) => [
          ...prev,
          {
            filename: file.name,
            content_type: file.type,
            data,
            preview_url,
            size: file.size,
          },
        ]);
      } catch {
        setFileError(`Failed to read ${file.name}`);
      }
    }

    // Reset file input so the same file can be re-selected
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const removeAttachment = (index: number) => {
    setAttachments((prev) => {
      const removed = prev[index];
      if (removed.preview_url) URL.revokeObjectURL(removed.preview_url);
      return prev.filter((_, i) => i !== index);
    });
    setFileError(null);
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if ((!input.trim() && attachments.length === 0) || isLoading) return;
    onSend(input, attachments.length > 0 ? attachments : undefined);
    setInput('');
    // Revoke preview URLs before clearing
    attachments.forEach((a) => {
      if (a.preview_url) URL.revokeObjectURL(a.preview_url);
    });
    setAttachments([]);
    setFileError(null);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const isPdf = (type: string) => type === 'application/pdf';

  return (
    <form onSubmit={handleSubmit} className="relative">
      {/* Attachment previews */}
      {attachments.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-2 px-1">
          {attachments.map((att, i) => (
            <div
              key={`${att.filename}-${i}`}
              className="flex items-center gap-2 bg-slate-100 rounded-lg px-3 py-1.5 text-sm text-slate-700 border border-slate-200"
            >
              {isPdf(att.content_type) ? (
                <FileText className="w-4 h-4 text-red-500 flex-shrink-0" />
              ) : att.preview_url ? (
                <img
                  src={att.preview_url}
                  alt={att.filename}
                  className="w-6 h-6 rounded object-cover flex-shrink-0"
                />
              ) : (
                <ImageIcon className="w-4 h-4 text-blue-500 flex-shrink-0" />
              )}
              <span className="truncate max-w-[120px]">{att.filename}</span>
              <span className="text-slate-400 text-xs">{formatFileSize(att.size)}</span>
              <button
                type="button"
                onClick={() => removeAttachment(i)}
                className="text-slate-400 hover:text-slate-600 ml-1"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}

      {fileError && (
        <p className="text-red-500 text-xs mb-1 px-1">{fileError}</p>
      )}

      <div
        className="flex gap-3 rounded-xl p-2 shadow-lg shadow-slate-200/50"
        style={{
          // Gradient border that keeps the rounded corners: white fill clipped to the
          // padding box, logo gradient showing through the transparent border.
          border: '2px solid transparent',
          background: `linear-gradient(#fff, #fff) padding-box, ${LOGO_GRADIENT} border-box`,
        }}
      >
        {/* File attach button */}
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={isLoading || attachments.length >= MAX_FILES}
          className={`px-2 flex items-center justify-center transition-colors ${
            attachments.length >= MAX_FILES
              ? 'text-slate-300 cursor-not-allowed'
              : 'text-slate-400 hover:text-slate-600'
          }`}
          title={attachments.length >= MAX_FILES ? `Maximum ${MAX_FILES} files` : 'Attach file'}
        >
          <Paperclip className="w-5 h-5" />
        </button>

        <input
          ref={fileInputRef}
          type="file"
          accept={ACCEPTED_TYPES}
          multiple
          onChange={handleFileSelect}
          className="hidden"
        />

        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          rows={1}
          className="flex-1 resize-none bg-transparent border-none outline-none focus:outline-none focus:ring-0 px-3 py-2.5 text-slate-900 placeholder:text-slate-400 text-[15px]"
          style={{ minHeight: '44px', maxHeight: '120px' }}
          disabled={isLoading}
        />
        <button
          type="submit"
          disabled={(!input.trim() && attachments.length === 0) || isLoading}
          className={`px-5 rounded-lg font-medium transition-all flex items-center gap-2 ${
            (input.trim() || attachments.length > 0) && !isLoading
              ? 'bg-slate-600 text-white hover:bg-slate-500 hover:shadow-md rounded-xl'
              : 'bg-slate-100 text-slate-400 cursor-not-allowed'
          }`}
        >
          {isLoading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Send className="w-4 h-4" />
          )}
          <span className="hidden sm:inline">Send</span>
        </button>
      </div>
    </form>
  );
}
