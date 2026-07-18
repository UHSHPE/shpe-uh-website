/* eslint-disable no-unused-vars */
import { useState, useRef } from 'react';
import { motion } from 'framer-motion';
import { useAuth } from '../context/AuthContext';
import { uploadResume, getResumeBlob, deleteResume } from '../api/api';
import MyOrders from '../components/MyOrders';
import { isShopManager } from '../utils/shop';

function yesNo(v) {
  return v ? 'Yes' : 'No';
}

function joinList(arr) {
  return Array.isArray(arr) && arr.length ? arr.join(', ') : '—';
}

// One labeled, read-only field in the info grid.
function Field({ label, value }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '3px', minWidth: 0 }}>
      <span style={{
        fontSize: '11px',
        fontWeight: 700,
        letterSpacing: '0.06em',
        textTransform: 'uppercase',
        color: '#9ca3af',
      }}>
        {label}
      </span>
      <span style={{ fontSize: '15px', color: '#111827', wordBreak: 'break-word' }}>
        {value === null || value === undefined || value === '' ? '—' : value}
      </span>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <div style={{
      border: '1px solid #e5e7eb',
      borderRadius: '16px',
      padding: '24px 28px',
      background: '#fff',
      boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
      marginBottom: '24px',
    }}>
      <h2 style={{
        fontWeight: 700,
        color: 'var(--blue)',
        fontSize: '18px',
        margin: '0 0 18px',
      }}>
        {title}
      </h2>
      {children}
    </div>
  );
}

export default function Profile() {
  const { user } = useAuth();
  const fileInputRef = useRef(null);
  const [resumeName, setResumeName] = useState(user?.resume_filename ?? null);
  const [status, setStatus] = useState(null); // { type: 'success' | 'error', msg }
  const [busy, setBusy] = useState(false);

  if (!user) {
    return (
      <div style={{ maxWidth: '800px', margin: '0 auto', padding: '120px 16px', fontFamily: 'Work Sans, sans-serif' }}>
        <p style={{ color: '#6b7280' }}>Loading your profile…</p>
      </div>
    );
  }

  async function handleFileChange(e) {
    const file = e.target.files?.[0];
    e.target.value = ''; // let the user re-pick the same file later
    if (!file) return;
    if (file.type !== 'application/pdf') {
      setStatus({ type: 'error', msg: 'Please choose a PDF file.' });
      return;
    }
    if (file.size > 2 * 1024 * 1024) {
      setStatus({ type: 'error', msg: 'Resume must be 2 MB or smaller.' });
      return;
    }
    setBusy(true);
    setStatus(null);
    try {
      const res = await uploadResume(file);
      setResumeName(res.data.resume_filename);
      setStatus({ type: 'success', msg: 'Resume uploaded.' });
    } catch (err) {
      setStatus({ type: 'error', msg: err.response?.data?.detail || 'Upload failed. Please try again.' });
    } finally {
      setBusy(false);
    }
  }

  async function handleView() {
    try {
      const res = await getResumeBlob();
      const url = URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }));
      window.open(url, '_blank', 'noopener');
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch {
      setStatus({ type: 'error', msg: 'Could not open the resume.' });
    }
  }

  async function handleRemove() {
    setBusy(true);
    setStatus(null);
    try {
      await deleteResume();
      setResumeName(null);
      setStatus({ type: 'success', msg: 'Resume removed.' });
    } catch {
      setStatus({ type: 'error', msg: 'Could not remove the resume.' });
    } finally {
      setBusy(false);
    }
  }

  const gridStyle = {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
    gap: '18px 28px',
  };

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
        }}
      >
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap' }}>
          <div>
            <p style={{ margin: 0, opacity: 0.75, fontSize: '14px', fontWeight: 500 }}>Your profile</p>
            <h1 style={{ margin: '4px 0 0', fontSize: '30px', fontWeight: 800, lineHeight: 1.1 }}>
              {user.first_name} {user.last_name}
            </h1>
            <p style={{ margin: '6px 0 0', opacity: 0.85, fontSize: '14px' }}>{user.cougarnet_email}</p>
          </div>
          {isShopManager(user) && (
            <span style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '7px',
              background: 'rgba(253,101,47,.2)',
              border: '1px solid rgba(253,101,47,.5)',
              borderRadius: '999px',
              padding: '6px 14px',
              fontSize: '12px',
              fontWeight: 700,
            }}>
              ★ Shop Manager
            </span>
          )}
        </div>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.1 }}
      >
        {/* Resume */}
        <Section title="Resume">
          {resumeName ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                padding: '12px 16px',
                border: '1px solid #e5e7eb',
                borderRadius: '10px',
                background: '#f9fafb',
              }}>
                <span style={{ fontSize: '20px' }}>📄</span>
                <span style={{ fontSize: '14px', color: '#111827', fontWeight: 600, wordBreak: 'break-all' }}>
                  {resumeName}
                </span>
              </div>
              <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                <button className="primaryBtn" onClick={handleView} disabled={busy}
                  style={{ fontSize: '14px', padding: '8px 18px' }}>
                  View
                </button>
                <button className="ghostBtn" onClick={() => fileInputRef.current?.click()} disabled={busy}
                  style={{ fontSize: '14px', padding: '8px 18px' }}>
                  Replace
                </button>
                <button className="accentBtn" onClick={handleRemove} disabled={busy}
                  style={{ fontSize: '14px', padding: '8px 18px' }}>
                  Remove
                </button>
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <p style={{ margin: 0, color: '#6b7280', fontSize: '14px' }}>
                Upload your resume so SHPE can share opportunities that fit you. PDF only, up to 2&nbsp;MB.
              </p>
              <button className="primaryBtn" onClick={() => fileInputRef.current?.click()} disabled={busy}
                style={{ fontSize: '14px', padding: '8px 18px', alignSelf: 'flex-start' }}>
                {busy ? 'Uploading…' : 'Upload Resume (PDF)'}
              </button>
            </div>
          )}

          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf,.pdf"
            onChange={handleFileChange}
            style={{ display: 'none' }}
          />

          {status && (
            <p style={{
              margin: '14px 0 0',
              fontSize: '13px',
              fontWeight: 600,
              color: status.type === 'error' ? '#D33A02' : '#047857',
            }}>
              {status.msg}
            </p>
          )}
        </Section>

        {/* Account */}
        <Section title="Account">
          <div style={gridStyle}>
            <Field label="First name" value={user.first_name} />
            <Field label="Last name" value={user.last_name} />
            <Field label="CougarNet email" value={user.cougarnet_email} />
            <Field label="Personal email" value={user.personal_email} />
            <Field label="Phone" value={user.phone_num} />
            <Field label="PSID" value={user.psid} />
            <Field label="SHPE points" value={user.points} />
            <Field label="Role" value={user.role} />
          </div>
        </Section>

        {/* Academics */}
        <Section title="Academics">
          <div style={gridStyle}>
            <Field label="College" value={user.college} />
            <Field label="Major" value={user.major} />
            <Field label="Classification" value={user.classification} />
            <Field label="GPA" value={user.gpa} />
            <Field label="Expected graduation" value={user.exp_grad_date} />
          </div>
        </Section>

        {/* Membership & interests */}
        <Section title="Membership & Interests">
          <div style={gridStyle}>
            <Field label="Membership status" value={user.is_returning} />
            <Field label="National member" value={yesNo(user.is_national_member)} />
            <Field label="In Slack" value={yesNo(user.in_slack)} />
            <Field label="First generation" value={yesNo(user.first_gen)} />
            <Field label="Gender" value={user.gender} />
            <Field label="Shirt size" value={user.shirt_size} />
            <Field label="Birthday" value={user.birthday} />
            <Field label="Country of origin" value={joinList(user.country_origin)} />
            <Field label="Race / ethnicity" value={joinList(user.race_and_ethnicity)} />
            <Field label="Interested industries" value={joinList(user.interested_industries)} />
            <Field label="Professional development" value={joinList(user.prof_dev)} />
          </div>
        </Section>

        {/* Order history — latest order up front, the rest behind the toggle */}
        <MyOrders />
      </motion.div>
    </div>
  );
}
