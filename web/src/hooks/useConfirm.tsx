import React, { useCallback, useRef, useState } from "react";
import { ConfirmDialog, type ConfirmDialogProps } from "@/components/ConfirmDialog";

export type ConfirmOptions = Pick<
  ConfirmDialogProps,
  "title" | "description" | "confirmText" | "cancelText" | "tone"
>;

export type ConfirmChoice = "confirm" | "cancel" | "extra";
export type ConfirmChoiceOptions = ConfirmOptions & { extraText: string };

type ConfirmDialogState =
  | { mode: "boolean"; options: ConfirmOptions }
  | { mode: "choice"; options: ConfirmChoiceOptions };

export function useConfirm() {
  const [dialogState, setDialogState] = useState<ConfirmDialogState | null>(null);
  const boolResolverRef = useRef<((value: boolean) => void) | null>(null);
  const choiceResolverRef = useRef<((value: ConfirmChoice) => void) | null>(null);

  const confirm = useCallback((opts: ConfirmOptions) => {
    setDialogState({ mode: "boolean", options: opts });
    return new Promise<boolean>((resolve) => {
      boolResolverRef.current = resolve;
      choiceResolverRef.current = null;
    });
  }, []);

  const confirmChoice = useCallback((opts: ConfirmChoiceOptions) => {
    setDialogState({ mode: "choice", options: opts });
    return new Promise<ConfirmChoice>((resolve) => {
      choiceResolverRef.current = resolve;
      boolResolverRef.current = null;
    });
  }, []);

  const handleClose = useCallback((result: ConfirmChoice) => {
    const mode = dialogState?.mode;
    setDialogState(null);

    if (mode === "choice") {
      const resolve = choiceResolverRef.current;
      choiceResolverRef.current = null;
      boolResolverRef.current = null;
      if (resolve) resolve(result);
      return;
    }

    const resolve = boolResolverRef.current;
    boolResolverRef.current = null;
    choiceResolverRef.current = null;
    if (resolve) resolve(result === "confirm");
  }, [dialogState?.mode]);

  const dialog = dialogState ? (
    <ConfirmDialog
      open={Boolean(dialogState)}
      title={dialogState.options.title}
      description={dialogState.options.description}
      confirmText={dialogState.options.confirmText}
      cancelText={dialogState.options.cancelText}
      tone={dialogState.options.tone}
      extraText={dialogState.mode === "choice" ? dialogState.options.extraText : undefined}
      onConfirm={() => handleClose("confirm")}
      onCancel={() => handleClose("cancel")}
      onExtra={dialogState.mode === "choice" ? () => handleClose("extra") : undefined}
    />
  ) : null;

  return { confirm, confirmChoice, dialog };
}
