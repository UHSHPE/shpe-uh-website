const TIER_STYLE = {
  president: {
    bg: "var(--shpe-navy)",
    fg: "#fff",
    sub: "rgba(255,255,255,.75)",
    border: "var(--shpe-navy)",
  },
  vp: {
    bg: "var(--surface-tint)",
    fg: "var(--shpe-navy)",
    sub: "var(--muted)",
    border: "var(--shpe-blue)",
  },
  officer: {
    bg: "#fff",
    fg: "var(--ink)",
    sub: "var(--muted-soft)",
    border: "var(--border-strong)",
  },
  chair: {
    bg: "#fff",
    fg: "var(--ink-soft)",
    sub: "var(--muted-soft)",
    border: "var(--border)",
  },
};

function holderNames(node) {
  if (!node.holders.length) return "Vacant";
  return node.holders
    .map((holder) => `${holder.first_name} ${holder.last_name}`)
    .join(", ");
}

function OrgCard({ node, options, savingRole, onRequestChange, pending }) {
  const tier = TIER_STYLE[node.tier] ?? TIER_STYLE.chair;
  const value =
    pending?.node.role === node.role
      ? pending.supervisorRole
      : (node.supervisor_role ?? "");
  const vacant = node.holders.length === 0;
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: "12px",
        flexWrap: "wrap",
        background: tier.bg,
        border: `1px solid ${tier.border}`,
        borderLeft: `4px solid ${tier.border}`,
        borderRadius: "10px",
        padding: "9px 14px",
        margin: "6px 0",
        boxShadow: "var(--shadow-card)",
      }}
    >
      <div style={{ minWidth: "170px", flex: "1 1 auto" }}>
        <p
          style={{
            margin: 0,
            fontSize: "13px",
            fontWeight: 800,
            color: tier.fg,
            lineHeight: 1.3,
          }}
        >
          {node.role}
        </p>
        <p
          style={{
            margin: "1px 0 0",
            fontSize: "12px",
            color: vacant ? "var(--status-ready-text)" : tier.sub,
          }}
        >
          {vacant ? "Vacant" : holderNames(node)}
          {node.holders.length > 1 && (
            <span style={{ marginLeft: "6px", fontSize: "11px", opacity: 0.8 }}>
              ({node.holders.length})
            </span>
          )}
        </p>
      </div>
      {options.length > 0 && (
        <select
          aria-label={`Who ${node.role} reports to`}
          value={value}
          disabled={savingRole === node.role}
          onChange={(event) => onRequestChange(node, event.target.value)}
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
          {!node.supervisor_role && (
            <option value="">— pick a supervisor —</option>
          )}
          {options.map((role) => (
            <option key={role} value={role}>
              {role}
            </option>
          ))}
        </select>
      )}
    </div>
  );
}

function OrgBranch({
  node,
  childrenOf,
  optionsFor,
  savingRole,
  onRequestChange,
  pending,
}) {
  const children = childrenOf[node.role] ?? [];
  return (
    <li>
      <OrgCard
        node={node}
        options={optionsFor(node)}
        savingRole={savingRole}
        onRequestChange={onRequestChange}
        pending={pending}
      />
      {children.length > 0 && (
        <ul>
          {children.map((child) => (
            <OrgBranch
              key={child.role}
              node={child}
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

export default function StructurePanel({
  structure,
  savingRole,
  onRequestChange,
  pending,
}) {
  if (!structure)
    return (
      <p style={{ margin: "8px 4px", fontSize: "14px", color: "var(--muted)" }}>
        Loading structure…
      </p>
    );

  const vicePresidents = structure
    .filter((node) => node.tier === "vp")
    .map((node) => node.role);
  const officers = structure
    .filter((node) => node.tier === "officer")
    .map((node) => node.role);
  const optionsFor = (node) =>
    node.tier === "officer"
      ? vicePresidents
      : node.tier === "chair"
        ? [...vicePresidents, ...officers]
        : [];
  const childrenOf = {};
  for (const node of structure) {
    if (node.supervisor_role)
      (childrenOf[node.supervisor_role] ??= []).push(node);
  }
  const root = structure.find((node) => node.tier === "president");
  const orphans = structure.filter(
    (node) => node.tier !== "president" && !node.supervisor_role,
  );
  const vacant = structure.filter((node) => node.holders.length === 0).length;

  return (
    <>
      <p
        style={{
          margin: "0 4px 16px",
          fontSize: "13px",
          color: "var(--muted)",
        }}
      >
        Who oversees whom. Officers report to a vice president; chairs report to
        a vice president or an officer. Use a card's dropdown to move it. This
        is organizational only — it does not grant anyone permissions.
        {vacant > 0 && (
          <strong style={{ color: "var(--status-ready-text)" }}>
            {" "}
            {vacant} seat{vacant === 1 ? "" : "s"} vacant.
          </strong>
        )}
      </p>
      <div
        style={{
          border: "1px solid var(--border)",
          borderRadius: "12px",
          background: "var(--surface-muted)",
          padding: "18px 20px",
          overflowX: "auto",
        }}
      >
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
        <div
          style={{
            marginTop: "18px",
            border: "1px solid var(--status-ready-border)",
            borderRadius: "12px",
            background: "var(--status-ready-bg)",
            padding: "14px 16px",
          }}
        >
          <p
            style={{
              margin: "0 0 10px",
              fontSize: "13px",
              fontWeight: 700,
              color: "var(--status-ready-text)",
            }}
          >
            Not in the chart yet ({orphans.length})
          </p>
          <p
            style={{
              margin: "0 0 10px",
              fontSize: "12px",
              color: "var(--ink-soft)",
            }}
          >
            These roles have no supervisor, so they don't appear above. Pick one
            to place them.
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
