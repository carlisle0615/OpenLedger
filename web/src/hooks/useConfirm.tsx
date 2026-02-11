import React, { useCallback, useRef, useState } from "react";
import { ConfirmDialog, type ConfirmDialogProps } from "@/components/ConfirmDialog";

export type ConfirmOptions = Pick<
  ConfirmDialogProps,
  "title" | "description" | "confirmText" | "cancelText" | "tone"
>;

export function useConfirm() {
  const [options, setOptions] = useState<ConfirmOptions | null>(null);
  const resolverRef = useRef<((value: boolean) => void) | null>(null);

  const confirm = useCallback((opts: ConfirmOptions) => {
    setOptions(opts);
    return new Promise<boolean>((resolve) => {
      resolverRef.current = resolve;
    });
  }, []);

  const handleClose = useCallback((result: boolean) => {
    setOptions(null);
    const resolve = resolverRef.current;
    resolverRef.current = null;
    if (resolve) resolve(result);
  }, []);

  const dialog = options ? (
    <ConfirmDialog
      open={Boolean(options)}
      title={options.title}
      description={options.description}
      confirmText={options.confirmText}
      cancelText={options.cancelText}
      tone={options.tone}
      onConfirm={() => handleClose(true)}
      onCancel={() => handleClose(false)}
    />
  ) : null;

  return { confirm, dialog };
}
