import React from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import {
    Collapsible, CollapsibleContent, CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Clock } from "lucide-react";

interface ConfigPanelProps {
    configText: string;
    setConfigText: (v: string) => void;
    cfgSaveToRun: boolean;
    setCfgSaveToRun: (v: boolean) => void;
    cfgSaveToGlobal: boolean;
    setCfgSaveToGlobal: (v: boolean) => void;
    saveConfig: () => void;
}

export function ConfigPanel({
    configText, setConfigText,
    cfgSaveToRun, setCfgSaveToRun,
    cfgSaveToGlobal, setCfgSaveToGlobal,
    saveConfig,
}: ConfigPanelProps) {
    return (
        <Collapsible>
            <CollapsibleTrigger asChild>
                <Button variant="outline" size="sm" className="w-full justify-between">
                    高级：分类器配置
                    <Clock className="h-3 w-3 opacity-50" />
                </Button>
            </CollapsibleTrigger>
            <CollapsibleContent className="mt-2">
                <Card>
                    <CardContent className="p-2">
                        <textarea
                            className="w-full min-h-[200px] p-2 rounded-md border bg-muted/50 font-mono text-xs focus:outline-none"
                            value={configText}
                            onChange={(e) => setConfigText(e.target.value)}
                        />
                        <div className="flex flex-wrap items-center gap-4 mt-2">
                            <div className="flex items-center gap-2">
                                <Checkbox
                                    id="cfg_save_run"
                                    checked={cfgSaveToRun}
                                    onCheckedChange={(chk: boolean | string) => setCfgSaveToRun(chk === true)}
                                />
                                <label
                                    htmlFor="cfg_save_run"
                                    className="text-xs leading-none text-muted-foreground"
                                    title="写入当前任务 runs/<run_id>/config/classifier.json（只影响本任务的重跑）"
                                >
                                    保存到本次任务
                                </label>
                            </div>
                            <div className="flex items-center gap-2">
                                <Checkbox
                                    id="cfg_save_global"
                                    checked={cfgSaveToGlobal}
                                    onCheckedChange={(chk: boolean | string) => setCfgSaveToGlobal(chk === true)}
                                />
                                <label
                                    htmlFor="cfg_save_global"
                                    className="text-xs leading-none text-muted-foreground"
                                    title="写入全局 config/classifier.local.json（本地覆盖，避免误提交；影响后续新建任务）"
                                >
                                    保存为默认（永久）
                                </label>
                            </div>
                        </div>
                        <Button size="sm" onClick={saveConfig} className="mt-2 w-full">
                            保存配置
                        </Button>
                    </CardContent>
                </Card>
            </CollapsibleContent>
        </Collapsible>
    );
}
