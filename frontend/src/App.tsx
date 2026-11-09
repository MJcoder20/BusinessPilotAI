
import { useEffect, useRef, useState } from "react";
import {
  Bot,
  Plus,
  Send,
  MessageSquare,
  Trash2,
  Menu,
  Sparkles,
  TrendingUp,
  Package,
  Users,
  FileText,
  LoaderCircle,
} from "lucide-react";

import {
  streamMessage,
  createConversation,
  getConversations,
  getConversation,
  deleteConversation as deleteConversationApi,
} from "./services/api";

import "./App.css";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  isError?: boolean;
}

interface Conversation {
  id: string;
  serverId: string | null;
  title: string;
  messages: ChatMessage[];
}
const suggestions = [
  {
    icon: TrendingUp,
    title: "Business overview",
    description: "Show me my business performance.",
    prompt: "Give me an overview of my business.",
  },
  {
    icon: Users,
    title: "Top customers",
    description: "Identify my highest-value customers.",
    prompt: "Who are my top 5 customers?",
  },
  {
    icon: Package,
    title: "Inventory analysis",
    description: "Find products that need restocking.",
    prompt: "Which products have low stock?",
  },
  {
    icon: FileText,
    title: "Overdue invoices",
    description: "Review outstanding customer payments.",
    prompt: "Do I have any overdue invoices?",
  },
];

function getErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error) {
    return error.message;
  }

  if (
    typeof error === "object" &&
    error !== null &&
    "response" in error
  ) {
    const response = (
      error as {
        response?: {
          data?: { detail?: string };
        };
      }
    ).response;

    return response?.data?.detail ?? fallback;
  }

  return fallback;
}

function App() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [loadingConversation, setLoadingConversation] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [historyError, setHistoryError] = useState<string | null>(null);

  const sendingRef = useRef(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const loadRequestRef = useRef(0);

  const activeConversation = conversations.find(
    (conversation) => conversation.id === activeId
  );

  const messages = activeConversation?.messages ?? [];

  // Load saved conversations when the application opens.
  useEffect(() => {
    let cancelled = false;

    async function loadHistory() {
      try {
        const savedConversations = await getConversations();

        if (cancelled) return;

        const mappedConversations: Conversation[] =
          savedConversations.map((conversation) => ({
            id: conversation.id,
            serverId: conversation.id,
            title: conversation.title,
            messages: [],
          }));

        setConversations(mappedConversations);

        // Automatically restore the most recently updated conversation.
        if (mappedConversations.length > 0) {
          const firstId = mappedConversations[0].id;

          setActiveId(firstId);
          setLoadingConversation(true);

          const requestId = ++loadRequestRef.current;

          try {
            const detail = await getConversation(firstId);

            if (cancelled || requestId !== loadRequestRef.current) {
              return;
            }

            setConversations((previous) =>
              previous.map((item) =>
                item.id === firstId
                  ? {
                      ...item,
                      messages: detail.messages.map((message) => ({
                        role: message.role,
                        content: message.content,
                      })),
                    }
                  : item
              )
            );
          } finally {
            if (
              !cancelled &&
              requestId === loadRequestRef.current
            ) {
              setLoadingConversation(false);
            }
          }
        }
      } catch (error) {
        if (!cancelled) {
          console.error("Failed to load conversation history:", error);
          setHistoryError("Unable to load conversation history.");
        }
      } finally {
        if (!cancelled) {
          setLoadingHistory(false);
          setLoadingConversation(false);
        }
      }
    }

    void loadHistory();

    return () => {
      cancelled = true;
      loadRequestRef.current += 1;
    };
  }, []);

  // Automatically scroll to the latest message.
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [messages, loading]);

  // Create a new local conversation.
  // It will be saved in PostgreSQL when the first message is sent.
  function createNewChat() {
    if (loading || loadingConversation) return;

    const id = crypto.randomUUID();

    setConversations((previous) => [
      {
        id,
        serverId: null,
        title: "New conversation",
        messages: [],
      },
      ...previous,
    ]);

    setActiveId(id);
    setInput("");
  }

  // Restore a conversation from PostgreSQL.
  async function openConversation(id: string) {
    if (loading || loadingConversation) return;

    const conversation = conversations.find(
      (item) => item.id === id
    );

    if (!conversation) return;

    setActiveId(id);
    setInput("");

    // Unsaved local conversations do not need an API request.
    if (!conversation.serverId) return;

    const requestId = ++loadRequestRef.current;

    setLoadingConversation(true);

    try {
      const detail = await getConversation(conversation.serverId);

      if (requestId !== loadRequestRef.current) return;

      setConversations((previous) =>
        previous.map((item) =>
          item.id === id
            ? {
                ...item,
                messages: detail.messages.map((message) => ({
                  role: message.role,
                  content: message.content,
                })),
              }
            : item
        )
      );
    } catch (error) {
      if (requestId === loadRequestRef.current) {
        console.error("Failed to restore conversation:", error);
        window.alert(
          getErrorMessage(error, "Unable to load this conversation.")
        );
      }
    } finally {
      if (requestId === loadRequestRef.current) {
        setLoadingConversation(false);
      }
    }
  }



  // Send a message to BusinessPilot AI using token streaming.
  async function handleSend(customMessage?: string) {
    const message = (customMessage ?? input).trim();

    if (
      !message ||
      sendingRef.current ||
      loading ||
      loadingConversation
    ) {
      return;
    }

    sendingRef.current = true;

    let conversation = activeConversation;

    // Create a local conversation if none is selected.
    if (!conversation) {
      conversation = {
        id: crypto.randomUUID(),
        serverId: null,
        title: message.slice(0, 35),
        messages: [],
      };

      setConversations((previous) => [
        conversation!,
        ...previous,
      ]);

      setActiveId(conversation.id);
    }

    const conversationId = conversation.id;
    const isFirstMessage = conversation.messages.length === 0;

    // The assistant placeholder follows the user's message.
    const assistantMessageIndex = conversation.messages.length + 1;

    // Display both messages immediately.
    setConversations((previous) =>
      previous.map((item) =>
        item.id === conversationId
          ? {
              ...item,
              title: isFirstMessage
                ? message.slice(0, 35)
                : item.title,
              messages: [
                ...item.messages,
                { role: "user", content: message },
                { role: "assistant", content: "" },
              ],
            }
          : item
      )
    );

    setInput("");
    setLoading(true);

    try {
      let serverId = conversation.serverId;

      // Create the database conversation on its first message.
      if (!serverId) {
        const created = await createConversation(
          message.slice(0, 200)
        );

        serverId = created.id;

        setConversations((previous) =>
          previous.map((item) =>
            item.id === conversationId
              ? {
                  ...item,
                  serverId: created.id,
                  title: message.slice(0, 35),
                }
              : item
          )
        );
      }

      // Stream the response token by token.
      await streamMessage(
        message,
        serverId,

        // Append each incoming token to the assistant message.
        (token) => {
          setConversations((previous) =>
            previous.map((item) => {
              if (item.id !== conversationId) return item;

              const updatedMessages = [...item.messages];
              const assistantMessage =
                updatedMessages[assistantMessageIndex];

              if (!assistantMessage) return item;

              updatedMessages[assistantMessageIndex] = {
                ...assistantMessage,
                content: assistantMessage.content + token,
              };

              return {
                ...item,
                messages: updatedMessages,
              };
            })
          );
        },

        // Confirm the persistent conversation ID.
        (id) => {
          serverId = id;

          setConversations((previous) =>
            previous.map((item) =>
              item.id === conversationId
                ? { ...item, serverId: id }
                : item
            )
          );
        }
      );
    } catch (error: unknown) {
      const errorMessage = getErrorMessage(
        error,
        "Something went wrong. Please try again."
      );

      // Restore the original message so the user can retry.
      setInput(message);

      // Show the error on the assistant placeholder.
      setConversations((previous) =>
        previous.map((item) => {
          if (item.id !== conversationId) return item;

          const updatedMessages = [...item.messages];
          const assistantMessage =
            updatedMessages[assistantMessageIndex];

          if (!assistantMessage) return item;

          updatedMessages[assistantMessageIndex] = {
            ...assistantMessage,
            content: assistantMessage.content || errorMessage,
            isError: true,
          };

          return {
            ...item,
            messages: updatedMessages,
          };
        })
      );
    } finally {
      sendingRef.current = false;
      setLoading(false);
    }
  }


  // Delete a conversation from PostgreSQL and the interface.
  async function deleteConversation(id: string) {
    if (loading || loadingConversation) return;

    const conversation = conversations.find(
      (item) => item.id === id
    );

    if (!conversation) return;

    try {
      if (conversation.serverId) {
        await deleteConversationApi(conversation.serverId);
      }

      const remaining = conversations.filter(
        (item) => item.id !== id
      );

      setConversations(remaining);

      if (activeId === id) {
        setActiveId(remaining[0]?.id ?? null);

        if (remaining[0]?.serverId) {
          void openConversation(remaining[0].id);
        }
      }
    } catch (error) {
      console.error("Failed to delete conversation:", error);

      window.alert(
        getErrorMessage(error, "Unable to delete this conversation.")
      );
    }
  }

  return (
    <div className="app-container">
      <aside className={`sidebar ${sidebarOpen ? "" : "collapsed"}`}>
        <div className="sidebar-header">
          <div className="brand">
            <div className="brand-icon">
              <Bot size={23} />
            </div>

            {sidebarOpen && (
              <div>
                <h2>BusinessPilot</h2>
                <span>AI BUSINESS ASSISTANT</span>
              </div>
            )}
          </div>
        </div>

        {sidebarOpen && (
          <>
            <button
              className="new-chat-button"
              onClick={createNewChat}
              disabled={loading || loadingConversation}
            >
              <Plus size={18} />
              <span>New conversation</span>
            </button>

            <div className="sidebar-section">
              <p className="section-label">YOUR WORKSPACE</p>

              <div className="workspace-item active">
                <MessageSquare size={17} />
                <span>AI Assistant</span>
              </div>
            </div>

            <div className="history-section">
              <p className="section-label">RECENT CONVERSATIONS</p>

              {loadingHistory ? (
                <p className="empty-history">
                  Loading conversations...
                </p>
              ) : conversations.length === 0 ? (
                <p className="empty-history">
                  {historyError ??
                    "Your conversations will appear here."}
                </p>
              ) : (
                conversations.map((conversation) => (
                  <div
                    key={conversation.id}
                    className={`history-item ${
                      activeId === conversation.id ? "selected" : ""
                    }`}
                  >
                    <button
                      className="history-title"
                      onClick={() =>
                        void openConversation(conversation.id)
                      }
                      disabled={loading || loadingConversation}
                    >
                      <MessageSquare size={15} />
                      <span>{conversation.title}</span>
                    </button>

                    <button
                      className="delete-button"
                      onClick={() =>
                        void deleteConversation(conversation.id)
                      }
                      aria-label="Delete conversation"
                      disabled={loading || loadingConversation}
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                ))
              )}
            </div>

            <div className="sidebar-footer">
              <div className="status-dot" />
              <span>Local AI environment</span>
            </div>
          </>
        )}

        {!sidebarOpen && (
          <button
            className="collapsed-new-chat"
            onClick={createNewChat}
            title="New conversation"
            disabled={loading || loadingConversation}
          >
            <Plus size={21} />
          </button>
        )}
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div className="topbar-left">
            <button
              className="icon-button"
              onClick={() => setSidebarOpen(!sidebarOpen)}
              aria-label="Toggle sidebar"
            >
              <Menu size={20} />
            </button>

            <div>
              <h3>AI Business Assistant</h3>
              <p>Intelligent business insights, powered by AI</p>
            </div>
          </div>

          <div className="model-indicator">
            <span className="model-dot" />
            Qwen 2.5 · Local
          </div>
        </header>

        <div className="chat-area">
          {loadingConversation ? (
            <div className="welcome-container">
              <LoaderCircle size={24} className="spinner" />
              <p>Restoring your conversation...</p>
            </div>
          ) : messages.length === 0 ? (
            <div className="welcome-container">
              <div className="welcome-icon">
                <Sparkles size={29} />
              </div>

              <h1>
                Your business,
                <br />
                <span>with intelligence.</span>
              </h1>

              <p className="welcome-description">
                Ask questions about your customers, sales, inventory,
                and invoices. BusinessPilot AI turns your business
                data into actionable insights.
              </p>

              <div className="suggestions-grid">
                {suggestions.map((suggestion) => {
                  const Icon = suggestion.icon;

                  return (
                    <button
                      className="suggestion-card"
                      key={suggestion.title}
                      onClick={() =>
                        void handleSend(suggestion.prompt)
                      }
                      disabled={loading}
                    >
                      <div className="suggestion-icon">
                        <Icon size={19} />
                      </div>

                      <strong>{suggestion.title}</strong>
                      <span>{suggestion.description}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          ) : (
            <div className="messages-container">
              {messages.map((message, index) => (
                <div
                  className={`message-row ${message.role}`}
                  key={`${index}-${message.role}`}
                >
                  <div className="message-avatar">
                    {message.role === "assistant" ? (
                      <Bot size={19} />
                    ) : (
                      <span>U</span>
                    )}
                  </div>

                  <div className="message-content">
                    <span className="message-author">
                      {message.role === "assistant"
                        ? "BusinessPilot AI"
                        : "You"}
                    </span>


                    <div className="message-text">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {message.role === "assistant"
                          ? message.content.replace(/\\\*/g, "*")
                          : message.content}
                      </ReactMarkdown>
                    </div>

                    {message.isError && (
                      <button
                        className="retry-button"
                        onClick={() => void handleSend()}
                        disabled={loading || loadingConversation}
                      >
                        Retry
                      </button>
                    )}
                  </div>
                </div>
              ))}

              {loading && (
                <div className="message-row assistant">
                  <div className="message-content">
                    <div className="typing-indicator">
                      <LoaderCircle
                        size={17}
                        className="spinner"
                      />
                      Analyzing your business data...
                    </div>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        <div className="input-section">
          <form
            className="message-form"
            onSubmit={(event) => {
              event.preventDefault();
              void handleSend();
            }}
          >
            <textarea
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  event.currentTarget.form?.requestSubmit();
                }
              }}
              placeholder="Ask anything about your business..."
              rows={1}
              disabled={loading || loadingConversation}
            />

            <button
              type="submit"
              className="send-button"
              disabled={
                !input.trim() || loading || loadingConversation
              }

              aria-label="Send message"
            >
              {loading ? (
                <LoaderCircle size={19} className="spinner" />
              ) : (
                <Send size={19} />
              )}
            </button>
          </form>

          <p className="input-disclaimer">
            BusinessPilot AI can make mistakes. Verify important
            business decisions against your records.
          </p>
        </div>
      </main>
    </div>
  );
}

export default App;
