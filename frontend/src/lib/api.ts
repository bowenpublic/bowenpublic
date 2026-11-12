import { ChatResponse, Source, Act, ActsResponse, FileAttachment } from '@/types';

export interface ApiError {
  error: string;
  code: string;
  detail?: string;
  retry_after?: number;
}

export class BowenApiError extends Error {
  code: string;
  detail?: string;
  retryAfter?: number;
  statusCode: number;

  constructor(statusCode: number, errorResponse: ApiError) {
    super(errorResponse.error);
    this.name = 'BowenApiError';
    this.code = errorResponse.code;
    this.detail = errorResponse.detail;
    this.retryAfter = errorResponse.retry_after;
    this.statusCode = statusCode;
  }

  get isRetryable(): boolean {
    return this.statusCode === 503 && this.retryAfter !== undefined;
  }

  get userMessage(): string {
    if (this.code === 'EMBEDDINGS_NOT_LOADED' || this.code === 'MODEL_NOT_LOADED') {
      return 'The service is still initializing. Please wait a moment and try again.';
    }
    if (this.code === 'ANTHROPIC_UNAVAILABLE') {
      return 'The AI service is temporarily unavailable. Please try again later.';
    }
    if (this.code === 'EMPTY_MESSAGE') {
      return 'Please enter a message.';
    }
    if (this.code === 'API_URL_NOT_CONFIGURED') {
      return 'Bowen is not configured correctly and cannot reach its backend. Please contact support.';
    }
    return this.detail || this.message;
  }
}

// The localhost fallback is a development convenience only. In a production
// build it would silently point the app at a backend that isn't there, so the
// misconfiguration is surfaced instead of being papered over.
const DEV_API_FALLBACK = 'http://localhost:8105';
const IS_PRODUCTION = process.env.NODE_ENV === 'production';
const CONFIGURED_API_HOST = process.env.NEXT_PUBLIC_API_URL;

export const API_URL_MISCONFIGURED = IS_PRODUCTION && !CONFIGURED_API_HOST;

const MISCONFIGURED_MESSAGE =
  'NEXT_PUBLIC_API_URL is not set in this production build. ' +
  'Set it to the backend URL at build time; the http://localhost:8105 fallback is development-only.';

if (API_URL_MISCONFIGURED) {
  console.error(`[Bowen] ${MISCONFIGURED_MESSAGE}`);
}

const API_HOST = CONFIGURED_API_HOST || DEV_API_FALLBACK;
// Use versioned API by default, fall back to legacy if needed
const API_VERSION = 'v1';
const API_BASE = `${API_HOST}/api/${API_VERSION}`;
const LEGACY_API_BASE = API_HOST;

/**
 * Throws a BowenApiError (which the existing error-banner path renders) when a
 * production build has no API URL configured, rather than quietly calling
 * localhost.
 */
function assertApiConfigured(): void {
  if (!API_URL_MISCONFIGURED) return;
  console.error(`[Bowen] ${MISCONFIGURED_MESSAGE}`);
  throw new BowenApiError(0, {
    error: 'Bowen is not configured correctly.',
    code: 'API_URL_NOT_CONFIGURED',
    detail: MISCONFIGURED_MESSAGE,
  });
}

/**
 * Absolute URL for a backend path that is not under /api/v1 (e.g. the donate
 * checkout endpoint), with the same production guard applied. Throws a
 * BowenApiError with code API_URL_NOT_CONFIGURED rather than silently
 * returning a localhost URL in a production build.
 */
export function resolveApiUrl(path: string): string {
  assertApiConfigured();
  return `${API_HOST}${path}`;
}

async function fetchWithFallback(
  endpoint: string,
  options?: RequestInit
): Promise<Response> {
  assertApiConfigured();

  // Try versioned API first
  try {
    const response = await fetch(`${API_BASE}${endpoint}`, options);
    if (response.ok || response.status < 500) {
      return response;
    }
  } catch {
    // Versioned API failed, try legacy
  }

  // Fall back to legacy API
  return fetch(`${LEGACY_API_BASE}${endpoint}`, options);
}

export async function sendMessage(
  message: string,
  sessionId?: string,
  attachments?: FileAttachment[]
): Promise<ChatResponse> {
  const body: Record<string, unknown> = { message, session_id: sessionId };
  if (attachments && attachments.length > 0) {
    body.attachments = attachments.map((a) => ({
      filename: a.filename,
      content_type: a.content_type,
      data: a.data,
    }));
  }

  const response = await fetchWithFallback('/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    try {
      const errorData = await response.json();
      if (errorData.detail && typeof errorData.detail === 'object') {
        throw new BowenApiError(response.status, errorData.detail as ApiError);
      }
      throw new BowenApiError(response.status, {
        error: errorData.detail || 'Failed to send message',
        code: 'UNKNOWN_ERROR'
      });
    } catch (e) {
      if (e instanceof BowenApiError) throw e;
      throw new Error('Failed to send message');
    }
  }

  return response.json();
}

export interface StreamCallbacks {
  onToken: (text: string) => void;
  onDone: (sources: Source[], disclaimer: string) => void;
  onError: (error: string) => void;
  /** What Bowen is doing before the first token, e.g. reading a section. */
  onStatus?: (text: string) => void;
}

export async function sendMessageStream(
  message: string,
  callbacks: StreamCallbacks,
  sessionId?: string,
  attachments?: FileAttachment[]
): Promise<void> {
  const body: Record<string, unknown> = { message, session_id: sessionId };
  if (attachments && attachments.length > 0) {
    body.attachments = attachments.map((a) => ({
      filename: a.filename,
      content_type: a.content_type,
      data: a.data,
    }));
  }

  try {
    assertApiConfigured();
  } catch (e) {
    callbacks.onError(
      e instanceof BowenApiError ? e.userMessage : 'Bowen is not configured correctly.'
    );
    return;
  }

  // Try versioned API first, fall back to legacy
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!response.ok && response.status >= 500) {
      throw new Error('v1 failed');
    }
  } catch {
    response = await fetch(`${LEGACY_API_BASE}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
  }

  if (!response.ok) {
    try {
      const errorData = await response.json();
      const msg = errorData?.detail?.error || errorData?.detail || 'Failed to send message';
      callbacks.onError(msg);
    } catch {
      callbacks.onError('Failed to send message');
    }
    return;
  }

  const reader = response.body?.getReader();
  if (!reader) {
    callbacks.onError('Streaming not supported');
    return;
  }

  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // Parse SSE lines
    const lines = buffer.split('\n');
    buffer = lines.pop() || ''; // Keep incomplete line in buffer

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      const jsonStr = line.slice(6);
      try {
        const event = JSON.parse(jsonStr);
        if (event.type === 'token') {
          callbacks.onToken(event.text);
        } else if (event.type === 'status') {
          if (typeof event.text === 'string') callbacks.onStatus?.(event.text);
        } else if (event.type === 'done') {
          callbacks.onDone(event.sources || [], event.disclaimer || '');
        } else if (event.type === 'error') {
          callbacks.onError(event.error);
        }
      } catch {
        // Skip malformed JSON
      }
    }
  }
}

export async function checkHealth(): Promise<boolean> {
  try {
    const response = await fetchWithFallback('/health');
    return response.ok;
  } catch {
    return false;
  }
}

export async function clearSession(sessionId: string): Promise<void> {
  try {
    await fetchWithFallback(`/session/${sessionId}`, { method: 'DELETE' });
  } catch {
    // Best-effort — don't break the UI if this fails
  }
}

export async function getActs(): Promise<Act[]> {
  const response = await fetchWithFallback('/acts');
  if (!response.ok) {
    throw new Error('Failed to fetch acts');
  }
  const data: ActsResponse = await response.json();
  return data.acts;
}
