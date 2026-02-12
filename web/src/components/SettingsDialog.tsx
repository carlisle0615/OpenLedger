import React from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { RefreshCw, CheckCircle2, XCircle, AlertCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";

interface SettingsDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    baseUrl: string;
    setBaseUrl: (url: string) => void;
    backendStatus: "idle" | "checking" | "ok" | "error";
    backendError: string;
    refreshRuns: () => Promise<any>;
    busy: boolean;
}

export function SettingsDialog({
    open,
    onOpenChange,
    baseUrl,
    setBaseUrl,
    backendStatus,
    backendError,
    refreshRuns,
    busy,
}: SettingsDialogProps) {
    const [localUrl, setLocalUrl] = React.useState(baseUrl);

    // Sync local state when prop changes, or when dialog opens
    React.useEffect(() => {
        if (open) setLocalUrl(baseUrl);
    }, [open, baseUrl]);

    const handleSave = () => {
        setBaseUrl(localUrl);
        // Trigger a check immediately
        setTimeout(() => {
            refreshRuns().catch(() => { });
        }, 100);
    };

    const statusIcon =
        backendStatus === "ok" ? (
            <CheckCircle2 className="h-4 w-4 text-green-500" />
        ) : backendStatus === "error" ? (
            <XCircle className="h-4 w-4 text-destructive" />
        ) : backendStatus === "checking" ? (
            <RefreshCw className="h-4 w-4 animate-spin text-muted-foreground" />
        ) : (
            <AlertCircle className="h-4 w-4 text-muted-foreground" />
        );

    const statusText =
        backendStatus === "ok"
            ? "已连接"
            : backendStatus === "error"
                ? "连接失败"
                : backendStatus === "checking"
                    ? "连接中..."
                    : "未检测";

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-[425px]">
                <DialogHeader>
                    <DialogTitle>设置</DialogTitle>
                    <DialogDescription>
                        配置后端服务连接地址。
                    </DialogDescription>
                </DialogHeader>
                <div className="grid gap-4 py-4">
                    <div className="grid grid-cols-4 items-center gap-4">
                        <Label htmlFor="backend-url" className="text-right">
                            后端地址
                        </Label>
                        <Input
                            id="backend-url"
                            value={localUrl}
                            onChange={(e) => setLocalUrl(e.target.value)}
                            className="col-span-3 font-mono text-sm"
                        />
                    </div>
                    <div className="grid grid-cols-4 items-center gap-4">
                        <div className="text-right text-sm font-medium">状态</div>
                        <div className="col-span-3 flex items-center gap-2">
                            {statusIcon}
                            <span className="text-sm text-muted-foreground">{statusText}</span>
                            {backendStatus === "error" && (
                                <span className="text-xs text-destructive truncate max-w-[180px]" title={backendError}>
                                    {backendError}
                                </span>
                            )}
                        </div>
                    </div>
                </div>
                <DialogFooter>
                    <Button variant="secondary" onClick={() => refreshRuns()} disabled={busy || backendStatus === "checking"}>
                        测试连接
                    </Button>
                    <Button onClick={handleSave}>保存</Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
