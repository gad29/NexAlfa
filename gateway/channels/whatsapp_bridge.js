/**
 * NexAlfa WhatsApp Web Bridge
 * Uses Baileys (@whiskeysockets/baileys) for WhatsApp Web WebSocket connection.
 * Runs on port 3001. Relays QR codes, message events, and HTTP send requests.
 */

const express = require('express');
const cors = require('cors');
const QRCode = require('qrcode');
const fs = require('fs');
const path = require('path');
const {
  default: makeWASocket,
  useMultiFileAuthState,
  DisconnectReason,
  fetchLatestBaileysVersion,
  isJidBroadcast,
} = require('@whiskeysockets/baileys');

const PORT = process.env.WHATSAPP_BRIDGE_PORT || 3001;
const GATEWAY_URL = process.env.GATEWAY_URL || 'http://localhost:18789';
const SESSION_DIR = process.env.SESSION_DIR || path.join(__dirname, '../../storage/whatsapp-session');

let sock = null;
let isConnected = false;
let currentQr = null;

// Express app setup
const app = express();
app.use(cors());
app.use(express.json());

// Send message endpoint
app.post('/send', async (req, res) => {
  const { to, message } = req.body;
  if (!to || !message) {
    return res.status(400).json({ error: 'to and message fields are required' });
  }
  if (!sock || !isConnected) {
    return res.status(503).json({ error: 'WhatsApp bridge is not connected yet' });
  }

  try {
    let formattedJid = to.includes('@s.whatsapp.net') ? to : `${to.replace(/[^0-9]/g, '')}@s.whatsapp.net`;
    await sock.sendMessage(formattedJid, { text: message });
    return res.json({ status: 'ok', sent_to: formattedJid });
  } catch (err) {
    console.error('❌ Failed to send WhatsApp message:', err.message);
    return res.status(500).json({ error: err.message });
  }
});

// Health endpoint
app.get('/health', (req, res) => {
  return res.json({
    status: 'ok',
    connected: isConnected,
    has_qr: !!currentQr,
  });
});

// Helper: Post JSON to Python Gateway
async function postToGateway(endpoint, data) {
  try {
    const fetch = (await import('node-fetch')).default || globalThis.fetch;
    await fetch(`${GATEWAY_URL}${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
  } catch (err) {
    // Gateway might be restarting, ignore error silently
  }
}

// Start Baileys socket connection
async function connectToWhatsApp() {
  if (!fs.existsSync(SESSION_DIR)) {
    fs.mkdirSync(SESSION_DIR, { recursive: true });
  }

  const { state, saveCreds } = await useMultiFileAuthState(SESSION_DIR);
  const { version } = await fetchLatestBaileysVersion().catch(() => ({ version: [2, 3000, 1015901307] }));

  console.log(`🚀 WhatsApp Bridge starting (Baileys v${version.join('.')})...`);

  sock = makeWASocket({
    version,
    auth: state,
    printQRInTerminal: true,
    shouldIgnoreJid: (jid) => isJidBroadcast(jid),
  });

  sock.ev.on('creds.update', saveCreds);

  sock.ev.on('connection.update', async (update) => {
    const { connection, lastDisconnect, qr } = update;

    if (qr) {
      console.log('📱 WhatsApp QR Code generated');
      try {
        currentQr = await QRCode.toDataURL(qr);
        await postToGateway('/api/channels/whatsapp/qr', { qr: currentQr });
      } catch (err) {
        console.error('Failed to encode QR:', err);
      }
    }

    if (connection === 'close') {
      isConnected = false;
      const shouldReconnect =
        lastDisconnect?.error?.output?.statusCode !== DisconnectReason.loggedOut;
      console.log(`🔌 WhatsApp connection closed due to:`, lastDisconnect?.error, `, reconnecting:`, shouldReconnect);

      await postToGateway('/api/channels/whatsapp/status', { status: 'disconnected' });

      if (shouldReconnect) {
        setTimeout(connectToWhatsApp, 5000);
      } else {
        console.log('❌ Logged out from WhatsApp. Resetting session...');
        fs.rmSync(SESSION_DIR, { recursive: true, force: true });
        setTimeout(connectToWhatsApp, 3000);
      }
    } else if (connection === 'open') {
      console.log('✅ WhatsApp Bridge connected & ready!');
      isConnected = true;
      currentQr = null;
      await postToGateway('/api/channels/whatsapp/qr', { qr: null });
      await postToGateway('/api/channels/whatsapp/status', { status: 'connected' });
    }
  });

  // Listen to incoming messages
  sock.ev.on('messages.upsert', async ({ messages, type }) => {
    if (type !== 'notify') return;

    for (const m of messages) {
      if (m.key.fromMe) continue;
      const from = m.key.remoteJid;
      if (!from || from.includes('@g.us')) continue; // Ignore group chats for now

      const body =
        m.message?.conversation ||
        m.message?.extendedTextMessage?.text ||
        m.message?.imageMessage?.caption ||
        '';

      if (!body) continue;

      const pushName = m.pushName || 'WhatsApp User';
      console.log(`📩 Incoming WhatsApp message from ${pushName} (${from}): ${body.substring(0, 50)}...`);

      await postToGateway('/webhook/whatsapp', {
        from: from,
        sender_name: pushName,
        message: body,
      });
    }
  });
}

// Start HTTP server and connect to WhatsApp
app.listen(PORT, '0.0.0.0', () => {
  console.log(`🚀 WhatsApp Bridge HTTP server listening on port ${PORT}`);
  connectToWhatsApp().catch((err) => console.error('Failed to start WhatsApp bridge:', err));
});
