import { useEffect, useState } from "react";
import { Studio } from "./components/Studio";

// Minimal hash routing: #/report/:auditId. Defaults to the demo audit.
function auditIdFromHash(): string {
  const match = window.location.hash.match(/#\/report\/([^/?#]+)/);
  return match ? decodeURIComponent(match[1]) : "pr-1-run-1";
}

export default function App() {
  const [auditId, setAuditId] = useState(auditIdFromHash());

  useEffect(() => {
    const onHash = () => setAuditId(auditIdFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  return <Studio auditId={auditId} />;
}
