import { formatOrderDate } from "../../utils/shop";
import Pagination from "../Pagination";

const timeStyle = {
  fontSize: "11px",
  color: "var(--muted-soft)",
  whiteSpace: "nowrap",
};

export default function NotificationsTab({
  notifications,
  unreadCount,
  pager,
  onMarkRead,
  onMarkAllRead,
}) {
  return (
    <>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "12px",
          marginBottom: "16px",
        }}
      >
        <p style={{ margin: 0, fontSize: "14px", color: "var(--muted)" }}>
          New-order alerts. Click an unread alert to mark it read.
        </p>
        {unreadCount > 0 && (
          <button
            onClick={onMarkAllRead}
            style={{
              borderRadius: "999px",
              padding: "7px 14px",
              fontSize: "13px",
              fontWeight: 700,
              border: "1px solid var(--border-strong)",
              background: "#fff",
              color: "var(--shpe-blue)",
              cursor: "pointer",
              whiteSpace: "nowrap",
            }}
          >
            Mark all read ({unreadCount})
          </button>
        )}
      </div>
      {notifications.length === 0 && (
        <div
          style={{
            textAlign: "center",
            padding: "32px",
            color: "var(--muted)",
            fontSize: "14px",
          }}
        >
          No notifications yet.
        </div>
      )}
      <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
        {pager.pageItems.map((notification) => (
          <div
            key={notification.id}
            onClick={
              notification.is_read
                ? undefined
                : () => onMarkRead(notification.id)
            }
            style={{
              border: `1px solid ${notification.is_read ? "var(--border)" : "var(--info-border)"}`,
              borderLeft: `4px solid ${notification.is_read ? "var(--border)" : "var(--shpe-blue-bright)"}`,
              borderRadius: "10px",
              padding: "12px 16px",
              background: notification.is_read ? "#fff" : "var(--surface-tint)",
              cursor: notification.is_read ? "default" : "pointer",
              display: "flex",
              justifyContent: "space-between",
              gap: "12px",
              alignItems: "flex-start",
            }}
          >
            <div
              style={{ display: "flex", gap: "10px", alignItems: "flex-start" }}
            >
              {!notification.is_read && (
                <span
                  style={{
                    width: "8px",
                    height: "8px",
                    borderRadius: "999px",
                    background: "var(--shpe-blue-bright)",
                    marginTop: "5px",
                    flexShrink: 0,
                  }}
                />
              )}
              <p
                style={{
                  margin: 0,
                  fontSize: "14px",
                  fontWeight: notification.is_read ? 400 : 600,
                  color: notification.is_read ? "var(--muted)" : "var(--ink)",
                }}
              >
                {notification.body}
              </p>
            </div>
            <span style={timeStyle}>
              {formatOrderDate(notification.created_at)}
            </span>
          </div>
        ))}
      </div>
      <Pagination {...pager} label="notifications" />
    </>
  );
}
