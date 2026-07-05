import { useEffect, useState } from "react";
import { Studio } from "./components/Studio";

// Minimal hash routing: #/report/:auditId deep-links an existing report.
// Without a hash we start on the intake screen (null) so nothing renders until upload.
function auditIdFromHash(): string | null {
  const match = window.location.hash.match(/#\/report\/([^/?#]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

export default function App() {
  const [auditId, setAuditId] = useState<string | null>(auditIdFromHash());

  useEffect(() => {
    document.title = "StateProof — Proof of how it was.";
  }, []);

  useEffect(() => {
    const onHash = () => setAuditId(auditIdFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  return <Studio auditId={auditId} />;
}
