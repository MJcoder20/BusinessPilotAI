import axios, {
  type InternalAxiosRequestConfig,
} from "axios";


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

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

// Prevent simultaneous requests from refreshing multiple times.
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

export async function login(
  email: string,
  password: string
): Promise<AuthTokenResponse> {
  const response = await api.post<AuthTokenResponse>(
    "/auth/login",
    { email, password }
  );

  setAccessToken(response.data.access_token);

  return response.data;
}

export async function register(
  full_name: string,
  email: string,
  password: string
): Promise<AuthUser> {
  const response = await api.post<AuthUser>(
    "/auth/register",
    { full_name, email, password }
  );

  return response.data;
}

export async function getCurrentUser(): Promise<AuthUser> {
  const response = await api.get<AuthUser>("/auth/me");
  return response.data;
}

export async function logout(): Promise<void> {
  try {
    await api.post("/auth/logout");
  } finally {
    setAccessToken(null);
  }
}

// Attach the access token to authenticated API requests.
api.interceptors.request.use((config) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }

  return config;
});

// Refresh expired access tokens and retry failed requests once.
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
      const token = await refreshAccessToken();

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
  role: "user" | "assistant";
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

// Send a message to the AI
export async function sendMessage(
  message: string,
  conversationId: string | null
): Promise<ChatResponse> {
  const response = await api.post<ChatResponse>("/ai/chat", {
    message,
    conversation_id: conversationId,
  });

  return response.data;
}

// Create a new conversation
export async function createConversation(
  title = "New conversation"
): Promise<Conversation> {
  const response = await api.post<Conversation>("/conversations", {
    title,
  });

  return response.data;
}

// Retrieve all conversations
export async function getConversations(): Promise<Conversation[]> {
  const response = await api.get<Conversation[]>("/conversations");

  return response.data;
}

// Retrieve one conversation with its messages
export async function getConversation(
  conversationId: string
): Promise<ConversationDetail> {
  const response = await api.get<ConversationDetail>(
    `/conversations/${conversationId}`
  );

  return response.data;
}

// Delete a conversation
export async function deleteConversation(
  conversationId: string
): Promise<void> {
  await api.delete(`/conversations/${conversationId}`);
}


// Stream an AI response using Server-Sent Events (SSE)

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
        ...(token
          ? { Authorization: `Bearer ${token}` }
          : {}),
      },
      body: requestBody,
      signal,
    });

  let response = await sendRequest(getAccessToken());

  // Refresh an expired access token and retry once.
  if (response.status === 401) {
    const newToken = await refreshAccessToken();
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
