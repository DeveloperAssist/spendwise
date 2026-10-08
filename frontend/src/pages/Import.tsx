import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, FileSpreadsheet, FileUp, History, Undo2 } from "lucide-react";
import { type DragEvent, useRef, useState } from "react";
import { ErrorNote, PageHeader } from "../components/ui";
import { api, download } from "../lib/api";
import { plural } from "../lib/format";
import type { ImportResult } from "../lib/types";

export default function ImportPage() {
  const qc = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  const history = useQuery({ queryKey: ["imports"], queryFn: () => api<ImportResult[]>("/api/imports") });
  const upload = useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return api<ImportResult>("/api/imports", { method: "POST", body: form });
    },
    onSuccess: () => qc.invalidateQueries(),
  });
  const undo = useMutation({
    mutationFn: (id: number) => api(`/api/imports/${id}`, { method: "DELETE" }),
    onSuccess: () => { upload.reset(); qc.invalidateQueries(); },
  });

  const pick = (files: FileList | null) => files?.[0] && upload.mutate(files[0]);
  const onDrop = (e: DragEvent) => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files); };
  const r = upload.data;

  return (
    <>
      <PageHeader title="Import a statement" subtitle="CSV or Excel from your bank or UPI app. Duplicates are skipped automatically." />
      <div
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)} onDrop={onDrop}
        onClick={() => input.current?.click()}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            input.current?.click();
          }
        }}
        role="button" tabIndex={0} aria-label="Choose a statement file to import"
        className={`card flex cursor-pointer flex-col items-center border-2 border-dashed py-14 text-center transition ${drag ? "border-brand-500 bg-brand-50" : "border-slate-300 hover:border-brand-500"}`}
      >
        <span className="grid size-14 place-items-center rounded-2xl bg-brand-50 text-brand-600"><FileUp className="size-7" /></span>
        <h2 className="mt-4 font-semibold">{upload.isPending ? "Reading your statement…" : "Drop your statement here, or click to choose"}</h2>
        <p className="mt-1 text-sm text-slate-500">.csv or .xlsx, up to 2 MB. Debit/Credit columns, a Dr/Cr column, or signed amounts all work.</p>
        <input ref={input} type="file" accept=".csv,.xlsx" hidden onChange={(e) => { pick(e.target.files); e.target.value = ""; }} />
      </div>
      <div className="mt-3 text-center text-sm text-slate-500">
        No statement handy?{" "}
        <button className="font-semibold text-brand-700 hover:underline" onClick={() => download("/api/imports/sample", "sample_statement.csv")}>
          Download the sample statement
        </button>{" "}
        (made-up data), then drop it above.
      </div>

      <div className="mt-4"><ErrorNote error={upload.error || undo.error} /></div>

      {r && (
        <div className="card mt-4">
          <div className="flex items-start gap-3">
            <CheckCircle2 className="mt-0.5 size-6 text-emerald-600" />
            <div className="flex-1">
              <h2 className="font-semibold">Imported {r.filename}</h2>
              <p className="mt-1 text-sm text-slate-600">
                <b>{r.added}</b> new payment{r.added === 1 ? "" : "s"} · <b>{r.duplicates}</b> already there · <b>{r.skipped}</b> row{r.skipped === 1 ? "" : "s"} skipped
              </p>
              {Object.keys(r.categorized_by).length > 0 && (
                <p className="mt-1 text-sm text-slate-500">
                  Sorted by: {Object.entries(r.categorized_by).map(([k, v]) => `${v} by ${k === "ai" ? "AI" : k}`).join(", ")}
                </p>
              )}
              {r.skipped_rows.length > 0 && (
                <details className="mt-3 text-sm">
                  <summary className="cursor-pointer font-medium text-slate-700">Why were rows skipped?</summary>
                  <ul className="mt-2 space-y-1 text-slate-500">
                    {r.skipped_rows.map((s) => <li key={s.line}>Line {s.line}: {s.reason}</li>)}
                  </ul>
                </details>
              )}
            </div>
          </div>
        </div>
      )}

      <div className="card mt-6">
        <h2 className="flex items-center gap-2 font-semibold"><History className="size-4.5" /> Past imports</h2>
        {history.data?.length ? (
          <ul className="mt-3 divide-y divide-slate-100">
            {history.data.map((b) => (
              <li key={b.id} className="flex items-center gap-3 py-3 text-sm">
                <FileSpreadsheet className="size-5 text-slate-400" />
                <div className="flex-1">
                  <div className="font-medium">{b.filename}</div>
                  <div className="text-xs text-slate-500">{new Date(b.created_at).toLocaleString("en-IN")} · {b.added} added</div>
                </div>
                <button className="btn-ghost !py-1.5 text-xs" disabled={undo.isPending}
                  onClick={() => confirm(`Undo ${b.filename}? Its ${plural(b.added, "payment")} will be removed.`) && undo.mutate(b.id)}>
                  <Undo2 className="size-3.5" /> Undo
                </button>
              </li>
            ))}
          </ul>
        ) : <p className="mt-3 text-sm text-slate-500">Nothing imported yet.</p>}
      </div>
    </>
  );
}
