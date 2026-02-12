import React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export type ConfirmTone = "default" | "danger";

export interface ConfirmDialogProps {
  open: boolean;
  title: string;
  description?: React.ReactNode;
  confirmText?: string;
  cancelText?: string;
  extraText?: string;
  tone?: ConfirmTone;
  onConfirm: () => void;
  onCancel: () => void;
  onExtra?: () => void;
}

export function ConfirmDialog({
  open,
  title,
  description,
  confirmText = "确认",
  cancelText = "取消",
  extraText,
  tone = "default",
  onConfirm,
  onCancel,
  onExtra,
}: ConfirmDialogProps) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <Card className={cn("w-full max-w-md shadow-lg")}> 
        <CardHeader className="pb-2">
          <CardTitle className="text-base">{title}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {description ? (
            <div className="text-sm text-muted-foreground">{description}</div>
          ) : null}
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={onCancel}>
              {cancelText}
            </Button>
            {extraText && onExtra ? (
              <Button variant="secondary" onClick={onExtra}>
                {extraText}
              </Button>
            ) : null}
            <Button variant={tone === "danger" ? "destructive" : "default"} onClick={onConfirm}>
              {confirmText}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
