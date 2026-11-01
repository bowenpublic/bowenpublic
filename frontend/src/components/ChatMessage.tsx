'use client';

import ReactMarkdown from 'react-markdown';
import { FileText, Image as ImageIcon } from 'lucide-react';
import Image from 'next/image';
import { Message } from '@/types';
import { Sources } from './Sources';

interface ChatMessageProps {
  message: Message;
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user';

  // Don't render empty assistant messages (streaming placeholder before first token)
  if (!isUser && !message.content) return null;

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[85%] md:max-w-[75%] ${
          isUser
            ? 'text-white rounded-2xl rounded-br-sm'
            : 'bg-white border border-slate-200 rounded-2xl rounded-bl-sm'
        } p-4`}
        style={isUser ? {background: 'linear-gradient(to bottom right, #DC602E, #2d2d44)'} : undefined}
      >
        {!isUser && (
          <div className="flex items-center gap-2 mb-3 pb-2 border-b border-slate-100">
            <Image src="/logo-mark.png" alt="" width={24} height={24} className="w-6 h-6" />
            <span className="bowen-brand text-xs text-slate-500">Bowen</span>
          </div>
        )}

        <div
          className={`prose prose-sm max-w-none ${
            isUser
              ? 'prose-invert'
              : 'prose-slate prose-headings:text-primary prose-a:text-blue-600'
          }`}
        >
          {isUser ? (
            <p className="m-0">{message.content}</p>
          ) : (
            <ReactMarkdown>{message.content}</ReactMarkdown>
          )}
        </div>

        {/* Attachment badges for user messages */}
        {isUser && message.attachments && message.attachments.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-2 pt-2 border-t border-white/20">
            {message.attachments.map((att, i) => (
              <span
                key={i}
                className="inline-flex items-center gap-1 text-xs bg-white/20 rounded px-2 py-0.5"
              >
                {att.content_type === 'application/pdf' ? (
                  <FileText className="w-3 h-3" />
                ) : (
                  <ImageIcon className="w-3 h-3" />
                )}
                <span className="truncate max-w-[100px]">{att.filename}</span>
              </span>
            ))}
          </div>
        )}

        {!isUser && message.sources && <Sources sources={message.sources} />}
      </div>
    </div>
  );
}
