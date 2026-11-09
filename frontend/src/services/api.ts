
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
