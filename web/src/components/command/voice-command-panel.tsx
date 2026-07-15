import {
  Loader2,
  Mic,
  MicOff,
  Navigation,
  ShieldOff,
  Volume2,
  X,
} from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';

const T = {
  bg: '#0d0d0d',
  surface: 'rgba(255,255,255,0.025)',
  border: 'rgba(255,255,255,0.08)',
  accent: '#c9b787',
  text: '#f5f5f5',
  textDim: '#8a8a8a',
  textMuted: '#5e5e5e',
  mono: 'ui-monospace, SFMono-Regular, Menlo, monospace',
  red: '#ef4444',
  green: '#22c55e',
};

// ---------------------------------------------------------------------------
// Navigation intent parsing
// ---------------------------------------------------------------------------

/**
 * Maps spoken artifact/section names to their URL paths.
 * External app paths trigger a full page navigation (window.location.href).
 * Internal Command paths use wouter navigation.
 */
const ARTIFACT_ROUTE_MAP: Array<{ keywords: string[]; path: string; label: string; external: boolean }> = [
  // External ecosystem apps
  { keywords: ['aegis', 'sentra', 'defense', 'cyber', 'cyber resilience', 'intelligence command', 'cyber command'], path: '/sentra/', label: 'TENAX', external: true },
  { keywords: ['vessels', 'maritime', 'fleet', 'ship'], path: '/vessels/', label: 'SEXTANT', external: true },
  { keywords: ['terra', 'real estate'], path: '/terra/', label: 'DOMAINE', external: true },
  { keywords: ['counsel', 'legal', 'matter command'], path: '/counsel/', label: 'Counsel', external: true },
  { keywords: ['pulse', 'briefing', 'executive briefing'], path: '/pulse/', label: 'Pulse', external: true },
  { keywords: ['a11oy', 'continuum', 'brand orchestration'], path: '/a11oy/', label: 'A11oy', external: true },
  { keywords: ['holdings', 'szl holdings', 'portfolio dashboard'], path: '/szl-holdings/', label: 'SZL Holdings', external: true },
  { keywords: ['lexicon', 'license intelligence', 'license catalog'], path: '/governance/lexicon', label: 'LEXICON', external: false },
  // Internal Command routes
  { keywords: ['strategy', 'strategic overview'], path: '/strategy', label: 'Strategy', external: false },
  { keywords: ['operations', 'live operations', 'ops'], path: '/operations/live', label: 'Live Operations', external: false },
  { keywords: ['agents', 'agent monitor', 'agent runtime'], path: '/agents', label: 'Agents', external: false },
  { keywords: ['omnia', 'world model'], path: '/omnia', label: 'OMNIA', external: false },
  { keywords: ['cognitive', 'cognitive loop'], path: '/cognitive', label: 'Cognitive', external: false },
  { keywords: ['infrastructure', 'global fabric'], path: '/infrastructure', label: 'Infrastructure', external: false },
  { keywords: ['approvals', 'hitl', 'approval queue'], path: '/substrate/approvals', label: 'Approvals', external: false },
  { keywords: ['evolution', 'evolution runtime'], path: '/evolution', label: 'Evolution', external: false },
  { keywords: ['forge', 'tool intelligence'], path: '/operations/forge', label: 'Forge', external: false },
];

// ---------------------------------------------------------------------------
// Approval intent detection
// ---------------------------------------------------------------------------

const APPROVAL_INTENT_WORDS = [
  'approve', 'approved', 'confirm', 'confirmed', 'authorize', 'authorise',
  'proceed', 'yes proceed', 'go ahead', 'i approve', 'i confirm',
];

interface ApprovalResult {
  actionId: string;
  actionLabel: string;
  transcript: string;
  approved: boolean;
  reason?: string;
}

function detectApprovalIntent(userText: string): { detected: boolean; actionLabel: string } {
  const lower = userText.toLowerCase();
  const detected = APPROVAL_INTENT_WORDS.some((w) => lower.includes(w));
  const match = lower.match(/(?:approve|confirm|authorize)\s+(?:the\s+)?(.{3,60}?)(?:\s|$)/);
  const actionLabel = match ? match[1].trim() : 'pending action';
  return { detected, actionLabel };
}

/** Navigation trigger phrases the assistant will produce */
const NAV_TRIGGER_PATTERNS = [
  /navigating\s+(?:you\s+)?to\s+(.+?)(?:\.|$)/i,
  /taking\s+you\s+to\s+(.+?)(?:\.|$)/i,
  /opening\s+(.+?)(?:\.|$)/i,
  /switching\s+to\s+(.+?)(?:\.|$)/i,
  /going\s+to\s+(.+?)(?:\.|$)/i,
  /i(?:'ll|'m going to)\s+navigate\s+(?:you\s+)?to\s+(.+?)(?:\.|$)/i,
];

interface NavigationIntent {
  path: string;
  label: string;
  external: boolean;
}

function parseNavigationIntent(text: string): NavigationIntent | null {
  const lowerText = text.toLowerCase();

  // Check for explicit navigation phrases
  for (const pattern of NAV_TRIGGER_PATTERNS) {
    const match = lowerText.match(pattern);
    if (match) {
      const target = match[1]?.trim() ?? '';
      for (const route of ARTIFACT_ROUTE_MAP) {
        if (route.keywords.some((kw) => target.includes(kw))) {
          return { path: route.path, label: route.label, external: route.external };
        }
      }
    }
  }

  // Fallback: check if any artifact keyword appears in a navigation context
  const navContextWords = ['navigate', 'go', 'open', 'switch', 'take you', 'heading'];
  const hasNavContext = navContextWords.some((w) => lowerText.includes(w));
  if (hasNavContext) {
    for (const route of ARTIFACT_ROUTE_MAP) {
      if (route.keywords.some((kw) => lowerText.includes(kw))) {
        return { path: route.path, label: route.label, external: route.external };
      }
    }
  }

  return null;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  navigationIntent?: NavigationIntent;
}

function getApiBase() {
  const base = import.meta.env.BASE_URL?.replace(/\/$/, '') || '';
  return `${base}/api`;
}

async function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      resolve(result.split(',')[1] ?? '');
    };
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}

interface VoiceCommandPanelProps {
  open: boolean;
  onClose: () => void;
  /** Called when the assistant produces a navigation intent. Path may be external or internal. */
  onNavigate?: (path: string, external: boolean) => void;
}

export function VoiceCommandPanel({ open, onClose, onNavigate }: VoiceCommandPanelProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [privacyMode, setPrivacyMode] = useState(false);
  const [userTranscript, setUserTranscript] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingNavIntent, setPendingNavIntent] = useState<NavigationIntent | null>(null);
  const [lastApproval, setLastApproval] = useState<ApprovalResult | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const objectUrlRef = useRef<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const conversationIdRef = useRef<string | null>(null);
  /** Real pending approvals fetched from the DB on panel open — used for voice approvals. */
  const pendingApprovalsRef = useRef<Array<{ id: number; title: string }>>([]);

  // Create a conversation session and fetch pending approvals when the panel opens
  useEffect(() => {
    if (!open) return;
    setMessages([]);
    setPendingNavIntent(null);
    conversationIdRef.current = null;
    pendingApprovalsRef.current = [];

    const abort = new AbortController();

    // Create conversation session (non-fatal if fails)
    fetch(`${getApiBase()}/openai/conversations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      signal: abort.signal,
    })
      .then((r) => r.json())
      .then((data: { id?: string | number }) => {
        if (data.id) conversationIdRef.current = String(data.id);
      })
      .catch(() => { /* non-fatal */ });

    // Fetch real pending approvals so voice-approval calls use actual DB IDs
    fetch(`${getApiBase()}/approvals?status=pending&limit=20`, {
      credentials: 'include',
      signal: abort.signal,
    })
      .then((r) => r.ok ? r.json() : null)
      .then((resp: { data?: Array<{ id: number; title: string }> } | Array<{ id: number; title: string }> | null) => {
        // Handles both sendSuccess shapes: raw array OR { data, meta } envelope
        const list: Array<{ id: number; title: string }> = Array.isArray(resp)
          ? resp
          : (resp as { data?: Array<{ id: number; title: string }> })?.data ?? [];
        pendingApprovalsRef.current = list.map((a) => ({ id: a.id, title: a.title }));
      })
      .catch(() => { /* non-fatal — approval list unavailable */ });

    return () => abort.abort();
  }, [open]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, userTranscript]);

  useEffect(() => {
    return () => {
      mediaRecorderRef.current?.stop();
      audioRef.current?.pause();
      if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
      abortRef.current?.abort();
    };
  }, []);

  const stopAudio = useCallback(() => {
    abortRef.current?.abort();
    audioRef.current?.pause();
    if (objectUrlRef.current) {
      URL.revokeObjectURL(objectUrlRef.current);
      objectUrlRef.current = null;
    }
    setIsPlaying(false);
  }, []);

  const executeNavigation = useCallback(
    (intent: NavigationIntent) => {
      if (onNavigate) {
        onNavigate(intent.path, intent.external);
      } else if (intent.external) {
        window.location.href = intent.path;
      }
      setPendingNavIntent(null);
      onClose();
    },
    [onNavigate, onClose],
  );

  const handleMicPress = useCallback(async () => {
    if (privacyMode) return;

    if (isRecording) {
      setIsRecording(false);
      mediaRecorderRef.current?.stop();
      return;
    }

    setError(null);
    setPendingNavIntent(null);
    audioChunksRef.current = [];

    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      setError('Microphone access denied. Check browser permissions.');
      return;
    }

    const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
      ? 'audio/webm;codecs=opus'
      : 'audio/webm';

    const recorder = new MediaRecorder(stream, { mimeType });
    mediaRecorderRef.current = recorder;

    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) audioChunksRef.current.push(e.data);
    };

    recorder.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop());
      const blob = new Blob(audioChunksRef.current, { type: mimeType });
      audioChunksRef.current = [];
      mediaRecorderRef.current = null;

      if (blob.size < 1000) return;

      setIsProcessing(true);
      stopAudio();

      try {
        const base64 = await blobToBase64(blob);

        const abort = new AbortController();
        abortRef.current = abort;

        const body: Record<string, string> = { audio: base64 };
        if (conversationIdRef.current) body.conversationId = conversationIdRef.current;

        const res = await fetch(`${getApiBase()}/openai/voice-query`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
          credentials: 'include',
          signal: abort.signal,
        });

        if (!res.ok) throw new Error('Voice query failed');

        const data = await res.json() as {
          userTranscript?: string;
          assistantTranscript?: string;
          audioBase64?: string;
          provenance?: { conversationId?: string };
        };

        // Update conversationId if server assigned/echoed one
        if (data.provenance?.conversationId && !conversationIdRef.current) {
          conversationIdRef.current = data.provenance.conversationId;
        }

        const userText = data.userTranscript?.trim() || userTranscript || 'Voice query';
        const assistantText = data.assistantTranscript?.trim() || 'No response received.';

        // Check for approval intent in the user's transcript
        const { detected: hasApprovalIntent, actionLabel } = detectApprovalIntent(userText);
        if (hasApprovalIntent && pendingApprovalsRef.current.length > 0) {
          // Match the spoken action label against real pending approvals; default to first pending
          const matched = pendingApprovalsRef.current.find(
            (a) => actionLabel && a.title.toLowerCase().includes(actionLabel.toLowerCase()),
          ) ?? pendingApprovalsRef.current[0];

          fetch(`${getApiBase()}/openai/voice-approval`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              pendingActionId: matched.id,
              transcript: userText,
              ...(conversationIdRef.current ? { conversationId: conversationIdRef.current } : {}),
            }),
            credentials: 'include',
          })
            .then((r) => r.json())
            .then((result: { approved?: boolean; reason?: string }) => {
              setLastApproval({
                actionId: String(matched.id),
                actionLabel: matched.title,
                transcript: userText,
                approved: result.approved ?? false,
                reason: result.reason,
              });
              // Remove approved item from local ref to prevent re-submission
              if (result.approved) {
                pendingApprovalsRef.current = pendingApprovalsRef.current.filter(
                  (a) => a.id !== matched.id,
                );
              }
              setTimeout(() => setLastApproval(null), 8000);
            })
            .catch(() => {/* non-fatal */});
        } else if (hasApprovalIntent && pendingApprovalsRef.current.length === 0) {
          // Intent detected but no real pending approvals available
          setLastApproval({
            actionId: 'none',
            actionLabel,
            transcript: userText,
            approved: false,
            reason: 'No pending approvals in queue — nothing to approve',
          });
          setTimeout(() => setLastApproval(null), 6000);
        }

        // Check for navigation intent
        const navIntent = parseNavigationIntent(assistantText);

        setUserTranscript('');
        setMessages((prev) => [
          ...prev,
          {
            id: `user-${Date.now()}`,
            role: 'user',
            content: userText,
            timestamp: new Date(),
          },
          {
            id: `asst-${Date.now()}`,
            role: 'assistant',
            content: assistantText,
            timestamp: new Date(),
            navigationIntent: navIntent ?? undefined,
          },
        ]);

        if (navIntent) {
          setPendingNavIntent(navIntent);
        }

        if (data.audioBase64 && !abort.signal.aborted) {
          const audioBytes = Uint8Array.from(atob(data.audioBase64), (c) => c.charCodeAt(0));
          const audioBlob = new Blob([audioBytes], { type: 'audio/mpeg' });
          const url = URL.createObjectURL(audioBlob);
          objectUrlRef.current = url;

          const audio = new Audio(url);
          audioRef.current = audio;
          setIsPlaying(true);

          audio.onended = () => {
            setIsPlaying(false);
            URL.revokeObjectURL(url);
            objectUrlRef.current = null;
            // Auto-execute navigation after audio finishes (if still pending)
            if (navIntent) {
              setPendingNavIntent((current) => {
                if (current) executeNavigation(current);
                return null;
              });
            }
          };
          audio.onerror = () => setIsPlaying(false);
          abort.signal.addEventListener('abort', () => audio.pause());
          audio.play().catch(() => setIsPlaying(false));
        } else if (navIntent) {
          // No audio — navigate immediately after a short delay
          setTimeout(() => executeNavigation(navIntent), 800);
        }
      } catch (err) {
        if ((err as Error).name !== 'AbortError') {
          setError('Voice processing failed. Please try again.');
        }
      } finally {
        setIsProcessing(false);
      }
    };

    recorder.start();
    setIsRecording(true);
    setUserTranscript('Recording…');
  }, [privacyMode, isRecording, userTranscript, stopAudio, executeNavigation]);

  // When privacy mode is enabled mid-recording, immediately stop the mic
  useEffect(() => {
    if (privacyMode && isRecording) {
      mediaRecorderRef.current?.stop();
      setIsRecording(false);
      setUserTranscript('');
    }
  }, [privacyMode, isRecording]);

  const handleClose = useCallback(() => {
    if (isRecording) {
      mediaRecorderRef.current?.stop();
      setIsRecording(false);
    }
    stopAudio();
    onClose();
  }, [isRecording, stopAudio, onClose]);

  const isBusy = isProcessing || isPlaying;

  if (!open) return null;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        display: 'flex',
        alignItems: 'flex-end',
        justifyContent: 'flex-end',
        pointerEvents: 'none',
      }}
    >
      <div
        style={{
          pointerEvents: 'all',
          width: 360,
          maxHeight: '70vh',
          margin: '0 24px 80px 0',
          background: T.bg,
          border: `1px solid ${T.border}`,
          borderRadius: 12,
          boxShadow: '0 24px 80px rgba(0,0,0,0.6)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        {/* Header */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '12px 16px',
            borderBottom: `1px solid ${T.border}`,
            flexShrink: 0,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div
              style={{
                width: 8,
                height: 8,
                borderRadius: '50%',
                background: isRecording
                  ? T.red
                  : isPlaying
                    ? T.accent
                    : pendingNavIntent
                      ? T.green
                      : 'rgba(255,255,255,0.2)',
                boxShadow: isRecording
                  ? `0 0 8px ${T.red}`
                  : isPlaying
                    ? `0 0 8px ${T.accent}`
                    : pendingNavIntent
                      ? `0 0 8px ${T.green}`
                      : 'none',
                transition: 'all 0.3s',
              }}
            />
            <span
              style={{
                fontSize: '0.75rem',
                fontWeight: 600,
                fontFamily: T.mono,
                color: T.textDim,
                letterSpacing: '0.06em',
                textTransform: 'uppercase',
              }}
            >
              Command Voice
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <button
              type="button"
              onClick={() => setPrivacyMode((p) => !p)}
              title={privacyMode ? 'Privacy mode on — mic muted' : 'Enable privacy mode'}
              style={{
                padding: 4,
                background: privacyMode ? 'rgba(239,68,68,0.15)' : 'none',
                border: privacyMode
                  ? '1px solid rgba(239,68,68,0.3)'
                  : '1px solid transparent',
                borderRadius: 4,
                color: privacyMode ? T.red : T.textMuted,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <ShieldOff style={{ width: 13, height: 13 }} />
            </button>
            <button
              type="button"
              onClick={handleClose}
              style={{
                padding: 4,
                background: 'none',
                border: 'none',
                color: T.textMuted,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <X style={{ width: 13, height: 13 }} />
            </button>
          </div>
        </div>

        {/* Voice approval confirmation banner */}
        {lastApproval && (
          <div
            style={{
              padding: '8px 16px',
              background: lastApproval.approved ? 'rgba(34,197,94,0.06)' : 'rgba(239,68,68,0.06)',
              borderBottom: `1px solid ${lastApproval.approved ? 'rgba(34,197,94,0.2)' : 'rgba(239,68,68,0.2)'}`,
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              flexShrink: 0,
            }}
          >
            <span
              style={{
                fontSize: '0.68rem',
                color: lastApproval.approved ? T.green : T.red,
                fontFamily: T.mono,
              }}
            >
              {lastApproval.approved
                ? `✓ Voice approval recorded — "${lastApproval.actionLabel}"`
                : `✗ Approval not confirmed — rephrase with "approve" or "confirm"`}
            </span>
          </div>
        )}

        {/* Privacy mode banner */}
        {privacyMode && (
          <div
            style={{
              padding: '8px 16px',
              background: 'rgba(239,68,68,0.06)',
              borderBottom: `1px solid rgba(239,68,68,0.15)`,
              display: 'flex',
              alignItems: 'center',
              gap: 6,
            }}
          >
            <ShieldOff style={{ width: 11, height: 11, color: T.red }} />
            <span style={{ fontSize: '0.68rem', color: T.red, fontFamily: T.mono }}>
              Privacy mode — microphone muted
            </span>
          </div>
        )}

        {/* Pending navigation intent banner */}
        {pendingNavIntent && (
          <div
            style={{
              padding: '8px 16px',
              background: 'rgba(34,197,94,0.06)',
              borderBottom: `1px solid rgba(34,197,94,0.18)`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 8,
              flexShrink: 0,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <Navigation style={{ width: 11, height: 11, color: T.green }} />
              <span style={{ fontSize: '0.68rem', color: T.green, fontFamily: T.mono }}>
                Navigate to {pendingNavIntent.label}?
              </span>
            </div>
            <div style={{ display: 'flex', gap: 6 }}>
              <button
                type="button"
                onClick={() => executeNavigation(pendingNavIntent)}
                style={{
                  padding: '2px 8px',
                  background: 'rgba(34,197,94,0.15)',
                  border: '1px solid rgba(34,197,94,0.35)',
                  borderRadius: 4,
                  color: T.green,
                  fontSize: '0.65rem',
                  fontFamily: T.mono,
                  cursor: 'pointer',
                }}
              >
                Go
              </button>
              <button
                type="button"
                onClick={() => setPendingNavIntent(null)}
                style={{
                  padding: '2px 8px',
                  background: 'none',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: 4,
                  color: T.textMuted,
                  fontSize: '0.65rem',
                  fontFamily: T.mono,
                  cursor: 'pointer',
                }}
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* Message thread */}
        <div
          ref={scrollRef}
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: '12px 16px',
            display: 'flex',
            flexDirection: 'column',
            gap: 10,
            minHeight: 0,
          }}
        >
          {messages.length === 0 && !userTranscript && !isProcessing && (
            <div
              style={{
                textAlign: 'center',
                padding: '24px 16px',
                color: T.textMuted,
                fontSize: '0.75rem',
                fontFamily: T.mono,
                lineHeight: 1.6,
              }}
            >
              <Mic
                style={{
                  width: 28,
                  height: 28,
                  color: T.accent,
                  margin: '0 auto 12px',
                  opacity: 0.5,
                }}
              />
              <div>Speak to navigate, query, or approve actions</div>
              <div style={{ marginTop: 6, fontSize: '0.63rem', color: T.textMuted }}>
                "Show me active threats" · "Navigate to PARAGON" · "Read my briefing"
              </div>
            </div>
          )}

          {messages.map((msg) => (
            <div
              key={msg.id}
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start',
                gap: 3,
              }}
            >
              <div
                style={{
                  maxWidth: '85%',
                  padding: '8px 12px',
                  borderRadius: msg.role === 'user' ? '10px 10px 2px 10px' : '10px 10px 10px 2px',
                  background:
                    msg.role === 'user'
                      ? `${T.accent}18`
                      : msg.navigationIntent
                        ? 'rgba(34,197,94,0.06)'
                        : T.surface,
                  border: `1px solid ${
                    msg.role === 'user'
                      ? `${T.accent}30`
                      : msg.navigationIntent
                        ? 'rgba(34,197,94,0.2)'
                        : T.border
                  }`,
                  fontSize: '0.81rem',
                  color: T.text,
                  lineHeight: 1.5,
                }}
              >
                {msg.content}
                {msg.navigationIntent && (
                  <div
                    style={{
                      marginTop: 6,
                      display: 'flex',
                      alignItems: 'center',
                      gap: 4,
                      fontSize: '0.65rem',
                      color: T.green,
                      fontFamily: T.mono,
                    }}
                  >
                    <Navigation style={{ width: 9, height: 9 }} />
                    Route: {msg.navigationIntent.label}
                  </div>
                )}
              </div>
              <span
                style={{
                  fontSize: '0.58rem',
                  color: T.textMuted,
                  fontFamily: T.mono,
                  padding: '0 4px',
                }}
              >
                {msg.role === 'user' ? 'You' : 'Command'}
                {' · '}
                {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
            </div>
          ))}

          {userTranscript && (
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'flex-end',
                gap: 3,
                opacity: 0.7,
              }}
            >
              <div
                style={{
                  maxWidth: '85%',
                  padding: '8px 12px',
                  borderRadius: '10px 10px 2px 10px',
                  background: `${T.accent}0a`,
                  border: `1px dashed ${T.accent}25`,
                  fontSize: '0.81rem',
                  color: T.textDim,
                  lineHeight: 1.5,
                }}
              >
                {userTranscript}
              </div>
            </div>
          )}

          {isProcessing && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                fontSize: '0.75rem',
                color: T.accent,
                fontFamily: T.mono,
                padding: '4px 0',
              }}
            >
              <Loader2 style={{ width: 12, height: 12, animation: 'spin 1s linear infinite' }} />
              Processing voice query…
            </div>
          )}

          {error && (
            <div
              style={{
                padding: '8px 12px',
                borderRadius: 6,
                background: 'rgba(239,68,68,0.06)',
                border: '1px solid rgba(239,68,68,0.2)',
                fontSize: '0.75rem',
                color: T.red,
              }}
            >
              {error}
            </div>
          )}
        </div>

        {/* Controls */}
        <div
          style={{
            padding: '12px 16px',
            borderTop: `1px solid ${T.border}`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 16,
            flexShrink: 0,
          }}
        >
          {isPlaying && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                fontSize: '0.68rem',
                color: T.accent,
                fontFamily: T.mono,
              }}
            >
              <Volume2 style={{ width: 12, height: 12 }} />
              Speaking…
            </div>
          )}

          {!isBusy && (
            <button
              type="button"
              onClick={handleMicPress}
              disabled={privacyMode}
              title={
                privacyMode
                  ? 'Privacy mode is on — mic muted'
                  : isRecording
                    ? 'Tap to send'
                    : 'Tap to speak'
              }
              style={{
                width: 52,
                height: 52,
                borderRadius: '50%',
                border: `2px solid ${
                  isRecording ? T.red : privacyMode ? 'rgba(255,255,255,0.1)' : T.accent
                }`,
                background: isRecording
                  ? 'rgba(239,68,68,0.12)'
                  : privacyMode
                    ? 'rgba(255,255,255,0.03)'
                    : `${T.accent}10`,
                color: isRecording ? T.red : privacyMode ? T.textMuted : T.accent,
                cursor: privacyMode ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                transition: 'all 0.2s',
                boxShadow: isRecording ? `0 0 20px rgba(239,68,68,0.25)` : 'none',
              }}
            >
              {isRecording ? (
                <MicOff style={{ width: 20, height: 20 }} />
              ) : (
                <Mic style={{ width: 20, height: 20 }} />
              )}
            </button>
          )}

          {isProcessing && !isPlaying && (
            <Loader2
              style={{
                width: 24,
                height: 24,
                color: T.accent,
                animation: 'spin 1s linear infinite',
              }}
            />
          )}
        </div>

        <div
          style={{
            padding: '6px 16px 10px',
            fontSize: '0.58rem',
            color: T.textMuted,
            fontFamily: T.mono,
            textAlign: 'center',
          }}
        >
          {isRecording
            ? 'Recording — tap mic to send'
            : isProcessing
              ? 'Processing your query…'
              : isPlaying
                ? 'Command is responding…'
                : pendingNavIntent
                  ? `Ready to navigate to ${pendingNavIntent.label}`
                  : 'Tap mic to speak'}
        </div>
      </div>
    </div>
  );
}
