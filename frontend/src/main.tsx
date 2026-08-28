import React, { useEffect } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { App } from "./app/App";
import { JoinPage } from "./app/JoinPage";
import { InvitePage } from "./app/InvitePage";
import { TaskCreatePage } from "./app/TaskCreatePage";
import "./styles.css";

const client = new QueryClient({ defaultOptions: { queries: { retry: 1, staleTime: 20_000 } } });
if ("serviceWorker" in navigator) {
  navigator.serviceWorker.getRegistrations().then((registrations) =>
    registrations.forEach((registration) => registration.unregister()),
  );
}
function CreateRedirect() {
  useEffect(() => {
    const redirect = (event: MouseEvent) => {
      const button = (event.target as Element | null)?.closest("button");
      if (button?.textContent?.trim().startsWith("Crear") && !button.closest('[role="dialog"]')) {
        event.preventDefault();
        event.stopPropagation();
        window.location.assign("/app/create");
      }
    };
    window.addEventListener("click", redirect, true);
    return () => window.removeEventListener("click", redirect, true);
  }, []);
  return null;
}

const pathname = window.location.pathname;
const page = pathname === "/join" ? <JoinPage /> : pathname === "/invite" ? <InvitePage /> : pathname === "/app/create" ? <TaskCreatePage /> : <><CreateRedirect /><App /></>;
createRoot(document.getElementById("root")!).render(<React.StrictMode><QueryClientProvider client={client}><BrowserRouter>{page}</BrowserRouter></QueryClientProvider></React.StrictMode>);
