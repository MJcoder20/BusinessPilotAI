
import axios from "axios";

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

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
  const response = await fetch(
    `${import.meta.env.VITE_API_URL}/ai/chat/stream`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      },
      body: JSON.stringify({
        message,
        conversation_id: conversationId,
      }),
      signal,
    }
  );

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
