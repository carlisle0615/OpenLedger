import React from "react";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import { RunState } from "@/types";
import {
    Check, Loader2, X, AlertCircle
} from "lucide-react";

interface WorkflowTimelineProps {
    state: RunState | null;
    selectedStageId: string;
    setSelectedStageId: (id: string) => void;
    className?: string;
}

export function WorkflowTimeline({
    state, selectedStageId, setSelectedStageId, className
}: WorkflowTimelineProps) {
    const tabsRef = React.useRef<HTMLDivElement | null>(null);
    // Default to first stage or selected
    const displayStageId = selectedStageId || state?.stages?.[0]?.id || "";

    React.useEffect(() => {
        if (!displayStageId) return;
        const root = tabsRef.current;
        if (!root) return;
        const esc = (v: string) => (typeof CSS !== "undefined" && CSS.escape ? CSS.escape(v) : v.replace(/"/g, '\\"'));
        const el = root.querySelector(`[data-stage-id="${esc(displayStageId)}"]`) as HTMLElement | null;
        if (!el) return;
        // Scroll into view logic
        el.scrollIntoView({ block: "nearest", inline: "center" });
    }, [displayStageId, state?.stages?.length]);

    if (!state?.stages?.length) return null;

    return (
        <div className={cn("w-full", className)}>
            <Tabs
                value={displayStageId}
                onValueChange={setSelectedStageId}
            >
                <ScrollArea ref={tabsRef} className="whitespace-nowrap rounded-md border bg-card">
                    <TabsList className="inline-flex h-auto w-max min-w-full items-center justify-start gap-0 rounded-none bg-transparent px-2 py-2">
                        {state.stages.map((st, idx) => {
                            const isActive = displayStageId === st.id;
                            const isDone = st.status === "succeeded";
                            const isRunning = st.status === "running";
                            const isFailed = st.status === "failed";
                            const needsReview = st.status === "needs_review";
                            const connectorActive = isDone || isRunning;
                            const circleClass = cn(
                                "mr-1.5 inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full border transition-colors",
                                isDone && "border-foreground bg-foreground text-background",
                                isRunning && "border-primary bg-primary text-primary-foreground",
                                isFailed && "border-destructive bg-destructive text-destructive-foreground",
                                needsReview && "border-[hsl(var(--warning))] bg-[hsl(var(--warning))] text-[hsl(var(--warning-foreground))]",
                                !isDone && !isRunning && !isFailed && !needsReview && isActive && "border-foreground bg-background text-foreground",
                                !isDone && !isRunning && !isFailed && !needsReview && !isActive && "border-muted-foreground/30 bg-background text-muted-foreground/30"
                            );
                            const labelClass = cn(
                                "max-w-[140px] truncate text-xs",
                                isActive ? "text-foreground" : "text-muted-foreground",
                                isDone && "text-foreground"
                            );

                            return (
                                <React.Fragment key={st.id}>
                                    <TabsTrigger
                                        value={st.id}
                                        data-stage-id={st.id}
                                        className={cn(
                                            "h-auto min-w-fit shrink-0 rounded-none bg-transparent p-0 text-left shadow-none hover:text-foreground",
                                            "data-[state=active]:bg-transparent data-[state=active]:shadow-none focus-visible:ring-0"
                                        )}
                                    >
                                        <div className="flex items-center px-1 py-1">
                                            <span className={circleClass}>
                                                {isDone && <Check className="h-2.5 w-2.5" />}
                                                {isRunning && <Loader2 className="h-2.5 w-2.5 animate-spin" />}
                                                {isFailed && <X className="h-2.5 w-2.5" />}
                                                {needsReview && <AlertCircle className="h-2.5 w-2.5" />}
                                            </span>
                                            <span className={labelClass} title={st.name}>{st.name}</span>
                                        </div>
                                    </TabsTrigger>
                                    {idx < state.stages.length - 1 && (
                                        <span
                                            aria-hidden
                                            className={cn(
                                                "mx-2 h-px w-8 shrink-0",
                                                connectorActive ? "bg-muted-foreground" : "bg-border"
                                            )}
                                        />
                                    )}
                                </React.Fragment>
                            )
                        })}
                    </TabsList>
                    <ScrollBar orientation="horizontal" />
                </ScrollArea>
            </Tabs>
        </div>
    );
}
