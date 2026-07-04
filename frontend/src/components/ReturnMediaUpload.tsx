import { useRef } from "react";

export interface ReturnMedia {
  url: string;
  type: "image" | "video";
  name: string;
}

interface Props {
  media: ReturnMedia | null;
  onUpload: (file: File, url: string) => void;
  onClear: () => void;
}

const ACCEPT = "image/*,video/*";

export function ReturnMediaUpload({ media, onUpload, onClear }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const url = URL.createObjectURL(file);
    onUpload(file, url);
    e.target.value = "";
  };

  return (
    <section className="return-upload">
      <div className="return-upload__head">
        <label className="return-upload__title">Return inspection media</label>
        {media && (
          <button type="button" className="btn btn--ghost return-upload__clear" onClick={onClear}>
            Clear
          </button>
        )}
      </div>

      {media ? (
        <div className="return-upload__preview">
          {media.type === "video" ? (
            <video src={media.url} controls className="return-upload__media" />
          ) : (
            <img src={media.url} alt="Return inspection" className="return-upload__media" />
          )}
          <span className="return-upload__filename">{media.name}</span>
        </div>
      ) : (
        <button
          type="button"
          className="return-upload__dropzone"
          onClick={() => inputRef.current?.click()}
        >
          <span className="return-upload__icon">📷</span>
          <span className="return-upload__label">Upload return photo or video</span>
          <span className="return-upload__hint">JPEG, PNG, MP4, WebM</span>
        </button>
      )}

      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT}
        className="sr-only"
        onChange={handleChange}
      />

      {media && (
        <button
          type="button"
          className="btn return-upload__replace"
          onClick={() => inputRef.current?.click()}
        >
          Replace file
        </button>
      )}
    </section>
  );
}
