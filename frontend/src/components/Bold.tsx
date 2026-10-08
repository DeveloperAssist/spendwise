import { Fragment } from "react";

/** AI text with its **bold** parts in bold. Everything else stays plain text: never parsed as HTML. */
export function Bold({ text }: { text: string }) {
  // split() with a capture group: every odd part is what was inside ** **
  return <>{text.split(/\*\*(.+?)\*\*/g).map((part, i) => (i % 2 ? <b key={i}>{part}</b> : <Fragment key={i}>{part}</Fragment>))}</>;
}
