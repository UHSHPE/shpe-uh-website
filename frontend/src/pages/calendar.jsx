/* eslint-disable no-unused-vars */
import { useState, useEffect, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useLocation, useNavigate } from 'react-router-dom';
import { getAllEvents, getMyReminders, setEventReminder, cancelEventReminder } from '../api/api';
import { useAuth } from '../context/AuthContext';
import useDocumentTitle from "../hooks/useDocumentTitle";

const EVENT_TYPE_COLORS = {
  'General Meeting': '#0070C0',
  'Professional': '#005A9C',
  'Outreach': '#D33A02',
  'Social': '#6B21A8',
  'SRT': '#065F46',
};

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

function eventColor(type) {
  return EVENT_TYPE_COLORS[type] ?? '#0070C0';
}

// Stored datetimes are naive UTC — append 'Z' so the browser reads them as UTC.
function parseUTC(str) {
  return new Date(str + 'Z');
}

function formatEventTime(startStr, endStr) {
  const start = parseUTC(startStr);
  const end = endStr ? parseUTC(endStr) : null;
  const timeFmt = new Intl.DateTimeFormat('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
  return timeFmt.format(start) + (end ? ` – ${timeFmt.format(end)}` : '');
}

// Local YYYY-MM-DD key for a Date
function dayKey(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

function sameDay(a, b) {
  return a.getFullYear() === b.getFullYear()
    && a.getMonth() === b.getMonth()
    && a.getDate() === b.getDate();
}

function startOfMonth(date) {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

export default function Calendar() {
  useDocumentTitle("Calendar");
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [viewDate, setViewDate] = useState(() => startOfMonth(new Date()));
  const [selectedDate, setSelectedDate] = useState(() => new Date());
  const [reminderEventIds, setReminderEventIds] = useState(() => new Set());
  const [reminderBusyId, setReminderBusyId] = useState(null);
  const { token } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    getAllEvents()
      .then(res => setEvents(res.data))
      .catch(() => setError('Could not load events. Please try again.'))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!token) return;
    getMyReminders()
      .then(res => setReminderEventIds(new Set(res.data.map(r => r.event_id))))
      .catch(() => {});
  }, [token]);

  async function toggleReminder(ev) {
    if (!token) {
      navigate('/signin', { state: { from: location } });
      return;
    }
    setReminderBusyId(ev.id);
    try {
      if (reminderEventIds.has(ev.id)) {
        await cancelEventReminder(ev.id);
        setReminderEventIds(prev => {
          const next = new Set(prev);
          next.delete(ev.id);
          return next;
        });
      } else {
        await setEventReminder(ev.id);
        setReminderEventIds(prev => new Set(prev).add(ev.id));
      }
    } catch (err) {
      // 409 = reminder already exists on the server; sync local state to match
      if (err.response?.status === 409) {
        setReminderEventIds(prev => new Set(prev).add(ev.id));
      }
    } finally {
      setReminderBusyId(null);
    }
  }

  // Bucket events by local day key
  const eventsByDay = useMemo(() => {
    const map = {};
    for (const ev of events) {
      const key = dayKey(parseUTC(ev.start_time));
      (map[key] ||= []).push(ev);
    }
    for (const key of Object.keys(map)) {
      map[key].sort((a, b) => a.start_time.localeCompare(b.start_time));
    }
    return map;
  }, [events]);

  const today = new Date();
  const year = viewDate.getFullYear();
  const month = viewDate.getMonth();

  // Build the grid: leading blanks + days of month, padded to full weeks
  const firstWeekday = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const cells = [];
  for (let i = 0; i < firstWeekday; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(new Date(year, month, d));
  while (cells.length % 7 !== 0) cells.push(null);

  const monthLabel = new Intl.DateTimeFormat('en-US', { month: 'long', year: 'numeric' }).format(viewDate);

  function shiftMonth(delta) {
    setViewDate(prev => new Date(prev.getFullYear(), prev.getMonth() + delta, 1));
  }

  function goToday() {
    const now = new Date();
    setViewDate(startOfMonth(now));
    setSelectedDate(now);
  }

  const selectedEvents = eventsByDay[dayKey(selectedDate)] ?? [];
  const selectedLabel = new Intl.DateTimeFormat('en-US', {
    weekday: 'long', month: 'long', day: 'numeric', year: 'numeric',
  }).format(selectedDate);

  return (
    <div style={{
      maxWidth: '880px',
      margin: '0 auto',
      padding: '96px 16px 80px',
      fontFamily: 'Work Sans, sans-serif',
    }}>
      <motion.div
        initial={{ opacity: 0, y: -12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        <h1 style={{ fontWeight: 800, color: 'var(--blue)', fontSize: '32px', margin: '0 0 8px' }}>
          Events Calendar
        </h1>
        <p style={{ color: '#6b7280', marginBottom: '28px', fontSize: '15px' }}>
          See what SHPE UH has coming up. Click a day to see event times and locations.
        </p>
      </motion.div>

      {/* Month controls */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: '12px',
        gap: '12px',
        flexWrap: 'wrap',
      }}>
        <h2 style={{ fontWeight: 700, color: 'var(--blue)', fontSize: '22px', margin: 0 }}>
          {monthLabel}
        </h2>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button className="ghostBtn" onClick={() => shiftMonth(-1)} aria-label="Previous month"
            style={{ fontSize: '14px', padding: '6px 14px' }}>←</button>
          <button className="ghostBtn" onClick={goToday}
            style={{ fontSize: '14px', padding: '6px 14px' }}>Today</button>
          <button className="ghostBtn" onClick={() => shiftMonth(1)} aria-label="Next month"
            style={{ fontSize: '14px', padding: '6px 14px' }}>→</button>
        </div>
      </div>

      {loading ? (
        <p style={{ color: '#6b7280' }}>Loading calendar…</p>
      ) : error ? (
        <p style={{ color: '#D33A02' }}>{error}</p>
      ) : (
        <>
          {/* Weekday header */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(7, 1fr)',
            gap: '6px',
            marginBottom: '6px',
          }}>
            {WEEKDAYS.map(w => (
              <div key={w} style={{
                textAlign: 'center',
                fontSize: '12px',
                fontWeight: 700,
                color: '#6b7280',
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
              }}>
                {w}
              </div>
            ))}
          </div>

          {/* Day grid */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: '6px' }}>
            {cells.map((date, i) => {
              if (!date) return <div key={`blank-${i}`} />;
              const key = dayKey(date);
              const dayEvents = eventsByDay[key] ?? [];
              const isToday = sameDay(date, today);
              const isSelected = sameDay(date, selectedDate);
              return (
                <button
                  key={key}
                  onClick={() => setSelectedDate(date)}
                  style={{
                    minHeight: '92px',
                    border: isSelected ? '2px solid var(--blue)' : '1px solid #e5e7eb',
                    borderRadius: '10px',
                    background: '#fff',
                    padding: '6px',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'stretch',
                    gap: '3px',
                    cursor: 'pointer',
                    textAlign: 'left',
                    fontFamily: 'inherit',
                    overflow: 'hidden',
                  }}
                >
                  <span style={{
                    fontSize: '13px',
                    fontWeight: isToday ? 800 : 600,
                    color: isToday ? '#fff' : '#111827',
                    background: isToday ? '#0070C0' : 'transparent',
                    borderRadius: '999px',
                    width: '24px',
                    height: '24px',
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    alignSelf: 'flex-start',
                  }}>
                    {date.getDate()}
                  </span>
                  {dayEvents.slice(0, 2).map(ev => (
                    <span key={ev.id} title={ev.title} style={{
                      background: eventColor(ev.event_type),
                      color: '#fff',
                      borderRadius: '6px',
                      padding: '2px 6px',
                      fontSize: '11px',
                      fontWeight: 600,
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}>
                      {ev.title}
                    </span>
                  ))}
                  {dayEvents.length > 2 && (
                    <span style={{ fontSize: '11px', color: '#6b7280', fontWeight: 600 }}>
                      +{dayEvents.length - 2} more
                    </span>
                  )}
                </button>
              );
            })}
          </div>

          {/* Selected day detail */}
          <AnimatePresence mode="wait">
            <motion.div
              key={dayKey(selectedDate)}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.25 }}
              style={{ marginTop: '28px' }}
            >
              <h3 style={{ fontWeight: 700, color: 'var(--blue)', fontSize: '18px', margin: '0 0 12px' }}>
                {selectedLabel}
              </h3>
              {selectedEvents.length === 0 ? (
                <p style={{ color: '#6b7280', fontSize: '14px' }}>No events on this day.</p>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {selectedEvents.map(ev => (
                    <div key={ev.id} style={{
                      border: '1px solid #e5e7eb',
                      borderLeft: `4px solid ${eventColor(ev.event_type)}`,
                      borderRadius: '10px',
                      padding: '14px 18px',
                      background: '#fff',
                      boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                        <p style={{ margin: 0, fontWeight: 700, fontSize: '15px', color: '#111827' }}>{ev.title}</p>
                        {ev.event_type && (
                          <span style={{
                            background: eventColor(ev.event_type),
                            color: '#fff',
                            borderRadius: '999px',
                            padding: '2px 8px',
                            fontSize: '11px',
                            fontWeight: 600,
                          }}>
                            {ev.event_type}
                          </span>
                        )}
                      </div>
                      <p style={{ margin: '4px 0 0', color: '#374151', fontSize: '13px' }}>
                        🕒 {formatEventTime(ev.start_time, ev.end_time)}
                      </p>
                      {ev.location && (
                        <p style={{ margin: '2px 0 0', color: '#374151', fontSize: '13px' }}>
                          📍 {ev.location}
                        </p>
                      )}
                      {ev.description && (
                        <p style={{ margin: '6px 0 0', color: '#6b7280', fontSize: '13px' }}>
                          {ev.description}
                        </p>
                      )}
                      {parseUTC(ev.start_time) > new Date() && (
                        <button
                          className="ghostBtn"
                          onClick={() => toggleReminder(ev)}
                          disabled={reminderBusyId === ev.id}
                          style={{ marginTop: '10px', fontSize: '13px', padding: '5px 12px' }}
                        >
                          {!token
                            ? '🔔 Sign in to get a reminder'
                            : reminderEventIds.has(ev.id)
                              ? '🔕 Cancel email reminder'
                              : '🔔 Remind me by email'}
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </motion.div>
          </AnimatePresence>
        </>
      )}
    </div>
  );
}
