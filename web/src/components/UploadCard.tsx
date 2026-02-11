import React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { RunState } from "@/types";

interface UploadCardProps {
    state: RunState | null;
    runId: string;
    busy: boolean;
    onUpload: (files: FileList | null) => void;
}

export function UploadCard({ state, runId, busy, onUpload }: UploadCardProps) {
    return (
        <Card>
            <CardHeader className="py-3">
                <CardTitle className="text-base">上传</CardTitle>
            </CardHeader>
            <CardContent className="py-3">
                <div className="flex items-center gap-2">
                    <Input
                        type="file"
                        multiple
                        onChange={(e) => onUpload(e.target.files)}
                        disabled={!runId || busy}
                        className="flex-1 cursor-pointer text-xs h-8"
                    />
                </div>
                {state?.inputs?.length ? (
                    <div className="mt-2 text-xs text-muted-foreground">
                        已上传 {state.inputs.length} 个文件
                    </div>
                ) : null}
            </CardContent>
        </Card>
    );
}
