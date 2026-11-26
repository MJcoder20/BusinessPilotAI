
import axios, { type InternalAxiosRequestConfig } from "axios";
import { supabase } from "./supabase";

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
  withCredentials: true,
  headers: {
    "Content-Type": "application/json",
  },
});

// Authentication types
export interface AuthUser {
  id: number;
  full_name: string;
  email: string;
  role: "admin" | "manager" | "employee";
  is_active: boolean;
  created_at: string;
}

export interface AuthTokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: AuthUser;
}

// Access tokens are stored only in memory.
let accessToken: string | null = null;

type AuthProvider = "legacy" | "supabase" | null;
let authProvider: AuthProvider = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

export function setAuthProvider(provider: AuthProvider): void {
  authProvider = provider;
}

export function getAuthProvider(): AuthProvider {
  return authProvider;
}

// Prevent simultaneous legacy refresh requests.
let refreshPromise: Promise<string> | null = null;

export function refreshAccessToken(): Promise<string> {
  if (refreshPromise) {
    return refreshPromise;
  }

  refreshPromise = axios
    .post<AuthTokenResponse>(
      `${api.defaults.baseURL}/auth/refresh`,
      null,
      { withCredentials: true }
    )
    .then((response) => {
      const token = response.data.access_token;
      setAuthProvider("legacy");
      setAccessToken(token);
      return token;
    })
    .catch((error: unknown) => {
      setAccessToken(null);
      window.dispatchEvent(new Event("auth:session-expired"));
      throw error;
    })
    .finally(() => {
      refreshPromise = null;
    });

  return refreshPromise;
}

// Refresh a Supabase session.
export async function refreshSupabaseAccessToken(): Promise<string> {
  const { data, error } = await supabase.auth.refreshSession();

  if (error || !data.session) {
    setAccessToken(null);
    window.dispatchEvent(new Event("auth:session-expired"));
    throw error ?? new Error("Supabase session has expired.");
  }

  const token = data.session.access_token;
  setAccessToken(token);

  return token;
}

// Refresh according to the active authentication provider.
export function refreshCurrentAccessToken(): Promise<string> {
  if (authProvider === "supabase") {
    return refreshSupabaseAccessToken();
  }

  return refreshAccessToken();
}

// Existing legacy login.
export async function login(
  email: string,
  password: string
): Promise<AuthTokenResponse> {
  setAccessToken(null);
  setAuthProvider(null);

  const response = await api.post<AuthTokenResponse>(
    "/auth/login",
    { email, password }
  );

  setAuthProvider("legacy");
  setAccessToken(response.data.access_token);

  return response.data;
}

// New account registration through Supabase.
export async function register(
  full_name: string,
  email: string,
  password: string
): Promise<void> {
  const { error } = await supabase.auth.signUp({
    email,
    password,
    options: {
      data: { full_name },
      emailRedirectTo: `${window.location.origin}/`,
    },
  });

  if (error) {
    throw error;
  }
}

// Synchronize an authenticated Supabase user with FastAPI.
export async function syncSupabaseUser(
  token: string
): Promise<AuthUser> {
  const response = await api.post<AuthUser>(
    "/auth/supabase/sync",
    null,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );

  return response.data;
}

// Link an existing local account to an authenticated Supabase identity.
export async function linkSupabaseAccount(
  token: string,
  password: string
): Promise<AuthUser> {
  const response = await api.post<AuthUser>(
    "/auth/supabase/link",
    { password },
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );

  return response.data;
}

export async function getCurrentUser(): Promise<AuthUser> {
  const response = await api.get<AuthUser>("/auth/me");
  return response.data;
}

// Logout.
export async function logout(): Promise<void> {
  try {
    if (authProvider === "legacy") {
      await api.post("/auth/logout");
    }
  } finally {
    setAccessToken(null);
    setAuthProvider(null);
  }
}

// Attach the current access token to authenticated API requests.
api.interceptors.request.use((config) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }

  return config;
});

// Refresh expired tokens and retry failed requests once.
api.interceptors.response.use(
  (response) => response,
  async (error: unknown) => {
    if (!axios.isAxiosError(error)) {
      return Promise.reject(error);
    }

    const originalRequest = error.config as
      | (InternalAxiosRequestConfig & { _retry?: boolean })
      | undefined;

    if (
      error.response?.status !== 401 ||
      !originalRequest ||
      originalRequest._retry ||
      originalRequest.url?.includes("/auth/")
    ) {
      return Promise.reject(error);
    }

    originalRequest._retry = true;

    try {
      const token = await refreshCurrentAccessToken();
      originalRequest.headers.Authorization = `Bearer ${token}`;
      return api(originalRequest);
    } catch (refreshError) {
      return Promise.reject(refreshError);
    }
  }
);

// Chat types
export interface ChatRequest {
  message: string;
  conversation_id: string | null;
}

export interface ChatResponse {
  conversation_id: string;
  response: string;
}

// Conversation types
export interface ChatMessage {
  id: number;
  conversation_id: string;
  role: string;
  content: string;
  created_at: string;
}

export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ConversationDetail extends Conversation {
  messages: ChatMessage[];
}

export interface ConversationCreate {
  title?: string;
}

// Conversation API functions
export async function createConversation(
  title = "New conversation"
): Promise<Conversation> {
  const response = await api.post<Conversation>(
    "/conversations",
    { title }
  );

  return response.data;
}

export async function getConversations(): Promise<Conversation[]> {
  const response = await api.get<Conversation[]>("/conversations");
  return response.data;
}

export async function getConversation(
  conversationId: string
): Promise<ConversationDetail> {
  const response = await api.get<ConversationDetail>(
    `/conversations/${encodeURIComponent(conversationId)}`
  );

  return response.data;
}

export async function deleteConversation(
  conversationId: string
): Promise<void> {
  await api.delete(
    `/conversations/${encodeURIComponent(conversationId)}`
  );
}

// Stream an AI response using Server-Sent Events (SSE).
export async function streamMessage(
  message: string,
  conversationId: string | null,
  onToken: (token: string) => void,
  onConversationId: (id: string) => void,
  signal?: AbortSignal
): Promise<void> {
  const url = `${import.meta.env.VITE_API_URL}/ai/chat/stream`;

  const requestBody = JSON.stringify({
    message,
    conversation_id: conversationId,
  });

  const sendRequest = (token: string | null) =>
    fetch(url, {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: requestBody,
      signal,
    });

  let response = await sendRequest(getAccessToken());

  if (response.status === 401) {
    const newToken = await refreshCurrentAccessToken();
    response = await sendRequest(newToken);
  }

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(
      `Streaming failed (${response.status}): ${errorText}`
    );
  }

  if (!response.body) {
    throw new Error("Streaming response body is unavailable.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { value, done } = await reader.read();

      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      const events = buffer.split("\n\n");
      buffer = events.pop() ?? "";

      for (const event of events) {
        const dataLines = event
          .split("\n")
          .filter((line) => line.startsWith("data:"));

        for (const line of dataLines) {
          const data = line.slice(5).trim();

          if (!data) continue;

          const payload = JSON.parse(data);

          if (payload.conversation_id) {
            onConversationId(payload.conversation_id);
          }

          if (payload.token) {
            onToken(payload.token);
          }

          if (payload.error) {
            throw new Error(payload.error);
          }

          if (payload.done) {
            return;
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
