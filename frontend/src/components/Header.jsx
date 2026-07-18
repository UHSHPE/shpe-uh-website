/* eslint-disable no-unused-vars */
import { useState, useRef, useEffect } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import shpeHoriztonalLogo from "../assets/logos/shpeHorizontalLogo.png";
import { useAuth } from "../context/AuthContext";
import { useCart } from "../context/CartContext";
import { isShopManager } from "../utils/shop";
import Avatar from "./Avatar";
import { CartIcon } from "./shopIcons";

const links = [
  { label: "Home", to: "/" },
  { label: "About", to: "/about" },
  { label: "MemberSHPE", to: "/membershpe" },
  { label: "Our Sponsors", to: "/sponsors" },
  { label: "Gallery", to: "/gallery" },
  { label: "Calendar", to: "/calendar" },
  { label: "Shop", to: "/shop" },
];

// Member-only tabs — grouped under the account dropdown once signed in.
// Add new member features here; they land in the menu, not the top nav.
const memberLinks = [
  { label: "Dashboard", to: "/dashboard" },
  { label: "Committees", to: "/committees" },
  { label: "Profile", to: "/profile" },
];

// Shop admins get an extra tab (after Committees) to the shop-management page.
function memberLinksFor(user) {
  if (user && isShopManager(user)) {
    return [
      ...memberLinks.slice(0, 2),
      { label: "Shop Manager", to: "/shop-manager" },
      ...memberLinks.slice(2),
    ];
  }
  return memberLinks;
}

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

// Header cart icon with the orange count badge; opens the cart drawer.
function CartButton({ className }) {
  const { count, openCart } = useCart();
  return (
    <button
      type="button"
      className={`cartBtn ${className ?? ""}`}
      aria-label="Open cart"
      onClick={openCart}
    >
      <CartIcon size={20} />
      {count > 0 && <span className="cartBtnBadge">{count}</span>}
    </button>
  );
}

function MemberMenu({ user, links, open, setOpen, onSignOut, menuRef }) {
  const location = useLocation();
  const onMember = links.some((l) => l.to === location.pathname);
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
          {links.map((l) => {
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

  // The calendar is public — it stays in the top nav whether signed in or not.
  const navLinks = links;
  // Member dropdown/mobile links, with the Shop Manager tab for shop admins.
  const memberNav = memberLinksFor(user);

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

        <CartButton className="cartBtnMobile" />
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

          <CartButton className="cartBtnDesktop" />

          {user ? (
            <MemberMenu
              user={user}
              links={memberNav}
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
            memberNav.map((l) => (
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
