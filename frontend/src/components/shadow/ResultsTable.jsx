import { useState } from "react";
import { FileSpreadsheet, Maximize2 } from "lucide-react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useApi, errMsg, saveBlob } from "@/lib/api";

function Grid({ table, max, testId }) {
  const rows = max ? table.rows.slice(-max) : table.rows;
  return (
    <div className="overflow-auto thin-scroll rounded-md border border-[#262B3D]" data-testid={testId}>
      <table className="w-full text-[11px]">
        <thead className="bg-[#181B26] sticky top-0">
          <tr>{table.columns.map((c) => <th key={c} className="text-left font-mono font-medium text-slate-400 px-2 py-1.5 whitespace-nowrap">{c}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-t border-[#262B3D]/60 fade-up">
              {table.columns.map((c) => <td key={c} className="px-2 py-1 text-slate-200 whitespace-nowrap max-w-[220px] truncate" title={r[c]}>{r[c]}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function ResultsTable({ run }) {
  const api = useApi();
  const [tab, setTab] = useState(0);
  const [open, setOpen] = useState(false);
  const tables = run.tables || [];
  if (!tables.length) return null;
  const t = tables[Math.min(tab, tables.length - 1)];
  const exportXlsx = () => saveBlob(api, `/runs/${run.id}/export`, `shadow-results-${run.created_at.slice(0, 10)}.xlsx`).catch((e) => toast.error(errMsg(e)));
  const exportBtn = (
    <button onClick={exportXlsx} data-testid="results-export-button" className="flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-md bg-[#00E676]/15 text-[#00E676] hover:bg-[#00E676]/25 transition-colors">
      <FileSpreadsheet className="h-3.5 w-3.5" />Export to Excel
    </button>
  );
  return (
    <div data-testid="results-section">
      <div className="flex items-center justify-between mb-2">
        <p className="text-[10px] font-mono uppercase tracking-widest text-slate-500">Results · {t.row_count} rows{run.status === "running" ? " · live" : ""}</p>
        <div className="flex gap-1.5">
          <button onClick={() => setOpen(true)} data-testid="results-expand-button" className="p-1 rounded text-slate-400 hover:text-slate-100" title="Open table"><Maximize2 className="h-3.5 w-3.5" /></button>
          {exportBtn}
        </div>
      </div>
      {tables.length > 1 && (
        <div className="flex gap-1 mb-2 overflow-x-auto thin-scroll">
          {tables.map((x, i) => <button key={x.name} onClick={() => setTab(i)} data-testid={`results-tab-${i}`} className={`text-[11px] px-2 py-0.5 rounded ${i === tab ? "bg-[#00F0FF]/15 text-[#00F0FF]" : "text-slate-400"}`}>{x.name}</button>)}
        </div>
      )}
      <div className="max-h-48 overflow-hidden"><Grid table={t} max={8} testId="results-mini-table" /></div>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="bg-[#12141C] border-[#262B3D] max-w-5xl" data-testid="results-dialog">
          <DialogHeader><DialogTitle className="font-display flex items-center justify-between pr-8"><span>{t.name} · {t.row_count} rows</span>{exportBtn}</DialogTitle></DialogHeader>
          <div className="max-h-[65vh] overflow-auto thin-scroll"><Grid table={t} testId="results-full-table" /></div>
          {t.row_count > t.rows.length && <p className="text-[11px] text-slate-500">Showing the latest {t.rows.length} rows — the Excel file has all {t.row_count}.</p>}
        </DialogContent>
      </Dialog>
    </div>
  );
}
