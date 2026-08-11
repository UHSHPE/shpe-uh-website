/* eslint-disable no-unused-vars */
import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  getCommittees,
  joinCommittee,
  leaveCommittee,
  getCommitteeMembers,
  getCommitteeMessages,
  sendCommitteeMessage,
} from '../api/api';
import useDocumentTitle from "../hooks/useDocumentTitle";

function formatMessageTime(str) {
  const d = new Date(str + 'Z'); // stored UTC
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  }).format(d);
}

function MessageThread({ messages }) {
  if (messages.length === 0) {
    return <p style={{ color: '#6b7280', fontSize: '13px', margin: 0 }}>No messages yet.</p>;
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      {messages.map(m => (
        <div
          key={m.id}
          style={{
            background: '#f9fafb',
            border: '1px solid #e5e7eb',
            borderRadius: '8px',
            padding: '10px 12px',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', marginBottom: '2px' }}>
            <span style={{ fontWeight: 700, fontSize: '13px', color: 'var(--blue)' }}>{m.sender_name}</span>
            <span style={{ fontSize: '11px', color: '#9ca3af' }}>{formatMessageTime(m.created_at)}</span>
          </div>
          <p style={{ margin: 0, fontSize: '14px', color: '#374151', whiteSpace: 'pre-wrap' }}>{m.body}</p>
        </div>
      ))}
    </div>
  );
}

function ChairPanel({ committeeId, onClose }) {
  const [members, setMembers] = useState([]);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [draft, setDraft] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([getCommitteeMembers(committeeId), getCommitteeMessages(committeeId)])
      .then(([mem, msg]) => {
        setMembers(mem.data);
        setMessages(msg.data);
      })
      .catch(() => setError('Could not load committee details.'))
      .finally(() => setLoading(false));
  }, [committeeId]);

  async function handleSend() {
    const body = draft.trim();
    if (!body) return;
    setSending(true);
    try {
      const res = await sendCommitteeMessage(committeeId, body);
      setMessages(prev => [res.data, ...prev]);
      setDraft('');
    } catch {
      setError('Could not send message.');
    } finally {
      setSending(false);
    }
  }

  if (loading) return <p style={{ color: '#6b7280', fontSize: '13px', margin: '12px 0 0' }}>Loading…</p>;

  return (
    <div style={{ marginTop: '16px', borderTop: '1px solid #e5e7eb', paddingTop: '16px' }}>
      {error && <p style={{ color: '#D33A02', fontSize: '13px' }}>{error}</p>}

      <h4 style={{ margin: '0 0 8px', fontSize: '14px', color: 'var(--blue)' }}>
        Members ({members.length})
      </h4>
      {members.length === 0 ? (
        <p style={{ color: '#6b7280', fontSize: '13px', margin: 0 }}>No members have joined yet.</p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          {members.map(m => (
            <div
              key={m.id}
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                gap: '12px',
                fontSize: '13px',
                color: '#374151',
                background: '#f9fafb',
                border: '1px solid #e5e7eb',
                borderRadius: '8px',
                padding: '8px 12px',
                flexWrap: 'wrap',
              }}
            >
              <span style={{ fontWeight: 600 }}>{m.first_name} {m.last_name}</span>
              <span style={{ color: '#6b7280' }}>{m.personal_email} · {m.phone_num}</span>
            </div>
          ))}
        </div>
      )}

      <h4 style={{ margin: '20px 0 8px', fontSize: '14px', color: 'var(--blue)' }}>
        Message your committee
      </h4>
      <textarea
        value={draft}
        onChange={e => setDraft(e.target.value)}
        placeholder="Write a message to everyone in this committee…"
        rows={3}
        style={{
          width: '100%',
          boxSizing: 'border-box',
          border: '1px solid #d1d5db',
          borderRadius: '8px',
          padding: '10px 12px',
          fontSize: '14px',
          fontFamily: 'inherit',
          resize: 'vertical',
        }}
      />
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', marginTop: '8px' }}>
        <button className="ghostBtn" onClick={onClose} style={{ fontSize: '13px', padding: '6px 14px' }}>
          Close
        </button>
        <button
          className="primaryBtn"
          onClick={handleSend}
          disabled={sending || !draft.trim()}
          style={{ fontSize: '13px', padding: '6px 16px', opacity: sending || !draft.trim() ? 0.6 : 1 }}
        >
          {sending ? 'Sending…' : 'Send'}
        </button>
      </div>

      <h4 style={{ margin: '20px 0 8px', fontSize: '14px', color: 'var(--blue)' }}>Sent messages</h4>
      <MessageThread messages={messages} />
    </div>
  );
}

function MemberMessagesPanel({ committeeId, onClose }) {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    getCommitteeMessages(committeeId)
      .then(res => setMessages(res.data))
      .catch(() => setError('Could not load messages.'))
      .finally(() => setLoading(false));
  }, [committeeId]);

  return (
    <div style={{ marginTop: '16px', borderTop: '1px solid #e5e7eb', paddingTop: '16px' }}>
      {loading ? (
        <p style={{ color: '#6b7280', fontSize: '13px', margin: 0 }}>Loading messages…</p>
      ) : error ? (
        <p style={{ color: '#D33A02', fontSize: '13px', margin: 0 }}>{error}</p>
      ) : (
        <MessageThread messages={messages} />
      )}
      <button
        className="ghostBtn"
        onClick={onClose}
        style={{ fontSize: '13px', padding: '6px 14px', marginTop: '12px' }}
      >
        Close
      </button>
    </div>
  );
}

function CommitteeCard({ committee, onToggle }) {
  const [busy, setBusy] = useState(false);
  const [panelOpen, setPanelOpen] = useState(false);

  async function handleToggle() {
    setBusy(true);
    await onToggle(committee.id, committee.is_member);
    setBusy(false);
  }

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      style={{
        border: '1px solid #e5e7eb',
        borderRadius: '12px',
        padding: '20px 24px',
        background: '#fff',
        boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '16px' }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <p style={{ margin: 0, fontWeight: 700, fontSize: '16px', color: 'var(--blue)' }}>
            {committee.name}
          </p>
          <p style={{ margin: '4px 0 0', color: '#6b7280', fontSize: '14px' }}>
            {committee.description}
          </p>
          {committee.chairs?.length > 0 && (
            <div style={{ margin: '6px 0 0' }}>
              {committee.chairs.map(chair => (
                <p
                  key={`${chair.first_name} ${chair.last_name}`}
                  style={{ margin: '2px 0 0', color: '#374151', fontSize: '13px' }}
                >
                  👤 {chair.first_name} {chair.last_name} · {chair.personal_email}
                </p>
              ))}
            </div>
          )}
        </div>
        <button
          className={committee.is_member ? 'ghostBtn' : 'primaryBtn'}
          onClick={handleToggle}
          disabled={busy}
          style={{
            whiteSpace: 'nowrap',
            opacity: busy ? 0.6 : 1,
            fontSize: '14px',
            padding: '8px 18px',
            flexShrink: 0,
          }}
        >
          {committee.is_member ? 'Leave' : 'Join'}
        </button>
      </div>

      {(committee.is_chair || committee.is_member) && (
        <div style={{ marginTop: '12px' }}>
          <button
            className="ghostBtn"
            onClick={() => setPanelOpen(o => !o)}
            style={{ fontSize: '13px', padding: '6px 14px' }}
          >
            {committee.is_chair
              ? (panelOpen ? 'Hide management' : 'Manage committee')
              : (panelOpen ? 'Hide messages' : 'View messages')}
          </button>
        </div>
      )}

      <AnimatePresence initial={false}>
        {panelOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            style={{ overflow: 'hidden' }}
          >
            {committee.is_chair ? (
              <ChairPanel committeeId={committee.id} onClose={() => setPanelOpen(false)} />
            ) : (
              <MemberMessagesPanel committeeId={committee.id} onClose={() => setPanelOpen(false)} />
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

export default function Committees() {
  useDocumentTitle("Committees");
  const [committees, setCommittees] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    getCommittees()
      .then(res => setCommittees(res.data))
      .catch(() => setError('Could not load committees. Please try again.'))
      .finally(() => setLoading(false));
  }, []);

  async function handleToggle(committeeId, isMember) {
    // Optimistic update
    setCommittees(prev =>
      prev.map(c => c.id === committeeId ? { ...c, is_member: !isMember } : c)
    );
    try {
      if (isMember) {
        await leaveCommittee(committeeId);
      } else {
        await joinCommittee(committeeId);
      }
    } catch {
      // Revert on failure
      setCommittees(prev =>
        prev.map(c => c.id === committeeId ? { ...c, is_member: isMember } : c)
      );
    }
  }

  return (
    <div style={{
      maxWidth: '720px',
      margin: '0 auto',
      padding: '96px 16px 80px',
      fontFamily: 'Work Sans, sans-serif',
    }}>
      <motion.div
        initial={{ opacity: 0, y: -12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        <h1 style={{
          fontWeight: 800,
          color: 'var(--blue)',
          fontSize: '32px',
          marginBottom: '8px',
          marginTop: 0,
        }}>
          Committees
        </h1>
        <p style={{ color: '#6b7280', marginBottom: '32px', fontSize: '15px' }}>
          Join committees that match your interests and get more involved with SHPE UH.
        </p>
      </motion.div>

      {loading ? (
        <p style={{ color: '#6b7280' }}>Loading committees…</p>
      ) : error ? (
        <p style={{ color: '#D33A02' }}>{error}</p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {committees.map(c => (
            <CommitteeCard key={c.id} committee={c} onToggle={handleToggle} />
          ))}
        </div>
      )}
    </div>
  );
}
