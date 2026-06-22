/* eslint-disable no-unused-vars */
import { useState, useRef, useEffect } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import shpeHoriztonalLogo from "../assets/logos/shpeHorizontalLogo.png";
import { useAuth } from "../context/AuthContext";
import Avatar from "./Avatar";

const links = [
  { label: "Home", to: "/" },
  { label: "About", to: "/about" },
  { label: "MemberSHPE", to: "/membershpe" },
  { label: "Our Sponsors", to: "/sponsors" },
  { label: "Gallery", to: "/gallery" },
  { label: "Calendar", to: "/calendar" },
];

// Member-only tabs — grouped under the account dropdown once signed in.
// Add new member features here; they land in the menu, not the top nav.
const memberLinks = [
  { label: "Dashboard", to: "/dashboard" },
  { label: "Committees", to: "/committees" },
  { label: "Profile", to: "/profile" },
];

function NavItem({ to, children }) {
  return (
    <NavLink to={to} className="navLink">
      {({ isActive }) => (
        <span className={`navLinkInner ${isActive ? "active" : ""}`}>
          {children}
          {isActive && (
            <motion.span
              className="underline"
              layoutId="nav-underline"
              initial={false}
              animate={{ opacity: isActive ? 1 : 0 }}
              transition={{ type: "spring", stiffness: 380, damping: 30 }}
            />
          )}
        </span>
      )}
    </NavLink>
  );
}

function MemberMenu({ user, open, setOpen, onSignOut, menuRef }) {
  const location = useLocation();
  const onMember = memberLinks.some((l) => l.to === location.pathname);
  return (
    <div className="memberMenu" ref={menuRef}>
      <button
        type="button"
        className={`memberPill ${open ? "open" : ""} ${onMember ? "onMember" : ""}`}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        <Avatar name={user.first_name} size={26} />
        Hi, {user.first_name}
        <span className={`memberPillCaret ${open ? "open" : ""}`}>▾</span>
      </button>

      {open && (
        <div className="memberMenuPanel" role="menu">
          <div className="memberMenuLabel">Member area</div>
          {memberLinks.map((l) => {
            const active = location.pathname === l.to;
            return (
              <NavLink
                key={l.to}
                to={l.to}
                role="menuitem"
                className={`memberMenuItem ${active ? "active" : ""}`}
                onClick={() => setOpen(false)}
              >
                <span className="memberMenuDot" />
                {l.label}
              </NavLink>
            );
          })}
          <div className="memberMenuDivider" />
          <button
            type="button"
            className="memberMenuSignout"
            role="menuitem"
            onClick={() => {
              setOpen(false);
              onSignOut();
            }}
          >
            Sign Out
          </button>
        </div>
      )}
    </div>
  );
}

export default function Header() {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [isMemberMenuOpen, setIsMemberMenuOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const memberMenuRef = useRef(null);

  // Calendar lives in the public nav when signed out; once signed in it moves
  // into the member dropdown, so drop it from the top nav.
  const navLinks = user ? links.filter((l) => l.to !== "/calendar") : links;

  // Close the member dropdown when clicking anywhere outside of it.
  useEffect(() => {
    function handleClickOutside(event) {
      if (memberMenuRef.current && !memberMenuRef.current.contains(event.target)) {
        setIsMemberMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Close the mobile menu whenever the route changes. Render-phase reset
  // instead of an effect — see "You Might Not Need an Effect" (React docs).
  const [prevPath, setPrevPath] = useState(location.pathname);
  if (prevPath !== location.pathname) {
    setPrevPath(location.pathname);
    setIsMobileMenuOpen(false);
    setIsMemberMenuOpen(false);
  }

  function handleSignOut() {
    logout();
    navigate("/");
  }

  return (
    <header className="header">
      <div className="headerRow">
        <div className="brand">
          <div className="brandMark">
            <img src={shpeHoriztonalLogo} alt="SHPE UH" onClick={() => navigate("/")} style={{ cursor: "pointer" }} />
          </div>
        </div>

        <button
          type="button"
          className="mobileMenuBtn"
          aria-label="Toggle navigation menu"
          aria-expanded={isMobileMenuOpen}
          aria-controls="mobile-nav-panel"
          onClick={() => setIsMobileMenuOpen((open) => !open)}
        >
          Menu
        </button>

        <nav className="nav">
          {navLinks.map((l) => (
            <NavItem key={l.to} to={l.to}>
              {l.label}
            </NavItem>
          ))}

          {user ? (
            <MemberMenu
              user={user}
              open={isMemberMenuOpen}
              setOpen={setIsMemberMenuOpen}
              onSignOut={handleSignOut}
              menuRef={memberMenuRef}
            />
          ) : (
            <button
              className="primaryBtn"
              onClick={() => navigate("/signin")}
              style={{ marginLeft: "8px", fontSize: "14px", padding: "6px 16px" }}
            >
              Sign In
            </button>
          )}
        </nav>
      </div>

      <nav
        id="mobile-nav-panel"
        className={`mobileNavPanel ${isMobileMenuOpen ? "open" : ""}`}
      >
        <div className="mobileNavGrid">
          {navLinks.map((l) => (
            <NavLink key={l.to} to={l.to} className="mobileNavLink">
              {({ isActive }) => (
                <span className={`mobileNavLinkInner ${isActive ? "active" : ""}`}>
                  {l.label}
                </span>
              )}
            </NavLink>
          ))}
          {user &&
            memberLinks.map((l) => (
              <NavLink key={l.to} to={l.to} className="mobileNavLink">
                {({ isActive }) => (
                  <span className={`mobileNavLinkInner ${isActive ? "active" : ""}`}>
                    {l.label}
                  </span>
                )}
              </NavLink>
            ))}
          {user ? (
            <button
              className="mobileNavLink"
              onClick={handleSignOut}
              style={{ textAlign: "left", background: "none", border: "none", cursor: "pointer", width: "100%" }}
            >
              <span className="mobileNavLinkInner">Sign Out</span>
            </button>
          ) : (
            <NavLink to="/signin" className="mobileNavLink">
              {({ isActive }) => (
                <span className={`mobileNavLinkInner ${isActive ? "active" : ""}`}>
                  Sign In
                </span>
              )}
            </NavLink>
          )}
        </div>
      </nav>
    </header>
  );
}
