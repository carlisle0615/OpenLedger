import { useState, useEffect, useCallback } from "react";

/** 应用支持的视图类型 */
export type ActiveView = "workspace" | "profiles" | "capabilities" | "config";

/** hash 值与视图的映射 */
const VALID_VIEWS: ReadonlySet<string> = new Set<ActiveView>([
    "workspace",
    "profiles",
    "capabilities",
    "config",
]);

/** 从 location.hash 解析出当前视图，不合法时返回 workspace */
function parseHash(): ActiveView {
    // hash 形如 "#/profiles" → 去掉 "#/" 前缀
    const raw = window.location.hash.replace(/^#\/?/, "").toLowerCase();
    return VALID_VIEWS.has(raw) ? (raw as ActiveView) : "workspace";
}

/**
 * 基于 hash 路由的视图状态 hook。
 * 将 activeView 与 URL hash 双向同步：
 *   - 切换视图 → 更新 URL hash
 *   - 浏览器前进/后退 / 手动改 hash → 更新视图 state
 *   - 刷新页面 → 从 hash 恢复视图
 */
export function useHashRoute(): [ActiveView, (v: ActiveView) => void] {
    const [view, setViewState] = useState<ActiveView>(parseHash);

    // state → URL
    const setView = useCallback((v: ActiveView) => {
        setViewState(v);
        const target = v === "workspace" ? "/" : `/${v}`;
        if (window.location.hash !== `#${target}`) {
            window.location.hash = target;
        }
    }, []);

    // URL → state（浏览器前进/后退 & 手动改 hash）
    useEffect(() => {
        const onHashChange = () => {
            setViewState(parseHash());
        };
        window.addEventListener("hashchange", onHashChange);
        return () => window.removeEventListener("hashchange", onHashChange);
    }, []);

    return [view, setView];
}
