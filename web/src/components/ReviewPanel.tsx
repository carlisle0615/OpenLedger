import React from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";

interface ReviewPanelProps {
    statusNeedsReview: boolean;
    reviewPendingCount: number;
    reviewEditsCount: number;
    reviewRowsCount: number;
    runId: string;
    busy: boolean;
    loadReview: () => void;
    openReview: () => void;
}

export function ReviewPanel({
    statusNeedsReview, reviewPendingCount, reviewEditsCount, reviewRowsCount,
    runId, busy, loadReview, openReview,
}: ReviewPanelProps) {
    return (
        <Card className={cn(statusNeedsReview ? "border-[hsl(var(--warning))]/60 bg-[hsl(var(--warning))]/5" : "")}>
            <CardHeader className="py-2">
                <CardTitle className="text-base flex items-center gap-2">
                    <AlertCircle className={cn("h-4 w-4", statusNeedsReview ? "text-[hsl(var(--warning))]" : "text-muted-foreground")} />
                    人工复核
                    {statusNeedsReview ? (
                        <Badge variant="secondary" className="text-[10px]">
                            需复核
                        </Badge>
                    ) : null}
                </CardTitle>
            </CardHeader>
            <CardContent className="py-2 space-y-1">
                <div className="flex flex-wrap items-center gap-2">
                    <Button size="sm" variant="outline" onClick={() => void loadReview()} disabled={!runId || busy}>
                        加载
                    </Button>
                    <Button size="sm" onClick={() => void openReview()} disabled={!runId || busy}>
                        打开
                    </Button>
                    <Badge variant="outline" className="h-6 text-[10px] font-mono">
                        待复核 {reviewPendingCount}
                    </Badge>
                    <Badge variant="outline" className="h-6 text-[10px] font-mono">
                        已编辑 {reviewEditsCount}
                    </Badge>
                    <Badge variant="outline" className="h-6 text-[10px] font-mono">
                        已加载 {reviewRowsCount}
                    </Badge>
                </div>
                <div className="text-[10px] text-muted-foreground leading-tight">
                    在弹窗里查看完整字段、批量应用规则，并保存到 <span className="font-mono">review.csv</span>。
                </div>
            </CardContent>
        </Card>
    );
}
