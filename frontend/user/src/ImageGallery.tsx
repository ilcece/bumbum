import { useEffect, useRef, useState } from "react";

export function ImageGallery({ urls, name }: { urls: string[]; name: string }) {
  const [current, setCurrent] = useState(urls[0]);
  const [failed, setFailed] = useState<string[]>([]);
  const [open, setOpen] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  const modal = useRef<HTMLDivElement>(null);
  const start = useRef<number | null>(null);
  const index = Math.max(0, urls.indexOf(current));
  useEffect(() => {
    if (!urls.includes(current)) setCurrent(urls[0]);
    if (!urls.length) setOpen(false);
  }, [urls.join("\n")]);
  useEffect(() => {
    if (!open) return;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    modal.current?.querySelector<HTMLButtonElement>("button")?.focus();
    return () => {
      document.body.style.overflow = overflow;
      trigger.current?.focus();
    };
  }, [open]);
  function move(change: number) {
    const next = index + change;
    if (next >= 0 && next < urls.length) setCurrent(urls[next]);
  }
  const image =
    current && !failed.includes(current) ? (
      <img
        src={current}
        alt={`${name}，第${index + 1}张图片`}
        referrerPolicy="no-referrer"
        onError={() => setFailed((list) => [...list, current])}
      />
    ) : (
      <div className="image-placeholder">图片暂不可用</div>
    );
  const count = urls.length > 1 && (
    <div className="image-controls">
      <button
        aria-label="上一张图片"
        disabled={index === 0}
        onClick={() => move(-1)}
      >
        ←
      </button>
      <span>
        {index + 1} / {urls.length}
      </span>
      <button
        aria-label="下一张图片"
        disabled={index === urls.length - 1}
        onClick={() => move(1)}
      >
        →
      </button>
    </div>
  );
  const touch = {
    onTouchStart: (e: React.TouchEvent) => {
      start.current = e.touches[0]?.clientX ?? null;
    },
    onTouchEnd: (e: React.TouchEvent) => {
      const end = e.changedTouches[0]?.clientX;
      if (
        start.current !== null &&
        end !== undefined &&
        Math.abs(end - start.current) > 35
      )
        move(end < start.current ? 1 : -1);
      start.current = null;
    },
  };
  return (
    <section
      className="gallery"
      aria-label="服装图片"
      {...touch}
      onKeyDown={(e) => {
        if (e.key === "ArrowLeft") move(-1);
        if (e.key === "ArrowRight") move(1);
      }}
    >
      <button
        ref={trigger}
        className="image-open"
        aria-label="放大服装图片"
        onClick={() => setOpen(true)}
        disabled={!urls.length}
      >
        {image}
      </button>
      {count}
      {open && (
        <div
          ref={modal}
          role="dialog"
          aria-modal="true"
          aria-label="服装图片大图"
          className="image-modal"
          onKeyDown={(e) => {
            if (e.key === "Escape") setOpen(false);
            if (e.key === "Tab") {
              const buttons = [
                ...(modal.current?.querySelectorAll<HTMLButtonElement>(
                  "button:not(:disabled)",
                ) || []),
              ];
              const first = buttons[0],
                last = buttons[buttons.length - 1];
              if (e.shiftKey && document.activeElement === first) {
                e.preventDefault();
                last?.focus();
              } else if (!e.shiftKey && document.activeElement === last) {
                e.preventDefault();
                first?.focus();
              }
            }
          }}
        >
          <button
            className="close-image"
            onClick={() => setOpen(false)}
            aria-label="关闭大图"
          >
            关闭 ×
          </button>
          {image}
          {count}
        </div>
      )}
    </section>
  );
}
