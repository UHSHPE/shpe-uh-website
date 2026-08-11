/* eslint-disable no-unused-vars */
import { FaFacebookF, FaXTwitter, FaTiktok, FaInstagram, FaLinkedinIn } from "react-icons/fa6";
import { motion } from "framer-motion";
import { href } from "react-router-dom";

import shpeHoriztonalWhite from "../assets/logos/shpeHorizontalWhite.png"


const socials = [
  { icon: <FaFacebookF />, label: "Facebook", href:"https://www.facebook.com/shpeuh" },
  { icon: <FaXTwitter />, label: "X", href:"https://twitter.com/shpe_uh" },
  { icon: <FaTiktok />, label: "TikTok", href:"https://www.tiktok.com/@shpe_uh" },
  { icon: <FaInstagram />, label: "Instagram", href:"https://www.instagram.com/shpe_uh/" },
  { icon: <FaLinkedinIn />, label: "LinkedIn", href:"https://www.linkedin.com/company/shpeuh/" },
];

export default function Footer() {
  return (
    <footer className="footer">
      <div className="footerInner">
        <div className="footerLeft">
          <div className="footerLogo">
            <div className="footerMark" >
              <img src={shpeHoriztonalWhite} alt="SHPE LOGO" />
            </div>
          </div>

          <div className="footerContact">
            <div>chapter@shpeuh.org</div>
            <div>@shpe_uh</div>
            <div>linktr.ee/SHPEUH</div>
          </div>
        </div>

        <div className="footerRight">
          <div className="footerFollow">Follow us on Social Media</div>
          <div className="socialRow">
            {socials.map((s) => (
              <motion.a
                key={s.label}
                href={s.href}
                target="_blank"
                rel="noopener noreferrer"
                className="socialBtn"
                whileHover={{ y: -3, scale: 1.03 }}
                whileTap={{ scale: 0.98 }}
                aria-label={s.label}
              >
                {s.icon}
              </motion.a>
            ))}
          </div>
        </div>
      </div>
    </footer>
  );
}
