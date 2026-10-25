import { createContext, useContext } from "react";
import type { ReactNode } from "react";
import { Button } from "./components/ui/button";
import { Info, Plus } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "./components/ui/dialog";

export const UnavailableContext = createContext<() => void>(() => {});
export function UnavailableButton({
  children = "更多",
  className = "action",
}: {
  children?: ReactNode;
  className?: string;
}) {
  const notify = useContext(UnavailableContext);
  return (
    <Button type="button" className={className} onClick={notify}>
      {children}
    </Button>
  );
}
export function PageHeading({
  title,
  subtitle,
  action,
}: {
  title: string;
  subtitle: string;
  action?: ReactNode;
}) {
  return (
    <section className="page-heading">
      <div>
        <div className="eyebrow">BUMBUM OPERATIONS</div>
        <h1 className="page-title">{title}</h1>
        <p className="page-subtitle">{subtitle}</p>
      </div>
      {action}
    </section>
  );
}
export function Notice({
  children,
  error = false,
}: {
  children: ReactNode;
  error?: boolean;
}) {
  return (
    <div
      role={error ? "alert" : "status"}
      className={`feedback ${error ? "feedback-danger" : "feedback-success"}`}
    >
      <Info size={18} />
      <div>{children}</div>
    </div>
  );
}
export function EntryDialog({
  open,
  title,
  description,
  onChange,
  children,
}: {
  open: boolean;
  title: string;
  description: string;
  onChange: (open: boolean) => void;
  children: ReactNode;
}) {
  return (
    <Dialog open={open} onOpenChange={onChange}>
      <DialogContent>
        <DialogHeader>
          <span className="modal-icon">
            <Plus />
          </span>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        {children}
      </DialogContent>
    </Dialog>
  );
}
