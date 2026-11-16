import React from "react";
import ReactDOM from "react-dom/client";
import Home from "../app/page";
import "../app/globals.css";
import "../app/library.css";
import "../app/froja-enhancements.css";
import "../app/professional.css";
import "../app/stainless-theme.css";
import "../app/cyan-metal-theme.css";
import "../app/skyline-theme.generated.css";
import "../app/skyline-theme.css";
import "../app/graphite-theme.generated.css";
import "../app/graphite-theme.css";
import "../app/layout-fixes.css";
import "../app/led-colours.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Home />
  </React.StrictMode>,
);
