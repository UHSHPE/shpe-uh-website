/* eslint-disable no-unused-vars */
import { useEffect, useMemo, useState } from "react";
import { Navigate } from "react-router-dom";
import { motion } from "framer-motion";
import { useAuth } from "../context/AuthContext";
import { useCart } from "../context/CartContext";
import {
  getAdminMembers,
  getAdminStats,
  getAssignableRoles,
  getOrgStructure,
  setRoleSupervisor,
  updateMemberRole,
} from "../api/api";
import {
  canAssignRoles,
  isChairRole,
  isEboardRole,
  isPresident,
  TOP_TIER_ROLES,
} from "../utils/shop";
import ConfirmDialog from "../components/ConfirmDialog";
import useDocumentTitle from "../hooks/useDocumentTitle";

// Members directory for the president and both VPs: chapter-wide stats
// (accounts, dues paid vs not), member lookup, role assignment, and the
// chapter reporting tree. Backed by the /admin/* endpoints — anyone else gets
// a 403 there, and other signed-in members are bounced to the dashboard here.

const DUES_FILTERS = [
  { key: "all", label: "Everyone" },
  { key: "paid", label: "Dues paid" },
  { key: "unpaid", label: "Not paid" },
];

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

function holderNames(node) {
  if (!node.holders.length) return "Vacant";
  return node.holders.map((h) => `${h.first_name} ${h.last_name}`).join(", ");
}

// Tier styling for a node card. The president and VPs are visually heavier so
// the top of the chart reads at a glance.
const TIER_STYLE = {
  president: { bg: "var(--shpe-navy)", fg: "#fff", sub: "rgba(255,255,255,.75)", border: "var(--shpe-navy)" },
  vp: { bg: "var(--surface-tint)", fg: "var(--shpe-navy)", sub: "var(--muted)", border: "var(--shpe-blue)" },
  officer: { bg: "#fff", fg: "var(--ink)", sub: "var(--muted-soft)", border: "var(--border-strong)" },
  chair: { bg: "#fff", fg: "var(--ink-soft)", sub: "var(--muted-soft)", border: "var(--border)" },
};

// One box in the tree: the role, who holds it, and (where the link is
// editable) a picker to move it under a different supervisor.
function OrgCard({ node, options, savingRole, onRequestChange, pending }) {
  const t = TIER_STYLE[node.tier] ?? TIER_STYLE.chair;
  const editable = options.length > 0;
  const value = pending?.node.role === node.role ? pending.supervisorRole : (node.supervisor_role ?? "");
  const vacant = node.holders.length === 0;

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: "12px",
        flexWrap: "wrap",
        background: t.bg,
        border: `1px solid ${t.border}`,
        borderLeft: `4px solid ${t.border}`,
        borderRadius: "10px",
        padding: "9px 14px",
        margin: "6px 0",
        boxShadow: "var(--shadow-card)",
      }}
    >
      <div style={{ minWidth: "170px", flex: "1 1 auto" }}>
        <p style={{ margin: 0, fontSize: "13px", fontWeight: 800, color: t.fg, lineHeight: 1.3 }}>
          {node.role}
        </p>
        <p style={{ margin: "1px 0 0", fontSize: "12px", color: vacant ? "var(--status-ready-text)" : t.sub }}>
          {vacant ? "Vacant" : holderNames(node)}
          {node.holders.length > 1 && (
            <span style={{ marginLeft: "6px", fontSize: "11px", opacity: 0.8 }}>({node.holders.length})</span>
          )}
        </p>
      </div>

      {editable && (
        <select
          aria-label={`Who ${node.role} reports to`}
          value={value}
          disabled={savingRole === node.role}
          onChange={(e) => onRequestChange(node, e.target.value)}
          style={{
            padding: "5px 8px",
            fontSize: "12px",
            fontFamily: "inherit",
            border: "1px solid var(--border-strong)",
            borderRadius: "8px",
            background: "#fff",
            color: "var(--ink-soft)",
            maxWidth: "100%",
            opacity: savingRole === node.role ? 0.6 : 1,
          }}
        >
          {!node.supervisor_role && <option value="">— pick a supervisor —</option>}
          {options.map((r) => (
            <option key={r} value={r}>{r}</option>
          ))}
        </select>
      )}
    </div>
  );
}

// Recursive branch. Children come from a supervisor_role -> nodes map, so the
// nesting is driven by the data rather than by tier position — a chair parked
// directly under a VP renders in the right place without a special case.
function OrgBranch({ node, childrenOf, optionsFor, savingRole, onRequestChange, pending }) {
  const kids = childrenOf[node.role] ?? [];
  return (
    <li>
      <OrgCard
        node={node}
        options={optionsFor(node)}
        savingRole={savingRole}
        onRequestChange={onRequestChange}
        pending={pending}
      />
      {kids.length > 0 && (
        <ul>
          {kids.map((kid) => (
            <OrgBranch
              key={kid.role}
              node={kid}
              childrenOf={childrenOf}
              optionsFor={optionsFor}
              savingRole={savingRole}
              onRequestChange={onRequestChange}
              pending={pending}
            />
          ))}
        </ul>
      )}
    </li>
  );
}

// The reporting tree as an actual tree: the president at the root, each VP
// beneath, their officers beneath those, and chairs at the leaves. Connector
// elbows come from the .orgTree rules in styles.css.
function StructurePanel({ structure, savingRole, onRequestChange, pending }) {
  if (!structure) {
    return <p style={{ margin: "8px 4px", fontSize: "14px", color: "var(--muted)" }}>Loading structure…</p>;
  }

  const vpNames = structure.filter((n) => n.tier === "vp").map((n) => n.role);
  const officerNames = structure.filter((n) => n.tier === "officer").map((n) => n.role);

  // Mirrors valid_supervisors() on the backend; an empty list means the link
  // is fixed (the president is the root, VPs always report to them).
  const optionsFor = (node) => {
    if (node.tier === "officer") return vpNames;
    if (node.tier === "chair") return [...vpNames, ...officerNames];
    return [];
  };

  const childrenOf = {};
  for (const node of structure) {
    if (node.supervisor_role) {
      (childrenOf[node.supervisor_role] ??= []).push(node);
    }
  }

  const root = structure.find((n) => n.tier === "president");
  // Anything without a supervisor can't hang off the tree — surface it
  // separately rather than letting it vanish.
  const orphans = structure.filter((n) => n.tier !== "president" && !n.supervisor_role);
  const vacant = structure.filter((n) => n.holders.length === 0).length;

  return (
    <>
      <p style={{ margin: "0 4px 16px", fontSize: "13px", color: "var(--muted)" }}>
        Who oversees whom. Officers report to a vice president; chairs report to a vice
        president or an officer. Use a card's dropdown to move it. This is organizational
        only — it does not grant anyone permissions.
        {vacant > 0 && (
          <strong style={{ color: "var(--status-ready-text)" }}> {vacant} seat{vacant === 1 ? "" : "s"} vacant.</strong>
        )}
      </p>

      <div style={{ border: "1px solid var(--border)", borderRadius: "12px", background: "var(--surface-muted)", padding: "18px 20px", overflowX: "auto" }}>
        <ul className="orgTree" style={{ minWidth: "460px" }}>
          {root && (
            <OrgBranch
              node={root}
              childrenOf={childrenOf}
              optionsFor={optionsFor}
              savingRole={savingRole}
              onRequestChange={onRequestChange}
              pending={pending}
            />
          )}
        </ul>
      </div>

      {orphans.length > 0 && (
        <div style={{ marginTop: "18px", border: "1px solid var(--status-ready-border)", borderRadius: "12px", background: "var(--status-ready-bg)", padding: "14px 16px" }}>
          <p style={{ margin: "0 0 10px", fontSize: "13px", fontWeight: 700, color: "var(--status-ready-text)" }}>
            Not in the chart yet ({orphans.length})
          </p>
          <p style={{ margin: "0 0 10px", fontSize: "12px", color: "var(--ink-soft)" }}>
            These roles have no supervisor, so they don't appear above. Pick one to place them.
          </p>
          {orphans.map((node) => (
            <OrgCard
              key={node.role}
              node={node}
              options={optionsFor(node)}
              savingRole={savingRole}
              onRequestChange={onRequestChange}
              pending={pending}
            />
          ))}
        </div>
      )}
    </>
  );
}

export default function MembersPage() {
  useDocumentTitle("Members");
  const { user } = useAuth();
  const { showToast } = useCart();

  const [members, setMembers] = useState(null);
  const [stats, setStats] = useState(null);
  const [roles, setRoles] = useState([]);
  const [structure, setStructure] = useState(null);
  const [loadError, setLoadError] = useState(false);
  const [savingId, setSavingId] = useState(null);

  const [tab, setTab] = useState("all");
  const [search, setSearch] = useState("");
  const [duesFilter, setDuesFilter] = useState("all");
  const [roleFilter, setRoleFilter] = useState("all");

  // Confirmation state doubles as the pending edit. Holding the requested
  // value here (rather than mutating on change) means the <select> can be
  // driven entirely from state — cancelling snaps it back on its own, with
  // no DOM poking.
  const [pendingRole, setPendingRole] = useState(null);      // {member, role}
  const [pendingReport, setPendingReport] = useState(null);  // {node, supervisorRole}

  // The president and both VPs reach this page; VPs are limited below.
  const authorized = user && canAssignRoles(user);
  const viewerIsPresident = isPresident(user);

  useEffect(() => {
    if (!authorized) return;
    let cancelled = false;
    Promise.all([getAdminMembers(), getAdminStats(), getAssignableRoles(), getOrgStructure()])
      .then(([membersRes, statsRes, rolesRes, structureRes]) => {
        if (cancelled) return;
        setMembers(membersRes.data);
        setStats(statsRes.data);
        setRoles(rolesRes.data);
        setStructure(structureRes.data);
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
      if (tab === "eboard" && !isEboardRole(m.role)) return false;
      if (tab === "chairs" && !isChairRole(m.role)) return false;
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
  }, [members, tab, search, duesFilter, roleFilter]);

  const tabCounts = useMemo(() => ({
    all: members?.length ?? 0,
    eboard: members?.filter((m) => isEboardRole(m.role)).length ?? 0,
    chairs: members?.filter((m) => isChairRole(m.role)).length ?? 0,
  }), [members]);

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

  async function confirmRoleChange() {
    const { member, role } = pendingRole;
    const name = `${member.first_name} ${member.last_name}`;
    setSavingId(member.id);
    try {
      const res = await updateMemberRole(member.id, role);
      setMembers((prev) => prev.map((m) => (m.id === member.id ? res.data : m)));
      // A chair change rewrites is_chair rows, so the tree's holders moved.
      if (isChairRole(member.role) || isChairRole(role)) {
        getOrgStructure().then((r) => setStructure(r.data)).catch(() => {});
      }
      showToast(`${name} is now ${role}`);
    } catch (err) {
      showToast(err.response?.data?.detail || "Couldn't update the role");
    } finally {
      setSavingId(null);
      setPendingRole(null);
    }
  }

  async function confirmReportChange() {
    const { node, supervisorRole } = pendingReport;
    setSavingId(node.role);
    try {
      const res = await setRoleSupervisor(node.role, supervisorRole);
      setStructure((prev) => prev.map((n) => (n.role === node.role ? res.data : n)));
      showToast(`${node.role} now reports to ${supervisorRole}`);
    } catch (err) {
      showToast(err.response?.data?.detail || "Couldn't update the structure");
    } finally {
      setSavingId(null);
      setPendingReport(null);
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

      {/* View tabs — underline style, matching the Shop Manager. Reads as
          "which view" against the pill filters below, which refine it. */}
      <div style={{ display: "flex", gap: "4px", borderBottom: "1px solid var(--border)", flexWrap: "wrap", marginBottom: "18px" }}>
        {[
          { key: "all", label: "All", count: tabCounts.all },
          { key: "eboard", label: "E-Board", count: tabCounts.eboard },
          { key: "chairs", label: "Chairs", count: tabCounts.chairs },
          { key: "structure", label: "Structure" },
        ].map((t) => {
          const active = tab === t.key;
          return (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              style={{
                position: "relative",
                border: "none",
                background: "transparent",
                padding: "10px 14px 14px",
                fontSize: "14px",
                fontFamily: "inherit",
                fontWeight: active ? 700 : 600,
                color: active ? "var(--shpe-blue)" : "var(--muted)",
                cursor: "pointer",
              }}
            >
              {t.label}
              {t.count !== undefined && (
                <span style={{ marginLeft: "7px", background: active ? "var(--shpe-blue)" : "var(--surface-soft)", color: active ? "#fff" : "var(--muted)", borderRadius: "999px", padding: "1px 7px", fontSize: "11px" }}>
                  {t.count}
                </span>
              )}
              {active && (
                <span style={{ position: "absolute", left: "8px", right: "8px", bottom: 0, height: "2px", background: "var(--shpe-blue)", borderRadius: "999px" }} />
              )}
            </button>
          );
        })}
      </div>

      {tab === "structure" ? (
        <StructurePanel
          structure={structure}
          savingRole={savingId}
          onRequestChange={(node, supervisorRole) => setPendingReport({ node, supervisorRole })}
          pending={pendingReport}
        />
      ) : (
      <>
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
          // Only the president may change a top-tier role (president or
          // either VP) — the backend 403s a VP here, so don't offer a select
          // that can't succeed.
          const locked = isSelf || (!viewerIsPresident && TOP_TIER_ROLES.includes(m.role));
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
                  // Shows the pending pick while its dialog is open, so
                  // cancelling reverts by clearing state — no DOM poking.
                  value={pendingRole?.member.id === m.id ? pendingRole.role : m.role}
                  disabled={savingId === m.id}
                  onChange={(e) => setPendingRole({ member: m, role: e.target.value })}
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
      </>
      )}

      {pendingRole && (
        <ConfirmDialog
          title="Change role?"
          confirmLabel="Change role"
          busy={savingId === pendingRole.member.id}
          onCancel={() => setPendingRole(null)}
          onConfirm={confirmRoleChange}
          body={
            <>
              <p style={{ margin: 0 }}>
                Change <strong>{pendingRole.member.first_name} {pendingRole.member.last_name}</strong> from{" "}
                <strong>{pendingRole.member.role}</strong> to <strong>{pendingRole.role}</strong>?
              </p>
              {(isChairRole(pendingRole.member.role) || isChairRole(pendingRole.role)) && (
                <p style={{ margin: "12px 0 0", padding: "10px 12px", borderRadius: "10px", background: "var(--surface-tint)", color: "var(--ink-soft)" }}>
                  This also updates that committee's chair listing. The About page roster is
                  maintained by hand and won't change.
                </p>
              )}
            </>
          }
        />
      )}

      {pendingReport && (
        <ConfirmDialog
          title="Change reporting line?"
          confirmLabel="Move"
          busy={savingId === pendingReport.node.role}
          onCancel={() => setPendingReport(null)}
          onConfirm={confirmReportChange}
          body={
            <>
              <p style={{ margin: 0 }}>
                Have <strong>{pendingReport.node.role}</strong> report to{" "}
                <strong>{pendingReport.supervisorRole}</strong>
                {pendingReport.node.supervisor_role
                  ? <> instead of <strong>{pendingReport.node.supervisor_role}</strong>?</>
                  : <>?</>}
              </p>
              <p style={{ margin: "12px 0 0", fontSize: "13px", color: "var(--muted)" }}>
                This records who oversees whom. It doesn't change anyone's permissions.
              </p>
            </>
          }
        />
      )}
    </div>
  );
}
