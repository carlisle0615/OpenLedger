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
                <ScrollArea ref={tabsRef} className="whitespace-nowrap">
                    <TabsList className="inline-flex h-auto w-max min-w-full items-center justify-start gap-0 rounded-none bg-transparent p-0">
                        {state.stages.map((st, idx) => {
                            const isActive = displayStageId === st.id;
                            const isDone = st.status === "succeeded";
                            const isRunning = st.status === "running";
                            const isFailed = st.status === "failed";
                            const needsReview = st.status === "needs_review";
                            const connectorActive = isDone || isRunning;
                            const circleClass = cn(
                                "mr-2 inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full border text-[10px] transition-colors",
                                isDone && "border-green-600 bg-green-100 text-green-700",
                                isRunning && "border-blue-600 bg-blue-100 text-blue-700 animate-pulse",
                                isFailed && "border-red-600 bg-red-100 text-red-700",
                                needsReview && "border-amber-600 bg-amber-100 text-amber-700",
                                !isDone && !isRunning && !isFailed && !needsReview && isActive && "border-primary bg-primary text-primary-foreground",
                                !isDone && !isRunning && !isFailed && !needsReview && !isActive && "border-muted-foreground/30 bg-muted/30 text-muted-foreground"
                            );
                            const labelClass = cn(
                                "max-w-[140px] truncate text-xs font-medium transition-colors",
                                isActive ? "text-foreground" : "text-muted-foreground",
                            );

                            return (
                                <React.Fragment key={st.id}>
                                    <TabsTrigger
                                        value={st.id}
                                        data-stage-id={st.id}
                                        className={cn(
                                            "h-9 min-w-fit shrink-0 rounded-sm px-3 mx-1 data-[state=active]:bg-accent data-[state=active]:text-accent-foreground shadow-none hover:bg-muted/50 transition-all",
                                        )}
                                    >
                                        <div className="flex items-center">
                                            <span className={circleClass}>
                                                {isDone && <Check className="h-2.5 w-2.5" />}
                                                {isRunning && <Loader2 className="h-2.5 w-2.5 animate-spin" />}
                                                {isFailed && <X className="h-2.5 w-2.5" />}
                                                {needsReview && <AlertCircle className="h-2.5 w-2.5" />}
                                                {!isDone && !isRunning && !isFailed && !needsReview && (idx + 1)}
                                            </span>
                                            <span className={labelClass} title={st.name}>{st.name}</span>
                                        </div>
                                    </TabsTrigger>
                                    {idx < state.stages.length - 1 && (
                                        <span
                                            aria-hidden
                                            className={cn(
                                                "mx-1 h-px w-4 shrink-0 bg-border/50",
                                                connectorActive && "bg-muted-foreground/40"
                                            )}
                                        />
                                    )}
                                </React.Fragment>
                            )
                        })}
                    </TabsList>
                    <ScrollBar orientation="horizontal" className="invisible" />
                </ScrollArea>
            </Tabs>
        </div>
    );
}
