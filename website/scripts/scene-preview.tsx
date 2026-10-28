/** Standalone review entry; bundle with esbuild to produce an offline preview. */
import React from "react";
import { createRoot } from "react-dom/client";
import { LanguageProvider } from "../lib/i18n";
import EmbodimentScene from "../components/embodiment/EmbodimentScene";

createRoot(document.getElementById("scene-root")!).render(<LanguageProvider><EmbodimentScene debug /></LanguageProvider>);
