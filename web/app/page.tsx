"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { getSocket, disconnectSocket, type ChatMessage, type AgentStatus } from "@/lib/socket";

type Page = "chat" | "dashboard" | "skills" | "channels" | "settings" | "memories" | "extensions";

export default function NexAlfa() {
  const [currentPage, setCurrentPage] = useState<Page>("chat");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [connected, setConnected] = useState(false);
  const [status, setStatus] = useState<AgentStatus | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [usageInfo, setUsageInfo] = useState<any>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // ── Socket.IO Connection ────────────────────────────────
  useEffect(() => {
    const socket = getSocket();
    const GATEWAY = process.env.NEXT_PUBLIC_API_URL ?? (process.env.NODE_ENV === 'development' ? 'http://localhost:18789' : '');

    socket.on("connect", () => {
      setConnected(true);
      // Load message history from the server
      socket.emit("load_history");
      // Initial usage fetch
      fetch(`${GATEWAY}/api/usage`).then(r => r.json()).then(setUsageInfo).catch(() => {});
    });
    socket.on("disconnect", () => setConnected(false));

    // Receive message history on connect / reconnect
    socket.on("history", (data: any) => {
      if (data.messages && data.messages.length > 0) {
        setMessages(data.messages.map((m: any) => ({
          role: m.role,
          content: m.content,
          thinking: m.thinking,
          timestamp: m.timestamp,
        })));
      }
      // Update status bar with latest model info from backend
      if (data.model) {
        setUsageInfo((prev: any) => ({ ...prev, model: data.model, thinking_level: data.thinking_level, temperature: data.temperature }));
      }
    });

    socket.on("message_start", (data: any) => {
      if (data.type === "user") return;
    });

    socket.on("message_chunk", (data: any) => {
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last && last.role === "assistant" && last.isStreaming) {
          const updated = { ...last };
          if (data.type === "thinking") {
            updated.thinking = (updated.thinking || "") + data.data;
          } else {
            updated.content += data.data;
          }
          return [...prev.slice(0, -1), updated];
        }
        return prev;
      });
    });

    socket.on("message_end", (data: any) => {
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last && last.role === "assistant" && last.isStreaming) {
          return [...prev.slice(0, -1), { ...last, isStreaming: false }];
        }
        return prev;
      });
      setIsStreaming(false);
      // Update status bar immediately from the response payload (model may have changed)
      if (data.model) {
        setUsageInfo((prev: any) => ({
          ...prev,
          model: data.model,
          thinking_level: data.thinking_level,
          temperature: data.temperature,
        }));
      }
      // Also fetch full usage stats
      fetch(`${GATEWAY}/api/usage`).then(r => r.json()).then(setUsageInfo).catch(() => {});
    });

    // Broadcast from other channels
    socket.on("message", (data: any) => {
      if (data.channel !== "webchat") {
        setMessages((prev) => [
          ...prev,
          {
            role: "user",
            content: `[${data.channel}] ${data.sender}: ${data.content}`,
            channel: data.channel,
            timestamp: data.timestamp,
          },
          {
            role: "assistant",
            content: data.response,
            channel: data.channel,
            timestamp: data.timestamp,
          },
        ]);
      }
    });

    // Request status
    socket.emit("get_status");
    socket.on("status", (data: AgentStatus) => setStatus(data));

    // Poll usage every 5s to keep status bar current
    const usagePoll = setInterval(() => {
      fetch(`${GATEWAY}/api/usage`).then(r => r.json()).then(setUsageInfo).catch(() => {});
    }, 5000);

    return () => {
      clearInterval(usagePoll);
      disconnectSocket();
    };
  }, []);

  // ── Auto-scroll ─────────────────────────────────────────
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // ── Send Message ────────────────────────────────────────
  const sendMessage = useCallback(() => {
    const text = input.trim();
    if (!text || isStreaming) return;

    const socket = getSocket();

    // Add user message
    setMessages((prev) => [
      ...prev,
      { role: "user", content: text, timestamp: Date.now() / 1000 },
    ]);

    // Add empty assistant message for streaming
    setMessages((prev) => [
      ...prev,
      { role: "assistant", content: "", timestamp: Date.now() / 1000, isStreaming: true },
    ]);

    setIsStreaming(true);
    setInput("");

    socket.emit("chat_message", { content: text });

    inputRef.current?.focus();
  }, [input, isStreaming]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  // ── Render ──────────────────────────────────────────────
  return (
    <div className="app-layout">
      {/* Sidebar */}
      <aside className={`sidebar ${sidebarOpen ? "open" : ""}`}>
        <div className="sidebar-header">
          <div className="sidebar-logo">N</div>
          <div>
            <div className="sidebar-title">NexAlfa</div>
            <div className="sidebar-subtitle">Personal Agent</div>
          </div>
        </div>

        <nav className="sidebar-nav">
          <div className="nav-section-label">Main</div>
          <NavItem icon="💬" label="Chat" active={currentPage === "chat"} onClick={() => { setCurrentPage("chat"); setSidebarOpen(false); }} />
          <NavItem icon="📊" label="Dashboard" active={currentPage === "dashboard"} onClick={() => { setCurrentPage("dashboard"); setSidebarOpen(false); }} />

          <div className="nav-section-label">Agent</div>
          <NavItem icon="⚡" label="Skills" active={currentPage === "skills"} onClick={() => { setCurrentPage("skills"); setSidebarOpen(false); }}
            badge={status?.memory?.total_memories} />
          <NavItem icon="🧩" label="Extensions" active={currentPage === "extensions"} onClick={() => { setCurrentPage("extensions"); setSidebarOpen(false); }} />
          <NavItem icon="🧠" label="Memories" active={currentPage === "memories"} onClick={() => { setCurrentPage("memories"); setSidebarOpen(false); }} />
          <NavItem icon="📡" label="Channels" active={currentPage === "channels"} onClick={() => { setCurrentPage("channels"); setSidebarOpen(false); }}
            badge={status?.channels?.filter(c => c.running).length} />

          <div className="nav-section-label">System</div>
          <NavItem icon="⚙️" label="Settings" active={currentPage === "settings"} onClick={() => { setCurrentPage("settings"); setSidebarOpen(false); }} />
        </nav>

        <div className="sidebar-footer">
          <div className="status-indicator">
            <span className={`status-dot ${connected ? "" : "offline"}`} />
            <span>{connected ? "Connected" : "Disconnected"}</span>
            <span style={{ marginLeft: "auto", fontSize: 11, color: "var(--text-tertiary)" }}>
              {(usageInfo?.model || status?.model?.current_model || '—').split('/').pop()}
            </span>
          </div>
        </div>
      </aside>

      {sidebarOpen && <div className="sidebar-overlay" onClick={() => setSidebarOpen(false)} />}

      {/* Main Content */}
      <main className="main-content">
        {/* Mobile header */}
        <div className="page-header" style={{ display: "none" }}>
          <button onClick={() => setSidebarOpen(!sidebarOpen)} style={{ background: "none", border: "none", color: "var(--text-primary)", fontSize: 20, cursor: "pointer" }}>☰</button>
          <span className="page-title">{currentPage.charAt(0).toUpperCase() + currentPage.slice(1)}</span>
          <span />
        </div>

        {currentPage === "chat" && (
          <ChatView
            messages={messages}
            input={input}
            setInput={setInput}
            isStreaming={isStreaming}
            sendMessage={sendMessage}
            handleKeyDown={handleKeyDown}
            messagesEndRef={messagesEndRef}
            inputRef={inputRef}
            agentName={status?.agent_name || "Nex"}
            usageInfo={usageInfo}
            status={status}
          />
        )}

        {currentPage === "dashboard" && <DashboardView status={status} connected={connected} />}
        {currentPage === "skills" && <SkillsView />}
        {currentPage === "extensions" && <ExtensionsView />}
        {currentPage === "memories" && <MemoriesView status={status} />}
        {currentPage === "channels" && <ChannelsView status={status} />}
        {currentPage === "settings" && <SettingsView status={status} />}
      </main>
    </div>
  );
}

/* ── Nav Item Component ──────────────────────────────────── */
function NavItem({ icon, label, active, onClick, badge }: {
  icon: string; label: string; active: boolean; onClick: () => void; badge?: number;
}) {
  return (
    <button className={`nav-item ${active ? "active" : ""}`} onClick={onClick}>
      <span className="nav-item-icon">{icon}</span>
      <span>{label}</span>
      {badge !== undefined && badge > 0 && <span className="nav-item-badge">{badge}</span>}
    </button>
  );
}

/* ── Chat View ───────────────────────────────────────────── */
function ChatView({ messages, input, setInput, isStreaming, sendMessage, handleKeyDown, messagesEndRef, inputRef, agentName, usageInfo, status }: any) {
  const [attachments, setAttachments] = useState<File[]>([]);
  const [isRecording, setIsRecording] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setAttachments(prev => [...prev, ...Array.from(e.target.files!)]);
    }
  };

  const removeAttachment = (idx: number) => {
    setAttachments(prev => prev.filter((_, i) => i !== idx));
  };

  const handleSendWithAttachments = () => {
    if (attachments.length > 0) {
      // Convert files to base64 and send
      const socket = (window as any).__nexSocket || require('@/lib/socket').getSocket();
      attachments.forEach(file => {
        const reader = new FileReader();
        reader.onload = () => {
          socket.emit('chat_upload', {
            filename: file.name,
            type: file.type,
            data: reader.result,
          });
        };
        reader.readAsDataURL(file);
      });
      setAttachments([]);
    }
    sendMessage();
  };

  const toggleRecording = async () => {
    if (isRecording) {
      mediaRecorderRef.current?.stop();
      setIsRecording(false);
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      const chunks: Blob[] = [];
      recorder.ondataavailable = (e) => chunks.push(e.data);
      recorder.onstop = () => {
        const blob = new Blob(chunks, { type: 'audio/webm' });
        stream.getTracks().forEach(t => t.stop());
        const reader = new FileReader();
        reader.onload = () => {
          const socket = require('@/lib/socket').getSocket();
          socket.emit('chat_upload', {
            filename: `voice_${Date.now()}.webm`,
            type: 'audio/webm',
            data: reader.result,
          });
        };
        reader.readAsDataURL(blob);
      };
      recorder.start();
      mediaRecorderRef.current = recorder;
      setIsRecording(true);
    } catch (err) {
      console.error('Microphone access denied:', err);
    }
  };

  // Format token usage for status bar
  const usage = usageInfo?.last_usage || {};
  const promptTokens = usage.prompt_tokens || 0;
  const completionTokens = usage.completion_tokens || 0;
  const totalTokens = promptTokens + completionTokens;
  const modelName = usageInfo?.model || status?.model?.current_model || '';
  const thinkingLvl = usageInfo?.thinking_level || status?.model?.thinking_level || 'medium';
  const temp = usageInfo?.temperature ?? status?.model?.temperature ?? 0.7;
  const currentAgent = usageInfo?.agent_name || agentName;
  // Estimate context % (assuming common context windows)
  const contextWindow = modelName.includes('gpt-4') ? 128000 : modelName.includes('gemini') ? 1000000 : modelName.includes('claude') ? 200000 : 128000;
  const contextPct = contextWindow > 0 ? ((totalTokens / contextWindow) * 100).toFixed(1) : '0';

  return (
    <div className="chat-container">
      <div className="page-header">
        <span className="page-title">💬 Chat with {agentName}</span>
        <span style={{ fontSize: 12, color: "var(--text-tertiary)" }}>{messages.length} messages</span>
      </div>

      <div className="chat-messages">
        {messages.length === 0 && (
          <div style={{ textAlign: "center", padding: "60px 20px", color: "var(--text-tertiary)" }}>
            <div style={{ fontSize: 48, marginBottom: 16 }}>🤖</div>
            <div style={{ fontSize: 18, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 8 }}>
              Hey, I&apos;m {agentName}
            </div>
            <div style={{ fontSize: 14 }}>
              Your personal AI agent. Ask me anything, or try a /command.
            </div>
          </div>
        )}

        {messages.map((msg: ChatMessage, i: number) => (
          <div key={i} className={`message ${msg.role}`}>
            <div className="message-avatar">
              {msg.role === "assistant" ? "N" : "Y"}
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 4, minWidth: 0 }}>
              {msg.thinking && (
                <div className="message-thinking">💭 {msg.thinking}</div>
              )}
              <div className={`message-bubble ${msg.content?.startsWith?.('❌') ? 'error' : ''}`}>
                {msg.content}
                {msg.isStreaming && !msg.content && (
                  <div className="typing-indicator">
                    <div className="typing-dot" />
                    <div className="typing-dot" />
                    <div className="typing-dot" />
                  </div>
                )}
              </div>
              {msg.channel && msg.channel !== "webchat" && (
                <div className="message-channel-tag">via {msg.channel}</div>
              )}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* ── Status Bar ─────────────────────────────────────── */}
      <div className="chat-status-bar">
        <span className="status-item" title="Active model">🧠 {modelName.split('/').pop() || '—'}</span>
        <span className="status-sep">|</span>
        <span className="status-item" title="Current agent">🤖 {currentAgent}</span>
        <span className="status-sep">|</span>
        <span className="status-item" title="Thinking level">💭 {thinkingLvl}</span>
        <span className="status-sep">|</span>
        <span className="status-item" title="Token usage">📊 {totalTokens > 0 ? `${totalTokens.toLocaleString()}/${(contextWindow/1000).toFixed(0)}K (${contextPct}%)` : '—'}</span>
        <span className="status-sep">|</span>
        <span className="status-item" title="Temperature">⚡ {temp}°</span>
      </div>

      {/* ── Attachment Previews ─────────────────────────────── */}
      {attachments.length > 0 && (
        <div className="chat-attachments">
          {attachments.map((file, i) => (
            <div key={i} className="attachment-chip">
              <span>{file.type.startsWith('image/') ? '🖼️' : file.type.startsWith('audio/') ? '🎤' : file.type.startsWith('video/') ? '🎥' : '📄'}</span>
              <span className="attachment-name">{file.name.length > 20 ? file.name.slice(0,18) + '...' : file.name}</span>
              <button className="attachment-remove" onClick={() => removeAttachment(i)}>×</button>
            </div>
          ))}
        </div>
      )}

      <div className="chat-input-container">
        <div className="chat-input-wrapper">
          {/* File upload */}
          <input type="file" ref={fileInputRef} onChange={handleFileSelect}
            multiple accept="image/*,audio/*,video/*,.pdf,.docx,.xlsx,.txt,.csv,.json" hidden />
          <button className="chat-action-btn" onClick={() => fileInputRef.current?.click()}
            title="Attach files (images, audio, video, documents)">
            📎
          </button>

          {/* Voice record */}
          <button className={`chat-action-btn ${isRecording ? 'recording' : ''}`}
            onClick={toggleRecording} title={isRecording ? 'Stop recording' : 'Record voice message'}>
            {isRecording ? '⏹️' : '🎤'}
          </button>

          <textarea
            ref={inputRef}
            className="chat-input"
            placeholder={`Message ${agentName}...`}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSendWithAttachments(); } }}
            rows={1}
            disabled={isStreaming}
          />
          <button className="chat-send-btn" onClick={handleSendWithAttachments}
            disabled={(!input.trim() && attachments.length === 0) || isStreaming}>
            ↑
          </button>
        </div>
      </div>
    </div>
  );
}

/* ── Dashboard View ──────────────────────────────────────── */
function DashboardView({ status, connected }: { status: AgentStatus | null; connected: boolean }) {
  return (
    <>
      <div className="page-header">
        <span className="page-title">📊 Dashboard</span>
      </div>
      <div className="page-body">
        <div className="dashboard-grid">
          <div className="card stat-card">
            <div className="stat-label">Status</div>
            <div className="stat-value" style={{ fontSize: 24 }}>
              {connected ? "🟢 Online" : "🔴 Offline"}
            </div>
            <div className="stat-sublabel">{status?.agent_name || "Nex"} · {status?.model?.current_model || "—"}</div>
          </div>

          <div className="card stat-card">
            <div className="stat-label">Sessions</div>
            <div className="stat-value">{status?.sessions?.active_sessions ?? 0}</div>
            <div className="stat-sublabel">{status?.sessions?.total_messages ?? 0} total messages</div>
          </div>

          <div className="card stat-card">
            <div className="stat-label">Memories</div>
            <div className="stat-value">{status?.memory?.total_memories ?? 0}</div>
            <div className="stat-sublabel">{status?.memory?.conversations_indexed ?? 0} indexed conversations</div>
          </div>

          <div className="card stat-card">
            <div className="stat-label">User Facts</div>
            <div className="stat-value">{status?.memory?.user_facts ?? 0}</div>
            <div className="stat-sublabel">What Nex knows about you</div>
          </div>

          <div className="card stat-card">
            <div className="stat-label">Active Channels</div>
            <div className="stat-value">{status?.channels?.filter(c => c.running).length ?? 0}</div>
            <div className="stat-sublabel">of {status?.channels?.length ?? 0} configured</div>
          </div>

          <div className="card stat-card">
            <div className="stat-label">Thinking Level</div>
            <div className="stat-value" style={{ fontSize: 24 }}>{status?.model?.thinking_level ?? "medium"}</div>
            <div className="stat-sublabel">Temperature: {status?.model?.temperature ?? 0.7}</div>
          </div>
        </div>

        {status?.channels && (
          <div style={{ marginTop: 24 }}>
            <div className="card">
              <div className="card-header">
                <span className="card-title">Channel Status</span>
              </div>
              <div className="card-body" style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                {status.channels.map((ch) => (
                  <span key={ch.name} className={`channel-badge ${ch.running ? "online" : ch.configured ? "configured" : "offline"}`}>
                    {ch.running ? "●" : "○"} {ch.display_name}
                  </span>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </>
  );
}

/* ── Extensions View ─────────────────────────────────────── */
function ExtensionsView() {
  const [toast, setToast] = useState("");
  const flash = (msg: string) => { setToast(msg); setTimeout(() => setToast(""), 2500); };
  
  const handleConnect = (name: string) => {
    // This would typically trigger an OAuth popup or prompt for a token
    flash(`🔗 Connecting to ${name}... (Requires OAuth link)`);
  };

  const extensions = [
    { name: "Claude Code", icon: "🤖", desc: "Anthropic's agentic coding assistant.", provider: "anthropic" },
    { name: "OpenAI Codex", icon: "⚡", desc: "OpenAI's powerful code generation.", provider: "openai" },
    { name: "Cursor Copilot", icon: "💻", desc: "VS Code integration and codebase indexing.", provider: "cursor" }
  ];

  return (
    <>
      <div className="page-header">
        <span className="page-title">🧩 Extensions & Copilots</span>
        {toast && <span className="channel-badge online" style={{ animation: "fadeIn 0.3s ease" }}>{toast}</span>}
      </div>
      <div className="page-body">
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: 16 }}>
          {extensions.map(ext => (
            <div key={ext.name} className="card" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <span style={{ fontSize: 32 }}>{ext.icon}</span>
                <div>
                  <div style={{ fontSize: 18, fontWeight: 600 }}>{ext.name}</div>
                  <div style={{ fontSize: 12, color: "var(--text-tertiary)", textTransform: "uppercase" }}>{ext.provider}</div>
                </div>
              </div>
              <div style={{ color: "var(--text-secondary)", fontSize: 14, flex: 1 }}>
                {ext.desc}
              </div>
              <button className="settings-btn active" onClick={() => handleConnect(ext.name)} style={{ width: "100%", justifyContent: "center" }}>
                Connect Integration
              </button>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

/* ── Skills View ─────────────────────────────────────────── */
function SkillsView() {
  const [skills, setSkills] = useState<any[]>([]);
  useEffect(() => {
    fetch(`${process.env.NEXT_PUBLIC_API_URL ?? (process.env.NODE_ENV === 'development' ? 'http://localhost:18789' : '')}/api/skills`)
      .then(r => r.json()).then(setSkills).catch(() => {});
  }, []);

  return (
    <>
      <div className="page-header">
        <span className="page-title">⚡ Skills</span>
      </div>
      <div className="page-body">
        {skills.length === 0 ? (
          <div className="card" style={{ padding: 40, textAlign: "center" }}>
            <div style={{ fontSize: 40, marginBottom: 12 }}>✨</div>
            <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 8 }}>No skills yet</div>
            <div style={{ color: "var(--text-secondary)", fontSize: 14 }}>
              Nex will auto-create skills as it learns from your conversations.
            </div>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {skills.map((s, i) => (
              <div key={i} className="card">
                <div className="card-body" style={{ display: "flex", alignItems: "center", gap: 16 }}>
                  <span style={{ fontSize: 24 }}>⚡</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 600 }}>/{s.name}</div>
                    <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>{s.description}</div>
                  </div>
                  <div style={{ textAlign: "right", fontSize: 12, color: "var(--text-tertiary)" }}>
                    <div>Used {s.usage_count}x</div>
                    {s.auto_created && <div style={{ color: "var(--accent)" }}>auto-created</div>}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  );
}

/* ── Memories View ───────────────────────────────────────── */
function MemoriesView({ status }: { status: AgentStatus | null }) {
  return (
    <>
      <div className="page-header">
        <span className="page-title">🧠 Memories</span>
      </div>
      <div className="page-body">
        <div className="dashboard-grid">
          <div className="card stat-card">
            <div className="stat-label">Total Messages</div>
            <div className="stat-value">{status?.memory?.total_messages ?? 0}</div>
            <div className="stat-sublabel">Across all channels</div>
          </div>
          <div className="card stat-card">
            <div className="stat-label">Extracted Memories</div>
            <div className="stat-value">{status?.memory?.total_memories ?? 0}</div>
            <div className="stat-sublabel">Auto-learned from conversations</div>
          </div>
          <div className="card stat-card">
            <div className="stat-label">User Facts</div>
            <div className="stat-value">{status?.memory?.user_facts ?? 0}</div>
            <div className="stat-sublabel">What Nex knows about you</div>
          </div>
          <div className="card stat-card">
            <div className="stat-label">Indexed Vectors</div>
            <div className="stat-value">{status?.memory?.conversations_indexed ?? 0}</div>
            <div className="stat-sublabel">For semantic search</div>
          </div>
        </div>

        <div style={{ marginTop: 24 }}>
          <div className="card" style={{ padding: 40, textAlign: "center" }}>
            <div style={{ fontSize: 40, marginBottom: 12 }}>🔍</div>
            <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 8 }}>Memory Browser</div>
            <div style={{ color: "var(--text-secondary)", fontSize: 14 }}>
              Nex auto-extracts memories, user facts, and skill candidates from conversations.
              <br />Use <code style={{ color: "var(--accent)" }}>/search &lt;query&gt;</code> in chat to search past conversations.
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

/* ── Channels View ───────────────────────────────────────── */
function ChannelsView({ status }: { status: AgentStatus | null }) {
  const channelIcons: Record<string, string> = {
    webchat: "🌐", telegram: "✈️", discord: "🎮", slack: "💼",
    whatsapp: "📱", google_chat: "💬", email: "📧",
  };

  return (
    <>
      <div className="page-header">
        <span className="page-title">📡 Channels</span>
      </div>
      <div className="page-body">
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {(status?.channels || []).map((ch) => (
            <div key={ch.name} className="card">
              <div className="card-body" style={{ display: "flex", alignItems: "center", gap: 16 }}>
                <span style={{ fontSize: 28 }}>{channelIcons[ch.name] || "📡"}</span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600 }}>{ch.display_name}</div>
                  <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>
                    {ch.running ? "Running" : ch.configured ? "Configured — not running" : "Not configured"}
                  </div>
                </div>
                <span className={`channel-badge ${ch.running ? "online" : ch.configured ? "configured" : "offline"}`}>
                  {ch.running ? "● Online" : ch.configured ? "● Ready" : "○ Offline"}
                </span>
              </div>
            </div>
          ))}
          {(!status?.channels || status.channels.length === 0) && (
            <div className="card" style={{ padding: 40, textAlign: "center", color: "var(--text-secondary)" }}>
              Connect to the gateway to see channel status.
            </div>
          )}
        </div>
      </div>
    </>
  );
}

/* ── Settings View (Interactive Controls) ────────────────── */
function SettingsView({ status }: { status: AgentStatus | null }) {
  const [modelInfo, setModelInfo] = useState<any>(null);
  const [selectedProvider, setSelectedProvider] = useState("");
  const [selectedModel, setSelectedModel] = useState("");
  const [customModel, setCustomModel] = useState("");
  const [thinkingLevel, setThinkingLevel] = useState("medium");
  const [temperature, setTemperature] = useState(0.7);
  const [showThinking, setShowThinking] = useState(true);
  const [toast, setToast] = useState("");
  const API = process.env.NEXT_PUBLIC_API_URL ?? (process.env.NODE_ENV === 'development' ? 'http://localhost:18789' : '');

  // Load model info
  useEffect(() => {
    fetch(`${API}/api/model`).then(r => r.json()).then(data => {
      setModelInfo(data);
      const parts = (data.current_model || "").split("/");
      setSelectedProvider(parts[0] || "");
      setSelectedModel(data.current_model || "");
      setThinkingLevel(data.thinking_level || "medium");
      setTemperature(data.temperature ?? 0.7);
    }).catch(() => {});
  }, [API]);

  useEffect(() => {
    setShowThinking(status?.dev_mode ?? true);
  }, [status]);

  const flash = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(""), 2500);
  };

  const changeModel = async (model: string) => {
    if (!model.trim()) return;
    setSelectedModel(model);
    setCustomModel("");
    const parts = model.split("/");
    setSelectedProvider(parts[0] || "");
    await fetch(`${API}/api/model`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model }),
    });
    flash(`✅ Model → ${model}`);
  };

  const changeThinking = async (level: string) => {
    setThinkingLevel(level);
    await fetch(`${API}/api/thinking`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ level }),
    });
    flash(`✅ Thinking → ${level}`);
  };

  const changeTemp = async (t: number) => {
    setTemperature(t);
    await fetch(`${API}/api/temperature`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ temperature: t }),
    });
    flash(`✅ Temperature → ${t}`);
  };

  const toggleShowThinking = async () => {
    const next = !showThinking;
    setShowThinking(next);
    await fetch(`${API}/api/dev-mode`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ show_thinking: next }),
    });
    flash(`✅ Show Thinking → ${next ? "On" : "Off"}`);
  };

  const providerModels = modelInfo?.providers?.find((p: any) => p.name === selectedProvider)?.models || [];

  return (
    <>
      <div className="page-header">
        <span className="page-title">⚙️ Settings</span>
        {toast && <span className="channel-badge online" style={{ animation: "fadeIn 0.3s ease" }}>{toast}</span>}
      </div>
      <div className="page-body">

        {/* ── Provider & Model ─────────────────────────── */}
        <div className="settings-section">
          <div className="settings-section-title">🤖 Model & Provider</div>
          <div className="card">
            <div className="card-body" style={{ display: "flex", flexDirection: "column", gap: 20 }}>
              {/* Current model display */}
              <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 16px", background: "var(--surface-2)", borderRadius: 12 }}>
                <span style={{ fontSize: 24 }}>🧠</span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 11, color: "var(--text-tertiary)", textTransform: "uppercase", letterSpacing: 1 }}>Active Model</div>
                  <div style={{ fontSize: 18, fontWeight: 700, color: "var(--accent)" }}>{selectedModel || "Loading..."}</div>
                </div>
              </div>

              {/* Provider selector */}
              <div>
                <label style={{ fontSize: 12, color: "var(--text-secondary)", display: "block", marginBottom: 8, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>Provider</label>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  {(modelInfo?.providers || []).map((p: any) => (
                    <button key={p.name} onClick={() => setSelectedProvider(p.name)}
                      className={`settings-btn ${selectedProvider === p.name ? "active" : ""}`}>
                      {p.display}
                    </button>
                  ))}
                </div>
              </div>

              {/* Quick pick models */}
              {providerModels.length > 0 && (
                <div>
                  <label style={{ fontSize: 12, color: "var(--text-secondary)", display: "block", marginBottom: 8, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>Quick Picks</label>
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    {providerModels.map((m: string) => {
                      const fullModel = selectedProvider === "openrouter" ? `openrouter/${m}` : `${selectedProvider}/${m}`;
                      const isActive = selectedModel === fullModel;
                      return (
                        <button key={m} onClick={() => changeModel(fullModel)}
                          className={`settings-btn ${isActive ? "active" : ""}`}>
                          {m}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Custom model input */}
              <div>
                <label style={{ fontSize: 12, color: "var(--text-secondary)", display: "block", marginBottom: 8, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>Any Model</label>
                <div style={{ display: "flex", gap: 8 }}>
                  <input
                    type="text"
                    className="settings-input"
                    placeholder="e.g. openai/gpt-5.5 or google/gemini-2.5-pro"
                    value={customModel}
                    onChange={(e) => setCustomModel(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter") changeModel(customModel); }}
                  />
                  <button className="settings-btn active" onClick={() => changeModel(customModel)}
                    style={{ whiteSpace: "nowrap" }} disabled={!customModel.trim()}>
                    Apply
                  </button>
                </div>
                <div style={{ fontSize: 12, color: "var(--text-tertiary)", marginTop: 8 }}>
                  Type <strong>provider/model-name</strong> — any model supported by LiteLLM works.<br />
                  Examples: <code style={{ color: "var(--accent)" }}>openai/gpt-5.5</code>, <code style={{ color: "var(--accent)" }}>openrouter/anthropic/claude-sonnet-4</code>, <code style={{ color: "var(--accent)" }}>ollama/qwen3</code>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* ── OAuth Web Accounts ─────────────────────────── */}
        <div className="settings-section" style={{ marginTop: 32 }}>
          <div className="settings-section-title">🌐 OAuth Web Accounts (Zero-Cost APIs)</div>
          <div className="card">
            <div className="card-body" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <div style={{ color: "var(--text-secondary)", fontSize: 14 }}>
                Connect your ChatGPT Plus or Claude Pro web sessions to use them inside NexAlfa without API costs.
              </div>
              
              <div style={{ display: "flex", alignItems: "center", gap: 16, background: "var(--surface-2)", padding: 16, borderRadius: 12 }}>
                <span style={{ fontSize: 24 }}>🟢</span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600 }}>ChatGPT Plus</div>
                  <div style={{ fontSize: 12, color: "var(--text-tertiary)" }}>Status: Disconnected</div>
                </div>
                <button className="settings-btn" onClick={() => flash("Paste your OpenAI session token in chat: /connect openai <token>")}>
                  Link Account
                </button>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: 16, background: "var(--surface-2)", padding: 16, borderRadius: 12 }}>
                <span style={{ fontSize: 24 }}>🟣</span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600 }}>Claude Pro</div>
                  <div style={{ fontSize: 12, color: "var(--text-tertiary)" }}>Status: Disconnected</div>
                </div>
                <button className="settings-btn" onClick={() => flash("Paste your Anthropic session token in chat: /connect anthropic <token>")}>
                  Link Account
                </button>
              </div>
            </div>
          </div>
        </div>


        {/* ── Thinking Level ──────────────────────────── */}
        <div className="settings-section">
          <div className="settings-section-title">💭 Thinking / Reasoning Level</div>
          <div className="card">
            <div className="card-body" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>
                Controls how much reasoning the model does before answering. Higher = more thorough but slower.
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                {[
                  { level: "none", icon: "⚡", label: "None", desc: "Instant responses" },
                  { level: "low", icon: "💡", label: "Low", desc: "Light reasoning" },
                  { level: "medium", icon: "🧠", label: "Medium", desc: "Balanced" },
                  { level: "high", icon: "🔬", label: "High", desc: "Deep thinking" },
                ].map(({ level, icon, label, desc }) => (
                  <button key={level} onClick={() => changeThinking(level)}
                    className={`settings-btn-lg ${thinkingLevel === level ? "active" : ""}`}
                    style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 4, padding: "14px 8px" }}>
                    <span style={{ fontSize: 20 }}>{icon}</span>
                    <span style={{ fontWeight: 600, fontSize: 13 }}>{label}</span>
                    <span style={{ fontSize: 10, color: thinkingLevel === level ? "rgba(255,255,255,0.7)" : "var(--text-tertiary)" }}>{desc}</span>
                  </button>
                ))}
              </div>
              <div style={{ fontSize: 12, color: "var(--text-tertiary)" }}>
                💡 Chat shortcut: <code style={{ color: "var(--accent)" }}>/think high</code>
              </div>
            </div>
          </div>
        </div>

        {/* ── Temperature ─────────────────────────────── */}
        <div className="settings-section">
          <div className="settings-section-title">🌡️ Temperature</div>
          <div className="card">
            <div className="card-body" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: 13, color: "var(--text-secondary)" }}>
                  Lower = more focused & deterministic. Higher = more creative & random.
                </span>
                <span style={{ fontWeight: 700, fontSize: 20, color: "var(--accent)", minWidth: 40, textAlign: "right" }}>
                  {temperature.toFixed(1)}
                </span>
              </div>
              <input type="range" min="0" max="2" step="0.1" value={temperature}
                onChange={(e) => setTemperature(parseFloat(e.target.value))}
                onMouseUp={() => changeTemp(temperature)}
                onTouchEnd={() => changeTemp(temperature)}
                className="settings-slider" />
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "var(--text-tertiary)" }}>
                <span>0.0 — Precise</span>
                <span>0.7 — Balanced</span>
                <span>2.0 — Creative</span>
              </div>
            </div>
          </div>
        </div>

        {/* ── Dev Mode ────────────────────────────────── */}
        <div className="settings-section">
          <div className="settings-section-title">🛠️ Dev Mode</div>
          <div className="card">
            <div className="card-body" style={{ padding: 0 }}>
              <div className="settings-item" style={{ cursor: "pointer" }} onClick={toggleShowThinking}>
                <div>
                  <span className="settings-key">Show Thinking</span>
                  <div style={{ fontSize: 12, color: "var(--text-tertiary)" }}>Display the model&apos;s reasoning process</div>
                </div>
                <div className={`settings-toggle ${showThinking ? "on" : ""}`}>
                  <div className="settings-toggle-dot" />
                </div>
              </div>
              <div className="settings-item">
                <span className="settings-key">Agent Name</span>
                <span className="settings-value">{status?.agent_name || "Nex"}</span>
              </div>
              <div className="settings-item">
                <span className="settings-key">Gateway</span>
                <span className="settings-value">localhost:18789</span>
              </div>
              <div className="settings-item">
                <span className="settings-key">Fallback Models</span>
                <span className="settings-value" style={{ fontSize: 12 }}>{modelInfo?.fallback_models?.join(", ") || "None"}</span>
              </div>
            </div>
          </div>
        </div>

      </div>
    </>
  );
}

