import { useEffect, useLayoutEffect, useRef, useState, type PointerEvent } from "react";

export function ImageGallery({ urls, name }: { urls: string[]; name: string }) {
  const [index, setIndex] = useState(0);
  const [failed, setFailed] = useState<string[]>([]);
  const [open, setOpen] = useState(false);
  const active = useRef(0);
  const track = useRef<HTMLDivElement>(null);
  const enlarged = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const mouse = useRef<{ id: number; start: number; left: number; dragging: boolean } | null>(null);
  const suppressClick = useRef(false);

  function select(position: number) {
    active.current = position;
    setIndex(position);
  }

  useEffect(() => {
    if (!urls.length) setOpen(false);
    if (active.current >= urls.length) select(Math.max(0, urls.length - 1));
  }, [urls.length]);

  useLayoutEffect(() => {
    if (!open || !dialog.current || !enlarged.current) return;
    const modal = dialog.current;
    const full = enlarged.current;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    modal.showModal();
    full.scrollLeft = active.current * full.clientWidth;
    return () => {
      modal.close();
      document.body.style.overflow = overflow;
      const gallery = track.current;
      if (gallery) {
        gallery.scrollLeft = active.current * gallery.clientWidth;
        gallery.querySelectorAll<HTMLButtonElement>(".image-open")[active.current]?.focus({ preventScroll: true });
      } else trigger.current?.focus({ preventScroll: true });
    };
  }, [open]);

  const current = Math.min(index, Math.max(0, urls.length - 1));

  function scrollToPhoto(element: HTMLDivElement, position: number) {
    if (position < 0 || position >= urls.length) return;
    element.scrollTo({
      left: position * element.clientWidth,
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
    });
  }

  function pointerDown(event: PointerEvent<HTMLDivElement>) {
    suppressClick.current = false;
    if (event.pointerType !== "mouse" || event.button !== 0) return;
    mouse.current = { id: event.pointerId, start: event.clientX, left: event.currentTarget.scrollLeft, dragging: false };
  }

  function pointerMove(event: PointerEvent<HTMLDivElement>) {
    const gesture = mouse.current;
    if (!gesture || gesture.id !== event.pointerId || !(event.buttons & 1)) return;
    const dx = event.clientX - gesture.start;
    const element = event.currentTarget;
    if (!gesture.dragging) {
      if (Math.abs(dx) < 6) return;
      gesture.dragging = true;
      element.setPointerCapture(event.pointerId);
      element.classList.add("gallery-track--dragging");
    }
    element.scrollLeft = gesture.left - dx;
    event.preventDefault();
  }

  function pointerEnd(event: PointerEvent<HTMLDivElement>) {
    const gesture = mouse.current;
    if (!gesture || gesture.id !== event.pointerId) return;
    mouse.current = null;
    if (!gesture.dragging) return;
    const element = event.currentTarget;
    const next = Math.round(element.scrollLeft / element.clientWidth);
    suppressClick.current = true;
    element.classList.remove("gallery-track--dragging");
    scrollToPhoto(element, next);
  }

  function photo(url: string, position: number, full = false) {
    return url && !failed.includes(url) ? <img
      className={full ? undefined : "product-image-frame"}
      src={url} alt={`${name}，第 ${position + 1} 张照片`} draggable={false}
      referrerPolicy="no-referrer" onError={() => setFailed((list) => list.includes(url) ? list : [...list, url])}
    /> : <div className={full ? "image-placeholder" : "image-placeholder product-image-frame"}>图片暂不可用</div>;
  }

  function strip(full = false) {
    const label = urls.length > 1 ? "物品照片，可左右滑动" : "物品照片";
    return <div className={full ? "photo-strip photo-strip--full" : "photo-strip"}>
      <div
        ref={full ? enlarged : track}
        className="gallery-track"
        role="region"
        aria-label={label}
        tabIndex={urls.length > 1 ? 0 : undefined}
        onScroll={(event) => {
          const element = event.currentTarget;
          if (full === open && element.clientWidth && urls.length) {
            const position = Math.min(urls.length - 1, Math.max(0, Math.round(element.scrollLeft / element.clientWidth)));
            if (active.current !== position) select(position);
          }
        }}
        onKeyDown={(event) => {
          if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
          event.preventDefault();
          event.currentTarget.focus({ preventScroll: true });
          scrollToPhoto(event.currentTarget, current + (event.key === "ArrowLeft" ? -1 : 1));
        }}
        onPointerDown={urls.length > 1 ? pointerDown : undefined}
        onPointerMove={urls.length > 1 ? pointerMove : undefined}
        onPointerUp={pointerEnd}
        onPointerCancel={pointerEnd}
        onClickCapture={(event) => {
          if (suppressClick.current && event.detail > 0) {
            suppressClick.current = false;
            event.stopPropagation();
          }
        }}>
        {!urls.length && photo("", 0)}
        {urls.map((url, i) => full ? (
          <div key={`${i}-${url}`} className="gallery-slide" aria-hidden={i !== current}>{photo(url, i, true)}</div>
        ) : (
          <button
            key={`${i}-${url}`} type="button" className="gallery-slide image-open"
            aria-label={i === current ? "放大服装图片" : `放大第 ${i + 1} 张图片`}
            tabIndex={i === current ? 0 : -1}
            onClick={(event) => { trigger.current = event.currentTarget; select(i); setOpen(true); }}
          >{photo(url, i)}</button>
        ))}
      </div>
      {urls.length > 1 && <>
        <span className="gallery-position" role="status">物品照片 · {current + 1} / {urls.length}</span>
        <span className="gallery-progress" aria-hidden="true">
          {urls.map((url, i) => <span key={`${i}-${url}`} className={i === current ? "current" : undefined} />)}
        </span>
      </>}
    </div>;
  }

  return <section className="gallery" aria-label="物品图片">
    {strip()}
    {open && <dialog ref={dialog} className="image-modal" aria-label="服装图片大图" onCancel={(event) => {
      event.preventDefault();
      setOpen(false);
    }}>
      <button type="button" className="close-image" autoFocus onClick={() => setOpen(false)} aria-label="关闭大图">关闭 ×</button>
      {strip(true)}
    </dialog>}
  </section>;
}
