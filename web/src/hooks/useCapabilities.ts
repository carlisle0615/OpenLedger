
import { useState, useEffect, useCallback, useRef } from "react";
import { api } from "@/utils/helpers";
import { CapabilitiesPayload, SourceSupportItem, PdfParserHealthItem, PdfParserHealthResponse } from "@/types";

export type ProjectCapabilities = {
    loading: boolean;
    error: string | null;
    sourceMatrix: SourceSupportItem[];
    parserHealth: PdfParserHealthResponse | null;
    lastUpdated: number;
    refresh: () => Promise<void>;
};

export type SourceCoverage = {
    matched: boolean;
    matchedFiles: string[];
    source: SourceSupportItem;
};

export type CapabilitiesCoverage = {
    totalSources: number;
    matchedSources: number;
    missingSources: number;
    matrix: SourceCoverage[];
};

// 增强的通配符匹配：支持 standard glob patterns
// *foo* -> 包含 foo
// *foo -> 以 foo 结尾
// foo* -> 以 foo 开头
// *foo*bar* -> 包含 foo 且此后包含 bar
function matchFilename(filename: string, hint: string): boolean {
    const f = filename.toLowerCase();
    const h = hint.toLowerCase();

    // 将 glob pattern 转换为 regex
    // 1. 转义特殊字符 (除了 *)
    // 2. 将 * 替换为 .*
    const pattern = h.replace(/[.+^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*');
    try {
        const re = new RegExp(`^${pattern}$`);
        return re.test(f);
    } catch (e) {
        console.warn("Invalid glob pattern:", hint);
        return false;
    }
}

export function useCapabilities(baseUrl: string, runState?: { inputs: { name: string }[] } | null): ProjectCapabilities & { coverage: CapabilitiesCoverage | null } {
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [sourceMatrix, setSourceMatrix] = useState<SourceSupportItem[]>([]);
    const [parserHealth, setParserHealth] = useState<PdfParserHealthResponse | null>(null);
    const [lastUpdated, setLastUpdated] = useState(0);
    const mounted = useRef(true);

    useEffect(() => {
        mounted.current = true;
        return () => { mounted.current = false; };
    }, []);

    const fetchAll = useCallback(async () => {
        if (!baseUrl) return;
        setLoading(true);
        setError(null);
        try {
            // 优先尝试聚合接口
            try {
                const res = await api<CapabilitiesPayload>(baseUrl, "/api/v2/capabilities");
                if (mounted.current) {
                    setSourceMatrix(res.source_support_matrix);
                    setParserHealth(res.pdf_parser_health);
                    setLastUpdated(Date.now());
                }
            } catch (e) {
                console.warn("Fetch capabilities aggregate failed, fallback to individual endpoints", e);
                // 降级：分别请求
                // 注意：/api/v2/sources/support 返回 { sources: [...] }
                const [p1, p2] = await Promise.allSettled([
                    api<{ sources: SourceSupportItem[] }>(baseUrl, "/api/v2/sources/support"),
                    api<PdfParserHealthResponse>(baseUrl, "/api/v2/parsers/pdf/health"),
                ]);

                if (mounted.current) {
                    if (p1.status === "fulfilled") {
                        // 修复：处理 { sources: ... } 结构
                        setSourceMatrix(p1.value.sources || []);
                    }
                    if (p2.status === "fulfilled") setParserHealth(p2.value);
                    setLastUpdated(Date.now());

                    if (p1.status === "rejected") throw p1.reason;
                    if (p2.status === "rejected") throw p2.reason;
                }
            }
        } catch (err: any) {
            if (mounted.current) {
                setError(err.message || String(err));
            }
        } finally {
            if (mounted.current) setLoading(false);
        }
    }, [baseUrl]);

    // 初始加载 & 轮询 (30s)
    useEffect(() => {
        fetchAll();
        const timer = setInterval(fetchAll, 30000);
        return () => clearInterval(timer);
    }, [fetchAll]);

    // 计算覆盖率
    const coverage = useCallback((): CapabilitiesCoverage | null => {
        if (!runState || !sourceMatrix.length) return null;

        const files = runState.inputs || [];
        const matrixMatches: SourceCoverage[] = sourceMatrix.map(source => {
            // 1. 检查文件扩展名
            const matchedFiles: string[] = [];

            // source.file_types 如 [".pdf", ".csv"]
            // source.filename_hints 如 ["*信用卡账单*.pdf"]

            const relevantFiles = files.filter(f =>
                source.file_types.some(ext => f.name.toLowerCase().endsWith(ext.toLowerCase()))
            );

            // 如果有 hint，则进一步匹配
            if (source.filename_hints && source.filename_hints.length > 0) {
                for (const f of relevantFiles) {
                    const isHit = source.filename_hints.some(hint => matchFilename(f.name, hint));
                    if (isHit) matchedFiles.push(f.name);
                }
            } else {
                // 没有 hint，只要扩展名对就算
                matchedFiles.push(...relevantFiles.map(f => f.name));
            }

            return {
                matched: matchedFiles.length > 0,
                matchedFiles,
                source,
            };
        });

        return {
            totalSources: matrixMatches.length,
            matchedSources: matrixMatches.filter(m => m.matched).length,
            missingSources: matrixMatches.filter(m => !m.matched).length,
            matrix: matrixMatches,
        };
    }, [runState, sourceMatrix]);

    return {
        loading,
        error,
        sourceMatrix,
        parserHealth,
        lastUpdated,
        refresh: fetchAll,
        coverage: coverage(),
    };
}
