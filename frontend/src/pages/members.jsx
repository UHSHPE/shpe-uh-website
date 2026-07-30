/* eslint-disable no-unused-vars */
import { useEffect, useMemo, useState } from "react";
import { Navigate } from "react-router-dom";
import { motion } from "framer-motion";
import { useAuth } from "../context/AuthContext";
import { useCart } from "../context/CartContext";
import { getAdminMembers, getAdminStats, getAssignableRoles, updateMemberRole } from "../api/api";
import { canAssignRoles, isPresident, PRESIDENT_ROLE } from "../utils/shop";

// Members directory for the president and both VPs: chapter-wide stats
// (accounts, dues paid vs not), member lookup, and role assignment (e-board,
// chairs, member…). Backed by the /admin/* endpoints — anyone else gets a 403
// there, and other signed-in members are bounced to the dashboard here.

const DUES_FILTERS = [
  { key: "all", label: "Everyone" },
  { key: "paid", label: "Dues paid" },
  { key: "unpaid", label: "Not paid" },
];

// Every committee chair role's display value ends in "Chair", so gaining or
// losing one also moves the person on/off that committee's chair listing.
function isChairRole(role) {
  return typeof role === "string" && role.endsWith("Chair");
}

function roleChangeWarning(member, nextRole) {
  const name = `${member.first_name} ${member.last_name}`;
  let text = `Change ${name} from "${member.role}" to "${nextRole}"?`;
  if (isChairRole(member.role) || isChairRole(nextRole)) {
    text += "\n\nThis also updates that committee's chair listing.";
  }
  return text;
}

function StatTile({ value, label, color }) {
  return (
    <div style={{ border: "1px solid var(--border)", borderRadius: "14px", padding: "18px 20px", background: "#fff" }}>
      <p style={{ margin: 0, fontSize: "30px", fontWeight: 800, lineHeight: 1, color }}>{value}</p>
      <p style={{ margin: "8px 0 0", fontSize: "12px", fontWeight: 600, color: "var(--muted)" }}>{label}</p>
    </div>
  );
}

function DuesPill({ paid }) {
  const meta = paid
    ? { label: "Paid", color: "var(--status-picked-text)", bg: "var(--status-picked-bg)", border: "var(--status-picked-border)" }
    : { label: "Not paid", color: "var(--status-ready-text)", bg: "var(--status-ready-bg)", border: "var(--status-ready-border)" };
  return (
    <span style={{
      display: "inline-block",
      padding: "3px 10px",
      borderRadius: "999px",
      fontSize: "12px",
      fontWeight: 700,
      color: meta.color,
      background: meta.bg,
      border: `1px solid ${meta.border}`,
      whiteSpace: "nowrap",
    }}>
      {meta.label}
    </span>
  );
}

// Single-hue count breakdown (magnitude is encoded by bar length, labels and
// counts stay in ink/muted text tokens).
function BreakdownCard({ title, counts }) {
  const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  const max = Math.max(1, ...entries.map(([, n]) => n));
  return (
    <div style={{ border: "1px solid var(--border)", borderRadius: "14px", padding: "18px 20px", background: "#fff" }}>
      <p style={{ margin: "0 0 12px", fontSize: "13px", fontWeight: 700, color: "var(--ink)" }}>{title}</p>
      {entries.length === 0 && (
        <p style={{ margin: 0, fontSize: "13px", color: "var(--muted)" }}>No data yet.</p>
      )}
      <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
        {entries.map(([label, n]) => (
          <div key={label} style={{ display: "grid", gridTemplateColumns: "minmax(90px, 1fr) 2fr 32px", gap: "10px", alignItems: "center" }}>
            <span style={{ fontSize: "12px", fontWeight: 600, color: "var(--ink-soft)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {label}
            </span>
            <span style={{ height: "8px", borderRadius: "999px", background: "var(--surface-soft)", overflow: "hidden" }}>
              <span style={{ display: "block", height: "100%", width: `${(n / max) * 100}%`, borderRadius: "999px", background: "var(--shpe-blue)" }} />
            </span>
            <span style={{ fontSize: "12px", fontWeight: 700, color: "var(--ink)", textAlign: "right" }}>{n}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

const memberRow = {
  display: "grid",
  gridTemplateColumns: "minmax(200px, 1.6fr) 110px 64px 100px minmax(180px, 1fr)",
  gap: "12px",
  alignItems: "center",
  padding: "12px 16px",
  minWidth: "700px",
};

export default function MembersPage() {
  const { user } = useAuth();
  const { showToast } = useCart();

  const [members, setMembers] = useState(null);
  const [stats, setStats] = useState(null);
  const [roles, setRoles] = useState([]);
  const [loadError, setLoadError] = useState(false);
  const [savingId, setSavingId] = useState(null);

  const [search, setSearch] = useState("");
  const [duesFilter, setDuesFilter] = useState("all");
  const [roleFilter, setRoleFilter] = useState("all");

  // The president and both VPs reach this page; VPs are limited below.
  const authorized = user && canAssignRoles(user);
  const viewerIsPresident = isPresident(user);

  useEffect(() => {
    if (!authorized) return;
    let cancelled = false;
    Promise.all([getAdminMembers(), getAdminStats(), getAssignableRoles()])
      .then(([membersRes, statsRes, rolesRes]) => {
        if (cancelled) return;
        setMembers(membersRes.data);
        setStats(statsRes.data);
        setRoles(rolesRes.data);
      })
      .catch(() => {
        if (!cancelled) setLoadError(true);
      });
    return () => {
      cancelled = true;
    };
  }, [authorized]);

  const visible = useMemo(() => {
    if (!members) return [];
    const needle = search.trim().toLowerCase();
    return members.filter((m) => {
      if (duesFilter === "paid" && !m.has_paid_dues) return false;
      if (duesFilter === "unpaid" && m.has_paid_dues) return false;
      if (roleFilter !== "all" && m.role !== roleFilter) return false;
      if (!needle) return true;
      return (
        `${m.first_name} ${m.last_name}`.toLowerCase().includes(needle) ||
        m.cougarnet_email.toLowerCase().includes(needle) ||
        m.personal_email.toLowerCase().includes(needle) ||
        m.psid.includes(needle)
      );
    });
  }, [members, search, duesFilter, roleFilter]);

  if (!user) {
    return (
      <div style={{
        minHeight: "60vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        color: "var(--blue)",
        fontWeight: 600,
        fontFamily: "Work Sans, sans-serif",
      }}>
        Loading…
      </div>
    );
  }

  if (!authorized) {
    return <Navigate to="/dashboard" replace />;
  }

  async function changeRole(member, role) {
    const name = `${member.first_name} ${member.last_name}`;
    setSavingId(member.id);
    try {
      const res = await updateMemberRole(member.id, role);
      setMembers((prev) => prev.map((m) => (m.id === member.id ? res.data : m)));
      showToast(`${name} is now ${role}`);
    } catch (err) {
      showToast(err.response?.data?.detail || "Couldn't update the role");
    } finally {
      setSavingId(null);
    }
  }

  const duesSince = stats
    ? new Date(stats.dues_period_start + "Z").toLocaleDateString(undefined, { month: "long", day: "numeric", year: "numeric" })
    : null;

  return (
    <div style={{
      maxWidth: "1040px",
      margin: "0 auto",
      padding: "96px 20px 80px",
      fontFamily: "Work Sans, sans-serif",
    }}>
      <motion.div initial={{ opacity: 0, y: -12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }}>
        <p style={{ margin: 0, fontSize: "13px", fontWeight: 700, letterSpacing: ".06em", textTransform: "uppercase", color: "var(--shpe-red)" }}>
          President tools
        </p>
        <h1 style={{ margin: "4px 0 6px", fontSize: "30px", fontWeight: 800, color: "var(--shpe-navy)" }}>Members</h1>
        <p style={{ margin: "0 0 24px", fontSize: "14px", color: "var(--muted)" }}>
          Every account on the site, with dues status and role assignment.
          {duesSince && <> Dues period started <strong style={{ color: "var(--ink-soft)" }}>{duesSince}</strong>.</>}
        </p>
      </motion.div>

      {loadError && (
        <p style={{ margin: "0 0 24px", fontSize: "14px", color: "var(--shpe-red)", fontWeight: 600 }}>
          Couldn't load the member directory. Refresh to try again.
        </p>
      )}

      {/* Chapter numbers */}
      {stats && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, delay: 0.05 }}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: "14px", marginBottom: "14px" }}>
            <StatTile value={stats.total_accounts} label="Total accounts" color="var(--shpe-blue)" />
            <StatTile value={stats.dues_paid} label="Dues paid" color="var(--status-picked-text)" />
            <StatTile value={stats.dues_unpaid} label="Not paid" color="var(--status-ready-text)" />
            <StatTile value={stats.national_members} label="SHPE national members" color="var(--shpe-navy)" />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "14px", marginBottom: "28px" }}>
            <BreakdownCard title="By classification" counts={stats.classification_counts} />
            <BreakdownCard title="Shirt sizes (for dues t-shirt orders)" counts={stats.shirt_size_counts} />
          </div>
        </motion.div>
      )}

      {/* Lookup controls */}
      <div style={{ display: "flex", gap: "10px", alignItems: "center", flexWrap: "wrap", marginBottom: "14px" }}>
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search name, email, or PSID…"
          style={{
            flex: "1 1 220px",
            padding: "9px 14px",
            fontSize: "14px",
            fontFamily: "inherit",
            border: "1px solid var(--border-strong)",
            borderRadius: "10px",
            background: "#fff",
            color: "var(--ink)",
          }}
        />
        <div style={{ display: "flex", gap: "4px" }}>
          {DUES_FILTERS.map((f) => {
            const active = duesFilter === f.key;
            return (
              <button
                key={f.key}
                type="button"
                onClick={() => setDuesFilter(f.key)}
                style={{
                  padding: "7px 13px",
                  fontSize: "13px",
                  fontWeight: active ? 700 : 600,
                  fontFamily: "inherit",
                  color: active ? "#fff" : "var(--muted)",
                  background: active ? "var(--shpe-blue)" : "var(--surface-soft)",
                  border: "none",
                  borderRadius: "999px",
                  cursor: "pointer",
                }}
              >
                {f.label}
              </button>
            );
          })}
        </div>
        <select
          value={roleFilter}
          onChange={(e) => setRoleFilter(e.target.value)}
          style={{
            padding: "8px 10px",
            fontSize: "13px",
            fontFamily: "inherit",
            border: "1px solid var(--border-strong)",
            borderRadius: "10px",
            background: "#fff",
            color: "var(--ink-soft)",
          }}
        >
          <option value="all">All roles</option>
          {roles.map((r) => (
            <option key={r} value={r}>{r}</option>
          ))}
        </select>
      </div>

      {/* Directory table */}
      <div style={{ border: "1px solid var(--border)", borderRadius: "12px", overflowX: "auto", background: "#fff" }}>
        <div style={{ ...memberRow, background: "var(--surface-muted)", borderBottom: "1px solid var(--border)", fontSize: "11px", fontWeight: 700, letterSpacing: ".04em", textTransform: "uppercase", color: "var(--muted-soft)" }}>
          <span>Member</span>
          <span>Classification</span>
          <span>Points</span>
          <span>Dues</span>
          <span>Role</span>
        </div>

        {members === null && !loadError && (
          <p style={{ margin: 0, padding: "20px 16px", fontSize: "14px", color: "var(--muted)" }}>Loading members…</p>
        )}

        {members !== null && visible.length === 0 && (
          <p style={{ margin: 0, padding: "20px 16px", fontSize: "14px", color: "var(--muted)" }}>
            No members match this search.
          </p>
        )}

        {visible.map((m) => {
          const isSelf = m.id === user.id;
          // Only the president may change the president's role — the backend
          // 403s a VP here, so don't offer a select that can't succeed.
          const locked = isSelf || (!viewerIsPresident && m.role === PRESIDENT_ROLE);
          return (
            <div key={m.id} style={{ ...memberRow, borderBottom: "1px solid var(--surface-soft)" }}>
              <div style={{ minWidth: 0 }}>
                <p style={{ margin: 0, fontSize: "14px", fontWeight: 700, color: "var(--ink)", lineHeight: 1.25 }}>
                  {m.first_name} {m.last_name}
                  {isSelf && (
                    <span style={{ marginLeft: "8px", fontSize: "11px", fontWeight: 700, color: "var(--shpe-blue)", background: "var(--surface-tint)", borderRadius: "999px", padding: "2px 8px" }}>
                      You
                    </span>
                  )}
                </p>
                <p style={{ margin: "2px 0 0", fontSize: "12px", color: "var(--muted-soft)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {m.cougarnet_email}
                </p>
              </div>
              <span style={{ fontSize: "13px", color: "var(--ink-soft)" }}>{m.classification}</span>
              <span style={{ fontSize: "13px", fontWeight: 700, color: "var(--ink)" }}>{m.points}</span>
              <span><DuesPill paid={m.has_paid_dues} /></span>
              {locked ? (
                // Your own role (no self-lockout), or the president's when a
                // VP is viewing — both are refused by the backend.
                <span style={{ fontSize: "13px", fontWeight: 600, color: "var(--muted)" }}>{m.role}</span>
              ) : (
                <select
                  value={m.role}
                  disabled={savingId === m.id}
                  onChange={(e) => {
                    const role = e.target.value;
                    if (!window.confirm(roleChangeWarning(m, role))) {
                      // Controlled value didn't change, so React won't repaint
                      // the cancelled pick — reset the DOM select directly.
                      e.target.value = m.role;
                      return;
                    }
                    changeRole(m, role);
                  }}
                  style={{
                    padding: "7px 10px",
                    fontSize: "13px",
                    fontFamily: "inherit",
                    border: "1px solid var(--border-strong)",
                    borderRadius: "8px",
                    background: "#fff",
                    color: "var(--ink-soft)",
                    maxWidth: "100%",
                    opacity: savingId === m.id ? 0.6 : 1,
                  }}
                >
                  {roles.map((r) => (
                    <option key={r} value={r}>{r}</option>
                  ))}
                </select>
              )}
            </div>
          );
        })}
      </div>

      {members !== null && (
        <p style={{ margin: "12px 4px 0", fontSize: "12px", color: "var(--muted-soft)" }}>
          Showing {visible.length} of {members.length} accounts. Changing a chair role also
          updates that committee's chair automatically. The About page roster is maintained
          by hand and does not change.
        </p>
      )}
    </div>
  );
}
