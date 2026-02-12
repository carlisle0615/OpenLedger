import React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { RunState, ProfileListItem } from "@/types";
import { AlertCircle, User, ArrowRight } from "lucide-react";

interface UploadCardProps {
    state: RunState | null;
    runId: string;
    busy: boolean;
    onUpload: (files: FileList | null) => void;
    boundProfileId: string;
    selectedProfileId: string;
    profiles: ProfileListItem[];
}

export function UploadCard({
    state, runId, busy, onUpload,
    boundProfileId, selectedProfileId, profiles
}: UploadCardProps) {
    const uploadedCount = state?.inputs?.length ?? 0;
    const boundProfile = profiles.find((p) => p.id === boundProfileId);
    const selectedProfile = profiles.find((p) => p.id === selectedProfileId);
    return (
        <Card>
            <CardHeader className="py-3 flex flex-row items-center justify-between">
                <CardTitle className="text-base">上传/追加上传</CardTitle>
                {boundProfile ? (
                    <div className="flex items-center gap-1.5 text-xs text-muted-foreground bg-muted/50 px-2 py-1 rounded">
                        <User className="h-3 w-3" />
                        <span>当前任务归属用户: </span>
                        <span className="font-medium text-foreground">{boundProfile.name}</span>
                    </div>
                ) : selectedProfile ? (
                    <div className="flex items-center gap-1.5 text-xs text-amber-600 dark:text-amber-500 bg-amber-50 dark:bg-amber-950/30 px-2 py-1 rounded border border-amber-200 dark:border-amber-900/50">
                        <AlertCircle className="h-3 w-3" />
                        <span>已选择用户 {selectedProfile.name}，但当前任务未绑定</span>
                    </div>
                ) : (
                    <div className="flex items-center gap-1.5 text-xs text-amber-600 dark:text-amber-500 bg-amber-50 dark:bg-amber-950/30 px-2 py-1 rounded border border-amber-200 dark:border-amber-900/50">
                        <AlertCircle className="h-3 w-3" />
                        <span>未指定归属用户</span>
                    </div>
                )}
            </CardHeader>
            <CardContent className="py-3 space-y-3">
                <div className="flex items-center gap-2">
                    <Input
                        type="file"
                        multiple
                        onChange={(e) => onUpload(e.target.files)}
                        disabled={!runId || busy}
                        className="flex-1 cursor-pointer text-xs h-8"
                    />
                </div>

                {!boundProfile && (
                    <div className="text-xs text-amber-600 dark:text-amber-500 flex items-center gap-2">
                        <ArrowRight className="h-3 w-3" />
                        <span>先在“用户”页执行“绑定当前任务到该用户”，即可自动归档。</span>
                    </div>
                )}
                <div className="text-[11px] text-muted-foreground">
                    归属用户用于归档到 SQLite 档案；归属年月可在“用户”页手动指定（也可留空）。
                </div>
                {!runId ? (
                    <div className="mt-2 text-xs text-muted-foreground">
                        请先在顶部选择或新建任务，再上传文件。
                    </div>
                ) : uploadedCount > 0 ? (
                    <div className="mt-2 text-xs text-muted-foreground">
                        已上传 {uploadedCount} 个文件，可继续追加。
                    </div>
                ) : (
                    <div className="mt-2 text-xs text-muted-foreground">
                        支持多选上传 PDF/CSV/XLSX。
                    </div>
                )}
            </CardContent>
        </Card>
    );
}
