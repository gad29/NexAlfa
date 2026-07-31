/**
 * NexAlfa WebSocket Client — real-time connection to the gateway.
 */
import { io, Socket } from 'socket.io-client';

const GATEWAY_URL = process.env.NEXT_PUBLIC_API_URL ?? (process.env.NODE_ENV === 'development' ? 'http://localhost:18789' : '');

let socket: Socket | null = null;

export function getSocket(): Socket {
  if (!socket) {
    socket = io(GATEWAY_URL, {
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionAttempts: 10,
    });
    socket.on('connect', () => console.log('🔌 Connected to NexAlfa Gateway'));
    socket.on('disconnect', () => console.log('🔌 Disconnected from Gateway'));
    socket.on('connect_error', (err) => console.error('Connection error:', err.message));
  }
  return socket;
}

export function disconnectSocket() {
  if (socket) { socket.disconnect(); socket = null; }
}

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  thinking?: string;
  channel?: string;
  timestamp: number;
  isStreaming?: boolean;
}

export interface AgentStatus {
  agent_name: string;
  model: {
    current_model: string;
    thinking_level: string;
    fallback_models: string[];
    streaming: boolean;
    temperature: number;
  };
  sessions: {
    total_sessions: number;
    active_sessions: number;
    total_messages: number;
    channels: string[];
  };
  memory: {
    total_messages: number;
    total_memories: number;
    user_facts: number;
    conversations_indexed: number;
    memories_indexed: number;
  };
  channels: Array<{
    name: string;
    display_name: string;
    configured: boolean;
    running: boolean;
  }>;
  dev_mode: boolean;
}
