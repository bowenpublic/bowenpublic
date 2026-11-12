'use client';

import { useState, useCallback, useMemo, useEffect } from 'react';
import { Message, FileAttachment } from '@/types';
import { sendMessageStream, clearSession as clearSessionApi } from '@/lib/api';

const SESSION_STORAGE_KEY = 'bowen-session-id';
const MESSAGES_STORAGE_KEY = 'bowen-chat-messages';

function generateSessionId(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

function getOrCreateSessionId(): string {
  if (typeof window === 'undefined') return generateSessionId();

  const stored = localStorage.getItem(SESSION_STORAGE_KEY);
  if (stored) return stored;

  const newId = generateSessionId();
  localStorage.setItem(SESSION_STORAGE_KEY, newId);
  return newId;
}

function loadStoredMessages(): Message[] {
  if (typeof window === 'undefined') return [];

  try {
    const stored = localStorage.getItem(MESSAGES_STORAGE_KEY);
    if (stored) {
      return JSON.parse(stored);
    }
  } catch (e) {
    console.warn('Failed to load stored messages:', e);
  }
  return [];
}

function saveMessages(messages: Message[]): void {
  if (typeof window === 'undefined') return;

  try {
    localStorage.setItem(MESSAGES_STORAGE_KEY, JSON.stringify(messages));
  } catch (e) {
    console.warn('Failed to save messages:', e);
  }
}

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Shown in place of the typing indicator's phrases until the first token.
  const [status, setStatus] = useState<string | null>(null);
  const [isInitialized, setIsInitialized] = useState(false);

  // Get or create session ID (persisted in localStorage)
  const sessionId = useMemo(() => getOrCreateSessionId(), []);

  // Clear stored messages and backend history on mount (fresh start on page reload)
  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.removeItem(MESSAGES_STORAGE_KEY);
      clearSessionApi(sessionId);
    }
    setIsInitialized(true);
  }, [sessionId]);

  // Save messages whenever they change (after initialization)
  useEffect(() => {
    if (isInitialized) {
      saveMessages(messages);
    }
  }, [messages, isInitialized]);

  const send = useCallback(async (content: string, attachments?: FileAttachment[]) => {
    const hasAttachments = attachments && attachments.length > 0;
    if ((!content.trim() && !hasAttachments) || isLoading) return;

    setError(null);

    // Store attachment metadata (without base64 data) for display in message history
    const attachmentMeta = attachments?.map(({ filename, content_type, size }) => ({
      filename, content_type, size,
    }));

    const userMessage: Message = {
      role: 'user',
      content,
      attachments: attachmentMeta,
    };
    setMessages(prev => [...prev, userMessage]);
    setIsLoading(true);

    // Add an empty assistant message that we'll stream into
    const assistantMessage: Message = { role: 'assistant', content: '' };
    setMessages(prev => [...prev, assistantMessage]);

    let streamFailed = false;

    try {
      await sendMessageStream(
        content,
        {
          onToken: (text) => {
            setStatus(null);
            setMessages(prev => {
              const updated = [...prev];
              const last = updated[updated.length - 1];
              if (last.role === 'assistant') {
                updated[updated.length - 1] = { ...last, content: last.content + text };
              }
              return updated;
            });
          },
          onDone: (sources, _disclaimer) => {
            setMessages(prev => {
              const updated = [...prev];
              const last = updated[updated.length - 1];
              if (last.role === 'assistant') {
                updated[updated.length - 1] = { ...last, sources };
              }
              return updated;
            });
          },
          onError: (errorMsg) => {
            streamFailed = true;
            setError(errorMsg);
          },
          onStatus: (text) => {
            setStatus(text);
          },
        },
        sessionId,
        attachments,
      );
    } catch {
      streamFailed = true;
      setError('Failed to get a response. Please check if the backend is running and try again.');
    }

    if (streamFailed) {
      // Remove user message and empty assistant message
      setMessages(prev => prev.slice(0, -2));
    }

    setStatus(null);
    setIsLoading(false);
  }, [isLoading, sessionId]);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setError(null);
    // Clear stored messages but keep session ID
    if (typeof window !== 'undefined') {
      localStorage.removeItem(MESSAGES_STORAGE_KEY);
    }
  }, []);

  const clearSession = useCallback(() => {
    setMessages([]);
    setError(null);
    // Clear everything including session ID and backend history
    if (typeof window !== 'undefined') {
      clearSessionApi(sessionId);
      localStorage.removeItem(MESSAGES_STORAGE_KEY);
      localStorage.removeItem(SESSION_STORAGE_KEY);
    }
  }, [sessionId]);

  return {
    messages,
    isLoading,
    status,
    error,
    send,
    clearMessages,
    clearSession,
    sessionId,
  };
}
