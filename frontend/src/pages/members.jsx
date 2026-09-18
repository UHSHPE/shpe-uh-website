/* eslint-disable no-unused-vars */
import { useEffect, useMemo, useState } from "react";
import { Navigate } from "react-router-dom";
import { motion } from "framer-motion";
import {
  getAdminMembers,
  getAdminStats,
  getAssignableRoles,
  getOrgStructure,
  setRoleSupervisor,
  updateMemberRole,
} from "../api/api";
import ConfirmDialog from "../components/ConfirmDialog";
import MemberDetailModal from "../components/MemberDetailModal";
import MemberDirectory from "../components/members/MemberDirectory";
import MemberStats from "../components/members/MemberStats";
import MemberTabs from "../components/members/MemberTabs";
import StructurePanel from "../components/members/StructurePanel";
import { useAuth } from "../context/AuthContext";
import { useCart } from "../context/CartContext";
import useDocumentTitle from "../hooks/useDocumentTitle";
import usePagination from "../hooks/usePagination";
import {
  canAssignRoles,
  isChairRole,
  isEboardRole,
  isPresident,
} from "../utils/shop";

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
  const [pendingRole, setPendingRole] = useState(null);
  const [detailMember, setDetailMember] = useState(null);
  const [pendingReport, setPendingReport] = useState(null);

  const authorized = user && canAssignRoles(user);
  const viewerIsPresident = isPresident(user);

  useEffect(() => {
    if (!authorized) return;
    let cancelled = false;
    Promise.all([
      getAdminMembers(),
      getAdminStats(),
      getAssignableRoles(),
      getOrgStructure(),
    ])
      .then(
        ([
          membersResponse,
          statsResponse,
          rolesResponse,
          structureResponse,
        ]) => {
          if (cancelled) return;
          setMembers(membersResponse.data);
          setStats(statsResponse.data);
          setRoles(rolesResponse.data);
          setStructure(structureResponse.data);
        },
      )
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
    return members.filter((member) => {
      if (tab === "eboard" && !isEboardRole(member.role)) return false;
      if (tab === "chairs" && !isChairRole(member.role)) return false;
      if (duesFilter === "paid" && !member.has_paid_dues) return false;
      if (duesFilter === "unpaid" && member.has_paid_dues) return false;
      if (roleFilter !== "all" && member.role !== roleFilter) return false;
      if (!needle) return true;
      return (
        `${member.first_name} ${member.last_name}`
          .toLowerCase()
          .includes(needle) ||
        member.cougarnet_email.toLowerCase().includes(needle) ||
        member.personal_email.toLowerCase().includes(needle) ||
        member.psid.includes(needle)
      );
    });
  }, [members, tab, search, duesFilter, roleFilter]);

  const pager = usePagination(visible, {
    resetKey: `${tab}|${search}|${duesFilter}|${roleFilter}`,
  });
  const tabCounts = useMemo(
    () => ({
      all: members?.length ?? 0,
      eboard:
        members?.filter((member) => isEboardRole(member.role)).length ?? 0,
      chairs: members?.filter((member) => isChairRole(member.role)).length ?? 0,
    }),
    [members],
  );

  if (!user)
    return (
      <div
        style={{
          minHeight: "60vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "var(--blue)",
          fontWeight: 600,
          fontFamily: "Work Sans, sans-serif",
        }}
      >
        Loading…
      </div>
    );
  if (!authorized) return <Navigate to="/dashboard" replace />;

  async function confirmRoleChange() {
    const { member, role } = pendingRole;
    setSavingId(member.id);
    try {
      const response = await updateMemberRole(member.id, role);
      setMembers((previous) =>
        previous.map((item) => (item.id === member.id ? response.data : item)),
      );
      if (isChairRole(member.role) || isChairRole(role))
        getOrgStructure()
          .then((result) => setStructure(result.data))
          .catch(() => {});
      showToast(`${member.first_name} ${member.last_name} is now ${role}`);
    } catch (error) {
      showToast(error.response?.data?.detail || "Couldn't update the role");
    } finally {
      setSavingId(null);
      setPendingRole(null);
    }
  }

  async function confirmReportChange() {
    const { node, supervisorRole } = pendingReport;
    setSavingId(node.role);
    try {
      const response = await setRoleSupervisor(node.role, supervisorRole);
      setStructure((previous) =>
        previous.map((item) =>
          item.role === node.role ? response.data : item,
        ),
      );
      showToast(`${node.role} now reports to ${supervisorRole}`);
    } catch (error) {
      showToast(
        error.response?.data?.detail || "Couldn't update the structure",
      );
    } finally {
      setSavingId(null);
      setPendingReport(null);
    }
  }

  const duesSince = stats
    ? new Date(stats.dues_period_start + "Z").toLocaleDateString(undefined, {
        month: "long",
        day: "numeric",
        year: "numeric",
      })
    : null;

  return (
    <div
      style={{
        maxWidth: "1040px",
        margin: "0 auto",
        padding: "16px 20px 80px",
        fontFamily: "Work Sans, sans-serif",
      }}
    >
      <motion.div
        initial={{ opacity: 0, y: -12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35 }}
      >
        <p
          style={{
            margin: 0,
            fontSize: "13px",
            fontWeight: 700,
            letterSpacing: ".06em",
            textTransform: "uppercase",
            color: "var(--shpe-red)",
          }}
        >
          President tools
        </p>
        <h1
          style={{
            margin: "4px 0 6px",
            fontSize: "30px",
            fontWeight: 800,
            color: "var(--shpe-navy)",
          }}
        >
          Members
        </h1>
        <p
          style={{
            margin: "0 0 24px",
            fontSize: "14px",
            color: "var(--muted)",
          }}
        >
          Every account on the site, with dues status and role assignment.
          {duesSince && (
            <>
              {" "}
              Dues period started{" "}
              <strong style={{ color: "var(--ink-soft)" }}>{duesSince}</strong>.
            </>
          )}
        </p>
      </motion.div>
      {loadError && (
        <p
          style={{
            margin: "0 0 24px",
            fontSize: "14px",
            color: "var(--shpe-red)",
            fontWeight: 600,
          }}
        >
          Couldn't load the member directory. Refresh to try again.
        </p>
      )}
      <MemberStats stats={stats} />
      <MemberTabs activeTab={tab} counts={tabCounts} onChange={setTab} />
      {tab === "structure" ? (
        <StructurePanel
          structure={structure}
          savingRole={savingId}
          onRequestChange={(node, supervisorRole) =>
            setPendingReport({ node, supervisorRole })
          }
          pending={pendingReport}
        />
      ) : (
        <MemberDirectory
          members={members}
          visibleCount={visible.length}
          pager={pager}
          roles={roles}
          userId={user.id}
          viewerIsPresident={viewerIsPresident}
          savingId={savingId}
          pendingRole={pendingRole}
          search={search}
          duesFilter={duesFilter}
          roleFilter={roleFilter}
          loadError={loadError}
          onSearchChange={setSearch}
          onDuesFilterChange={setDuesFilter}
          onRoleFilterChange={setRoleFilter}
          onOpenMember={setDetailMember}
          onRequestRole={setPendingRole}
        />
      )}

      {detailMember && (
        <MemberDetailModal
          memberId={detailMember.id}
          fallbackName={`${detailMember.first_name} ${detailMember.last_name}`}
          onClose={() => setDetailMember(null)}
        />
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
                Change{" "}
                <strong>
                  {pendingRole.member.first_name} {pendingRole.member.last_name}
                </strong>{" "}
                from <strong>{pendingRole.member.role}</strong> to{" "}
                <strong>{pendingRole.role}</strong>?
              </p>
              {(isChairRole(pendingRole.member.role) ||
                isChairRole(pendingRole.role)) && (
                <p
                  style={{
                    margin: "12px 0 0",
                    padding: "10px 12px",
                    borderRadius: "10px",
                    background: "var(--surface-tint)",
                    color: "var(--ink-soft)",
                  }}
                >
                  This also updates that committee's chair listing. The About
                  page roster is maintained by hand and won't change.
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
                {pendingReport.node.supervisor_role ? (
                  <>
                    {" "}
                    instead of{" "}
                    <strong>{pendingReport.node.supervisor_role}</strong>?
                  </>
                ) : (
                  <>?</>
                )}
              </p>
              <p
                style={{
                  margin: "12px 0 0",
                  fontSize: "13px",
                  color: "var(--muted)",
                }}
              >
                This records who oversees whom. It doesn't change anyone's
                permissions.
              </p>
            </>
          }
        />
      )}
    </div>
  );
}
