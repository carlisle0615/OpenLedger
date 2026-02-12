import React from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
    Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { AlertCircle, Play, RefreshCw, Settings, Plus, CheckCircle2, CloudLightning } from "lucide-react";
import { type RunMeta } from "@/utils/helpers";
import { SettingsDialog } from "@/components/SettingsDialog";
import {
    Popover,
    PopoverContent,
    PopoverTrigger,
} from "@/components/ui/popover";
import { Label } from "@/components/ui/label";
import { ProfileListItem } from "@/types";
import { ProfileSelector } from "@/components/ProfileSelector";

interface HeaderBarProps {
    baseUrl: string;
    setBaseUrl: (v: string) => void;
    backendStatus: "idle" | "checking" | "ok" | "error";
    backendError: string;
    runs: string[];
    runId: string;
    setRunId: (v: string) => void;
    runsMeta: RunMeta[];
    newRunName: string;
    setNewRunName: (v: string) => void;
    busy: boolean;
    runStatus: { text: string; variant: string; icon: React.ComponentType<any> } | null;
    runName: string;
    refreshRuns: () => Promise<any>;
    onCreateRun: (name: string) => Promise<void>;
    activeView: "workspace" | "profiles" | "capabilities" | "config";
    setActiveView: (v: "workspace" | "profiles" | "capabilities" | "config") => void;
    profiles: ProfileListItem[];
    currentProfileId: string;
    onSelectProfile: (id: string) => void;
    onCreateProfile: (name: string) => void;
    profileSelectorDisabled?: boolean;
}

export function HeaderBar({
    baseUrl, setBaseUrl,
    backendStatus, backendError,
    runs, runId, setRunId, runsMeta, newRunName, setNewRunName,
    busy, runStatus, runName,
    refreshRuns, onCreateRun,
    activeView, setActiveView,
    profiles, currentProfileId, onSelectProfile, onCreateProfile,
    profileSelectorDisabled = false,
}: HeaderBarProps) {
    const [settingsOpen, setSettingsOpen] = React.useState(false);
    const [createOpen, setCreateOpen] = React.useState(false);

    const handleCreate = async () => {
        if (!newRunName.trim()) return;
        await onCreateRun(newRunName);
        setCreateOpen(false);
        setNewRunName("");
    };

    return (
        <>
            <div className="flex items-center justify-between h-14 px-4 border-b bg-background sticky top-0 z-50">
                <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2">
                        <div className="h-6 w-6 rounded bg-primary text-primary-foreground flex items-center justify-center font-bold">
                            LE
                        </div>
                        <h1 className="text-lg font-semibold tracking-tight hidden md:block">OpenLedger</h1>
                    </div>

                    <nav className="flex items-center gap-1">
                        <div className="flex items-center gap-1 rounded-md bg-muted/50 p-1">
                            <Button
                                size="sm"
                                variant={activeView === "workspace" ? "secondary" : "ghost"}
                                className="h-7 px-3 text-xs"
                                onClick={() => setActiveView("workspace")}
                            >
                                工作台
                            </Button>
                            <Button
                                size="sm"
                                variant={activeView === "profiles" ? "secondary" : "ghost"}
                                className="h-7 px-3 text-xs"
                                onClick={() => setActiveView("profiles")}
                            >
                                用户
                            </Button>
                            <Button
                                size="sm"
                                variant={activeView === "capabilities" ? "secondary" : "ghost"}
                                className="h-7 px-3 text-xs"
                                onClick={() => setActiveView("capabilities")}
                            >
                                能力
                            </Button>
                            <Button
                                size="sm"
                                variant={activeView === "config" ? "secondary" : "ghost"}
                                className="h-7 px-3 text-xs"
                                onClick={() => setActiveView("config")}
                            >
                                配置中心
                            </Button>
                        </div>
                    </nav>
                </div>

                <div className="flex items-center gap-2">
                    {/* Profile Selector */}
                    <ProfileSelector
                        profiles={profiles}
                        currentProfileId={currentProfileId}
                        onSelect={onSelectProfile}
                        onCreate={onCreateProfile}
                        disabled={busy || profileSelectorDisabled}
                    />
                    <Separator orientation="vertical" className="h-6 mx-2" />

                    {/* Run Selector */}
                    <div className="flex items-center gap-2">
                        <Select value={runId} onValueChange={setRunId}>
                            <SelectTrigger className="w-[300px] h-8 text-xs bg-muted/30 border-dashed" title={runId || "未选择任务"}>
                                <SelectValue placeholder="选择任务" />
                            </SelectTrigger>
                            <SelectContent>
                                {runs.map((r) => (
                                    <SelectItem key={r} value={r} className="text-xs" title={r}>
                                        <div className="flex items-center gap-2">
                                            <span className="font-mono text-xs truncate max-w-[180px]" title={r}>{r}</span>
                                            {(() => {
                                                const name = String(runsMeta.find((m) => m.id === r)?.name ?? "").trim();
                                                return name ? <span className="text-muted-foreground truncate max-w-[120px]" title={name}>{name}</span> : null;
                                            })()}
                                        </div>
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>

                        <Popover open={createOpen} onOpenChange={setCreateOpen}>
                            <PopoverTrigger asChild>
                                <Button variant="ghost" size="icon" className="h-8 w-8" title="新建任务">
                                    <Plus className="h-4 w-4" />
                                </Button>
                            </PopoverTrigger>
                            <PopoverContent className="w-80" align="end">
                                <div className="grid gap-4">
                                    <div className="space-y-2">
                                        <h4 className="font-medium leading-none">新建任务</h4>
                                        <p className="text-sm text-muted-foreground">
                                            输任务名称开始新的流程。
                                        </p>
                                    </div>
                                    <div className="grid gap-2">
                                        <Label htmlFor="new-run-name">名称</Label>
                                        <Input
                                            id="new-run-name"
                                            value={newRunName}
                                            onChange={(e) => setNewRunName(e.target.value)}
                                            className="h-8"
                                        />
                                    </div>
                                    <div className="flex justify-end">
                                        <Button size="sm" onClick={handleCreate} disabled={busy || !newRunName.trim()}>
                                            创建并开始
                                        </Button>
                                    </div>
                                </div>
                            </PopoverContent>
                        </Popover>
                    </div>

                    <Separator orientation="vertical" className="h-6 mx-2" />

                    {/* Status & Actions */}
                    <div className="flex items-center gap-1">
                        {runStatus && (
                            <Badge variant={runStatus.variant as any} className="gap-1 px-2 h-7 font-normal">
                                {runStatus.icon && <runStatus.icon className="h-3.5 w-3.5" />}
                                <span className="hidden sm:inline-block">{runStatus.text}</span>
                            </Badge>
                        )}

                        <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8 text-muted-foreground"
                            onClick={() => setSettingsOpen(true)}
                            title="设置"
                        >
                            <Settings className="h-4 w-4" />
                            {backendStatus === "error" && (
                                <span className="absolute top-1.5 right-1.5 h-2 w-2 rounded-full bg-destructive" />
                            )}
                        </Button>
                    </div>


                    {!runId && (
                        <div className="hidden lg:flex items-center gap-2 text-xs text-muted-foreground bg-muted/30 px-2 py-1 rounded border border-dashed ml-2">
                            <AlertCircle className="h-3 w-3" />
                            <span>请先配置后端并选择任务</span>
                        </div>
                    )}
                </div>
            </div>

            <SettingsDialog
                open={settingsOpen}
                onOpenChange={setSettingsOpen}
                baseUrl={baseUrl}
                setBaseUrl={setBaseUrl}
                backendStatus={backendStatus}
                backendError={backendError}
                refreshRuns={refreshRuns}
                busy={busy}
            />
        </>
    );
}
