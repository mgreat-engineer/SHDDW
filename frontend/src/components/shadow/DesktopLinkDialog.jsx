import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Laptop } from "lucide-react";
import { useApi, errMsg } from "@/lib/api";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";

// Asks to link the Shadow desktop app that opened this window to your account.
export default function DesktopLinkDialog({ onLinked }) {
  const api = useApi();
  const [req, setReq] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const id = sessionStorage.getItem("shadow-link");
    if (!id) return;
    api.get(`/helper/link/${id}`).then((r) => (r.data.approved ? sessionStorage.removeItem("shadow-link") : setReq(r.data)))
      .catch((e) => { sessionStorage.removeItem("shadow-link"); toast.error(errMsg(e)); });
  }, [api]);
  const close = () => { sessionStorage.removeItem("shadow-link"); setReq(null); };
  const approve = async () => {
    setBusy(true);
    try {
      await api.post(`/helper/link/${req.id}/approve`);
      toast.success("This computer is linked — Shadow will work here in a few seconds");
      close();
      onLinked?.();
    } catch (e) { toast.error(errMsg(e)); close(); }
    setBusy(false);
  };
  return (
    <AlertDialog open={!!req} onOpenChange={(o) => !o && close()}>
      <AlertDialogContent data-testid="desktop-link-dialog">
        <AlertDialogHeader>
          <AlertDialogTitle className="flex items-center gap-2"><Laptop className="h-5 w-5 text-[#1A73E8]" />Link this computer?</AlertDialogTitle>
          <AlertDialogDescription>
            The Shadow app on <b data-testid="desktop-link-name">{req?.name}</b> will run your tasks in Chrome on that computer, using its internet and only the folders you allow. Only link it if you just opened the Shadow app yourself.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel data-testid="desktop-link-cancel">Not now</AlertDialogCancel>
          <AlertDialogAction onClick={approve} disabled={busy} data-testid="desktop-link-approve" className="bg-[#1A73E8] hover:bg-[#1765CC]">Link computer</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
