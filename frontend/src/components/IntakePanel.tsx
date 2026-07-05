import { useRef, useState } from "react";

export interface IntakeResult {
  plate: string;
  pickupFile: File;
  returnFile: File;
  pickupUrl: string;
  returnUrl: string;
}

interface Props {
  onRun: (result: IntakeResult) => void | Promise<void>;
}

interface Picked {
  file: File;
  url: string;
  type: "image" | "video";
}

function UploadZone({
  label,
  hint,
  icon,
  picked,
  onPick,
  onClear,
}: {
  label: string;
  hint: string;
  icon: string;
  picked: Picked | null;
  onPick: (file: File, url: string) => void;
  onClear: () => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const open = () => inputRef.current?.click();

  const handleFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    onPick(file, URL.createObjectURL(file));
    e.target.value = "";
  };

  return (
    <div className="intake__slot">
      <div className="intake__slot-head">
        <label>{label}</label>
        {picked && (
          <button type="button" className="btn btn--ghost" onClick={onClear}>
            Clear
          </button>
        )}
      </div>
      <div
        className={`intake__drop${picked ? " intake__drop--filled" : ""}`}
        role="button"
        tabIndex={0}
        onClick={open}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            open();
          }
        }}
      >
        {picked ? (
          picked.type === "video" ? (
            <video src={picked.url} className="intake__preview" muted />
          ) : (
            <img src={picked.url} alt={`${label} preview`} className="intake__preview" />
          )
        ) : (
          <div className="intake__placeholder">
            <span className="intake__icon">{icon}</span>
            <span className="intake__label">{label}</span>
            <span className="intake__hint">{hint}</span>
          </div>
        )}
      </div>
      <input
        ref={inputRef}
        type="file"
        accept="image/*,video/*"
        className="sr-only"
        onChange={handleFile}
      />
    </div>
  );
}

export function IntakePanel({ onRun }: Props) {
  const [plate, setPlate] = useState("AB-123-CD");
  const [pickup, setPickup] = useState<Picked | null>(null);
  const [ret, setRet] = useState<Picked | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const pick = (setter: (p: Picked | null) => void, prev: Picked | null) => (file: File, url: string) => {
    if (prev?.url.startsWith("blob:")) URL.revokeObjectURL(prev.url);
    setter({ file, url, type: file.type.startsWith("video/") ? "video" : "image" });
  };

  const clear = (setter: (p: Picked | null) => void, prev: Picked | null) => () => {
    if (prev?.url.startsWith("blob:")) URL.revokeObjectURL(prev.url);
    setter(null);
  };

  const ready = !!pickup && !!ret && plate.trim().length > 0 && !submitting;

  const run = async () => {
    if (!pickup || !ret || !ready) return;
    setSubmitting(true);
    await onRun({
      plate: plate.trim(),
      pickupFile: pickup.file,
      returnFile: ret.file,
      pickupUrl: pickup.url,
      returnUrl: ret.url,
    });
  };

  return (
    <div className="intake">
      <div className="intake__card">
        <header className="intake__header">
          <span className="intake__logo">◈</span>
          <div>
            <h1>StateProof</h1>
            <p>Proof of how it was. Upload the pickup and return media to run the audit.</p>
          </div>
        </header>

        <label className="intake__field">
          <span>License plate</span>
          <input
            className="intake__plate-input"
            value={plate}
            onChange={(e) => setPlate(e.target.value.toUpperCase())}
            placeholder="AB-123-CD"
            spellCheck={false}
          />
        </label>

        <div className="intake__grid">
          <UploadZone
            label="Pickup baseline"
            hint="JPEG, PNG, MP4, WebM"
            icon="📷"
            picked={pickup}
            onPick={pick(setPickup, pickup)}
            onClear={clear(setPickup, pickup)}
          />
          <UploadZone
            label="Return condition"
            hint="JPEG, PNG, MP4, WebM"
            icon="🔍"
            picked={ret}
            onPick={pick(setRet, ret)}
            onClear={clear(setRet, ret)}
          />
        </div>

        <button className="btn btn--primary intake__run" disabled={!ready} onClick={run}>
          {submitting ? "Analyzing…" : "Run audit"}
        </button>
        <p className="intake__foot">
          The analysis compares the two uploads and classifies each difference as damage,
          normal wear, or an agreed change.
        </p>
      </div>
    </div>
  );
}
