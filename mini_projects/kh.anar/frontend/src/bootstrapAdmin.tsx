import React from "react";
import { createRoot } from "react-dom/client";
import AdminPanel from "./components/AdminPanel";

const mountAdmin = () => {
  const el = document.getElementById("admin-root");
  if (el) {
    createRoot(el).render(<AdminPanel />);
  }
};

// manuális mountolás kitetéle fejlesztéshez vagy tesztekhez
export default mountAdmin;
