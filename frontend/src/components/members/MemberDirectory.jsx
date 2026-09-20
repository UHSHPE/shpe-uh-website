import { TOP_TIER_ROLES } from "../../utils/shop";
import Pagination from "../Pagination";

const DUES_FILTERS = [
  { key: "all", label: "Everyone" },
  { key: "paid", label: "Dues paid" },
  { key: "unpaid", label: "Not paid" },
];

const memberRow = {
  display: "grid",
  gridTemplateColumns:
    "minmax(200px, 1.6fr) 110px 64px 100px minmax(180px, 1fr)",
  gap: "12px",
  alignItems: "center",
  padding: "12px 16px",
  minWidth: "700px",
};

function DuesPill({ paid }) {
  const meta = paid
    ? {
        label: "Paid",
        color: "var(--status-picked-text)",
        bg: "var(--status-picked-bg)",
        border: "var(--status-picked-border)",
      }
    : {
        label: "Not paid",
        color: "var(--status-ready-text)",
        bg: "var(--status-ready-bg)",
        border: "var(--status-ready-border)",
      };
  return (
    <span
      style={{
        display: "inline-block",
        padding: "3px 10px",
        borderRadius: "999px",
        fontSize: "12px",
        fontWeight: 700,
        color: meta.color,
        background: meta.bg,
        border: `1px solid ${meta.border}`,
        whiteSpace: "nowrap",
      }}
    >
      {meta.label}
    </span>
  );
}

export default function MemberDirectory({
  members,
  visibleCount,
  pager,
  roles,
  userId,
  viewerIsPresident,
  savingId,
  pendingRole,
  search,
  duesFilter,
  roleFilter,
  loadError,
  onSearchChange,
  onDuesFilterChange,
  onRoleFilterChange,
  onOpenMember,
  onRequestRole,
}) {
  return (
    <>
      <div
        style={{
          display: "flex",
          gap: "10px",
          alignItems: "center",
          flexWrap: "wrap",
          marginBottom: "14px",
        }}
      >
        <input
          type="search"
          value={search}
          onChange={(event) => onSearchChange(event.target.value)}
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
          {DUES_FILTERS.map((filter) => {
            const active = duesFilter === filter.key;
            return (
              <button
                key={filter.key}
                type="button"
                onClick={() => onDuesFilterChange(filter.key)}
                style={{
                  padding: "7px 13px",
                  fontSize: "13px",
                  fontWeight: active ? 700 : 600,
                  fontFamily: "inherit",
                  color: active ? "#fff" : "var(--muted)",
                  background: active
                    ? "var(--shpe-blue)"
                    : "var(--surface-soft)",
                  border: "none",
                  borderRadius: "999px",
                  cursor: "pointer",
                }}
              >
                {filter.label}
              </button>
            );
          })}
        </div>
        <select
          value={roleFilter}
          onChange={(event) => onRoleFilterChange(event.target.value)}
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
          {roles.map((role) => (
            <option key={role} value={role}>
              {role}
            </option>
          ))}
        </select>
      </div>

      <div
        style={{
          border: "1px solid var(--border)",
          borderRadius: "12px",
          overflowX: "auto",
          background: "#fff",
        }}
      >
        <div
          style={{
            ...memberRow,
            background: "var(--surface-muted)",
            borderBottom: "1px solid var(--border)",
            fontSize: "11px",
            fontWeight: 700,
            letterSpacing: ".04em",
            textTransform: "uppercase",
            color: "var(--muted-soft)",
          }}
        >
          <span>Member</span>
          <span>Classification</span>
          <span>Points</span>
          <span>Dues</span>
          <span>Role</span>
        </div>
        {members === null && !loadError && (
          <p
            style={{
              margin: 0,
              padding: "20px 16px",
              fontSize: "14px",
              color: "var(--muted)",
            }}
          >
            Loading members…
          </p>
        )}
        {members !== null && visibleCount === 0 && (
          <p
            style={{
              margin: 0,
              padding: "20px 16px",
              fontSize: "14px",
              color: "var(--muted)",
            }}
          >
            No members match this search.
          </p>
        )}
        {pager.pageItems.map((member) => {
          const isSelf = member.id === userId;
          const locked =
            isSelf ||
            (!viewerIsPresident && TOP_TIER_ROLES.includes(member.role));
          return (
            <div
              key={member.id}
              className="memberRow"
              role="button"
              tabIndex={0}
              onClick={() => onOpenMember(member)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onOpenMember(member);
                }
              }}
              title="View full profile"
              style={{
                ...memberRow,
                borderBottom: "1px solid var(--surface-soft)",
                cursor: "pointer",
              }}
            >
              <div style={{ minWidth: 0 }}>
                <p
                  style={{
                    margin: 0,
                    fontSize: "14px",
                    fontWeight: 700,
                    color: "var(--ink)",
                    lineHeight: 1.25,
                  }}
                >
                  {member.first_name} {member.last_name}
                  {isSelf && (
                    <span
                      style={{
                        marginLeft: "8px",
                        fontSize: "11px",
                        fontWeight: 700,
                        color: "var(--shpe-blue)",
                        background: "var(--surface-tint)",
                        borderRadius: "999px",
                        padding: "2px 8px",
                      }}
                    >
                      You
                    </span>
                  )}
                </p>
                <p
                  style={{
                    margin: "2px 0 0",
                    fontSize: "12px",
                    color: "var(--muted-soft)",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {member.cougarnet_email}
                </p>
              </div>
              <span style={{ fontSize: "13px", color: "var(--ink-soft)" }}>
                {member.classification}
              </span>
              <span
                style={{
                  fontSize: "13px",
                  fontWeight: 700,
                  color: "var(--ink)",
                }}
              >
                {member.points}
              </span>
              <span>
                <DuesPill paid={member.has_paid_dues} />
              </span>
              <div
                onClick={(event) => event.stopPropagation()}
                onKeyDown={(event) => event.stopPropagation()}
              >
                {locked ? (
                  <span
                    style={{
                      fontSize: "13px",
                      fontWeight: 600,
                      color: "var(--muted)",
                    }}
                  >
                    {member.role}
                  </span>
                ) : (
                  <select
                    value={
                      pendingRole?.member.id === member.id
                        ? pendingRole.role
                        : member.role
                    }
                    disabled={savingId === member.id}
                    onChange={(event) =>
                      onRequestRole({ member, role: event.target.value })
                    }
                    style={{
                      padding: "7px 10px",
                      fontSize: "13px",
                      fontFamily: "inherit",
                      border: "1px solid var(--border-strong)",
                      borderRadius: "8px",
                      background: "#fff",
                      color: "var(--ink-soft)",
                      maxWidth: "100%",
                      opacity: savingId === member.id ? 0.6 : 1,
                    }}
                  >
                    {roles.map((role) => (
                      <option key={role} value={role}>
                        {role}
                      </option>
                    ))}
                  </select>
                )}
              </div>
            </div>
          );
        })}
      </div>
      <Pagination {...pager} label="accounts" />
      {members !== null && (
        <p
          style={{
            margin: "12px 4px 0",
            fontSize: "12px",
            color: "var(--muted-soft)",
          }}
        >
          Click a member to see their full profile, committees, and resume.
          Changing a chair role also updates that committee's chair
          automatically. The About page roster is maintained by hand and does
          not change.
        </p>
      )}
    </>
  );
}
