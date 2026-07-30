/* eslint-disable no-unused-vars */
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { useAuth } from '../context/AuthContext';
import { getUpcomingEvents, getNotifications, markNotificationRead } from '../api/api';

function PointsBadge({ points }) {
  return (
    <div style={{
      background: 'rgba(255,255,255,0.15)',
      border: '2px solid rgba(255,255,255,0.3)',
      borderRadius: '16px',
      padding: '20px 28px',
      display: 'inline-flex',
      flexDirection: 'column',
      alignItems: 'center',
      gap: '4px',
      minWidth: '130px',
      backdropFilter: 'blur(8px)',
    }}>
      <span style={{ fontSize: '52px', fontWeight: 800, lineHeight: 1, color: '#fff' }}>
        {points}
      </span>
      <span style={{
        fontSize: '11px',
        fontWeight: 700,
        letterSpacing: '0.1em',
        textTransform: 'uppercase',
        color: 'rgba(255,255,255,0.85)',
      }}>
        SHPE Points
      </span>
    </div>
  );
}

function formatEventTime(startStr, endStr) {
  const start = new Date(startStr + 'Z'); // treat stored UTC as UTC
  const end = endStr ? new Date(endStr + 'Z') : null;
  const dayFmt = new Intl.DateTimeFormat('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
  const timeFmt = new Intl.DateTimeFormat('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
  return {
    day: dayFmt.format(start),
    time: timeFmt.format(start) + (end ? ` – ${timeFmt.format(end)}` : ''),
  };
}

const EVENT_TYPE_COLORS = { // why these color mappings ? idk i didnt come up with these
  'General Meeting': '#0070C0',
  'Professional': '#005A9C',
  'Outreach': '#D33A02',
  'Social': '#6B21A8',
  'SRT': '#065F46',
};

function EventCard({ event }) {
  const { day, time } = formatEventTime(event.start_time, event.end_time);
  const [dayLabel, ...dateParts] = day.split(', ');
  const typeColor = EVENT_TYPE_COLORS[event.event_type] ?? '#0070C0';

  return (
    <div style={{
      border: '1px solid #e5e7eb',
      borderRadius: '12px',
      padding: '16px 20px',
      display: 'flex',
      alignItems: 'flex-start',
      gap: '16px',
      background: '#fff',
      boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
    }}>
      <div style={{
        minWidth: '60px',
        textAlign: 'center',
        paddingTop: '2px',
      }}>
        <div style={{ fontWeight: 700, color: 'var(--blue)', fontSize: '12px', textTransform: 'uppercase' }}>
          {dayLabel}
        </div>
        <div style={{ fontWeight: 800, fontSize: '24px', color: 'var(--blue)', lineHeight: 1.1 }}>
          {dateParts.join(', ').split(' ')[1]}
        </div>
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <p style={{ margin: 0, fontWeight: 700, fontSize: '15px', color: '#111827' }}>{event.title}</p>
          {event.event_type && (
            <span style={{
              background: typeColor,
              color: '#fff',
              borderRadius: '999px',
              padding: '2px 8px',
              fontSize: '11px',
              fontWeight: 600,
            }}>
              {event.event_type}
            </span>
          )}
        </div>
        <p style={{ margin: '3px 0 0', color: '#6b7280', fontSize: '13px' }}>{time}</p>
        {event.location && (
          <p style={{ margin: '2px 0 0', color: '#6b7280', fontSize: '13px' }}>📍 {event.location}</p>
        )}
      </div>
      {event.points_value > 0 && (
        <div style={{
          background: '#D33A02',
          color: '#fff',
          borderRadius: '999px',
          padding: '4px 10px',
          fontSize: '12px',
          fontWeight: 700,
          whiteSpace: 'nowrap',
          alignSelf: 'center',
        }}>
          +{event.points_value} pts
        </div>
      )}
    </div>
  );
}

function formatNotificationTime(str) {
  const d = new Date(str + 'Z'); // stored UTC
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  }).format(d);
}

function NotificationItem({ notification, onRead }) {
  const unread = !notification.is_read;
  return (
    <div
      onClick={unread ? () => onRead(notification.id) : undefined}
      style={{
        border: '1px solid #e5e7eb',
        borderLeft: unread ? '4px solid #0070C0' : '4px solid #e5e7eb',
        borderRadius: '10px',
        padding: '12px 16px',
        background: unread ? '#eff6ff' : '#fff',
        cursor: unread ? 'pointer' : 'default',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'flex-start',
        gap: '12px',
      }}
    >
      <p style={{ margin: 0, fontSize: '14px', color: '#111827', fontWeight: unread ? 600 : 400 }}>
        {notification.body}
      </p>
      <span style={{ fontSize: '11px', color: '#9ca3af', whiteSpace: 'nowrap' }}>
        {formatNotificationTime(notification.created_at)}
      </span>
    </div>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [events, setEvents] = useState([]);
  const [eventsLoading, setEventsLoading] = useState(true);
  const [notifications, setNotifications] = useState([]);
  const [notifsLoading, setNotifsLoading] = useState(true);

  useEffect(() => {
    getUpcomingEvents()
      .then(res => setEvents(res.data))
      .catch(() => setEvents([]))
      .finally(() => setEventsLoading(false));

    getNotifications()
      .then(res => setNotifications(res.data))
      .catch(() => setNotifications([]))
      .finally(() => setNotifsLoading(false));
  }, []);

  async function handleRead(id) {
    setNotifications(prev =>
      prev.map(n => n.id === id ? { ...n, is_read: true } : n)
    );
    try {
      await markNotificationRead(id);
    } catch {
      setNotifications(prev =>
        prev.map(n => n.id === id ? { ...n, is_read: false } : n)
      );
    }
  }

  const unreadCount = notifications.filter(n => !n.is_read).length;

  return (
    <div style={{
      maxWidth: '800px',
      margin: '0 auto',
      padding: '96px 16px 80px',
      fontFamily: 'Work Sans, sans-serif',
    }}>
      {/* Hero strip */}
      <motion.div
        initial={{ opacity: 0, y: -16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        style={{
          background: 'linear-gradient(135deg, #001F5B 0%, #003A70 55%, #0070C0 100%)',
          borderRadius: '20px',
          padding: '32px',
          color: '#fff',
          marginBottom: '28px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '20px',
        }}
      >
        <div>
          <p style={{ margin: 0, opacity: 0.75, fontSize: '14px', fontWeight: 500 }}>Welcome back,</p>
          <h1 style={{ margin: '4px 0 0', fontSize: '30px', fontWeight: 800, lineHeight: 1.1 }}>
            {user?.first_name}
          </h1>
        </div>
        <PointsBadge points={user?.points ?? 0} />
      </motion.div>

      {/* Quick links */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.1 }}
        style={{ marginBottom: '32px' }}
      >
        <button
          className="primaryBtn"
          onClick={() => navigate('/committees')}
          style={{ fontSize: '14px', padding: '10px 20px' }}
        >
          View Committees →
        </button>
      </motion.div>

      {/* Notifications */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.12 }}
        style={{ marginBottom: '32px' }}
      >
        <h2 style={{
          fontWeight: 700,
          color: 'var(--blue)',
          fontSize: '20px',
          marginBottom: '16px',
          marginTop: 0,
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
        }}>
          Notifications
          {unreadCount > 0 && (
            <span style={{
              background: '#D33A02',
              color: '#fff',
              borderRadius: '999px',
              padding: '2px 9px',
              fontSize: '12px',
              fontWeight: 700,
            }}>
              {unreadCount}
            </span>
          )}
        </h2>
        {notifsLoading ? (
          <p style={{ color: '#6b7280' }}>Loading notifications…</p>
        ) : notifications.length === 0 ? (
          <p style={{ color: '#6b7280' }}>You're all caught up — no notifications.</p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {notifications.map(n => (
              <NotificationItem key={n.id} notification={n} onRead={handleRead} />
            ))}
          </div>
        )}
      </motion.div>

      {/* Upcoming events */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.15 }}
      >
        <h2 style={{
          fontWeight: 700,
          color: 'var(--blue)',
          fontSize: '20px',
          marginBottom: '16px',
          marginTop: 0,
        }}>
          Upcoming Events This Week
        </h2>
        {eventsLoading ? (
          <p style={{ color: '#6b7280' }}>Loading events…</p>
        ) : events.length === 0 ? (
          <p style={{ color: '#6b7280' }}>No upcoming events this week — check back soon!</p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {events.map(ev => <EventCard key={ev.id} event={ev} />)}
          </div>
        )}
      </motion.div>
    </div>
  );
}
