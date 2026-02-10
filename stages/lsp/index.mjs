import { ChatOpenAI } from "@langchain/openai";
import { ChatOllama } from "@langchain/ollama";
import { ChatAlibabaTongyi } from "@langchain/community/chat_models/alibaba_tongyi";
import { ChatMoonshot } from "@langchain/community/chat_models/moonshot";
import { ChatMinimax } from "@langchain/community/chat_models/minimax";
import { ChatDeepSeek } from "@langchain/deepseek";

/**
 * @typedef {"openrouter" | "ollama" | "tongyi" | "deepseek" | "kimi" | "minimax"} LspProviderId
 * LSP 提供方 ID
 */

/**
 * @typedef {Object} LspConfig
 * @property {LspProviderId | undefined} [provider] 提供方 ID
 * @property {string | undefined} [model] 模型名称
 * @property {number | undefined} [temperature] 采样温度
 * @property {number | undefined} [max_tokens] 最大输出 token
 * @property {string | undefined} [base_url] 自定义 API Base URL
 * @property {string | undefined} [api_key_env] API Key 环境变量名
 * @property {string | undefined} [minimax_group_id] MiniMax group_id
 * @property {string | undefined} [openrouter_referer] OpenRouter Referer
 * @property {string | undefined} [openrouter_title] OpenRouter 应用标题
 */

/**
 * @typedef {Object} LspResolvedConfig
 * @property {LspProviderId} providerId 提供方 ID
 * @property {string} providerName 提供方名称
 * @property {string} model 模型名称
 * @property {number} temperature 采样温度
 * @property {number | null} maxTokens 最大输出 token
 * @property {string} baseUrl API Base URL
 * @property {string | null} apiKey API Key（已解析）
 * @property {string} apiKeyEnv API Key 环境变量名
 * @property {string} minimaxGroupId MiniMax group_id
 * @property {string} openrouterReferer OpenRouter Referer
 * @property {string} openrouterTitle OpenRouter 应用标题
 */

/**
 * @typedef {Object} LspProviderDefinition
 * @property {LspProviderId} id 提供方 ID
 * @property {string} name 提供方名称
 * @property {string} defaultModel 默认模型
 * @property {string} defaultBaseUrl 默认 API Base URL
 * @property {string} defaultApiKeyEnv 默认 API Key 环境变量名
 * @property {boolean} requiresApiKey 是否必须 API Key
 * @property {boolean} requiresGroupId 是否必须 group_id
 * @property {(cfg: LspResolvedConfig) => import("@langchain/core/language_models/chat_models").BaseChatModel} build 构造模型实例
 */

/** @type {Record<LspProviderId, LspProviderDefinition>} */
const PROVIDERS = {
  openrouter: {
    id: "openrouter",
    name: "OpenRouter",
    defaultModel: "google/gemini-3-flash-preview",
    defaultBaseUrl: "https://openrouter.ai/api/v1",
    defaultApiKeyEnv: "OPENROUTER_API_KEY",
    requiresApiKey: true,
    requiresGroupId: false,
    build: (cfg) => {
      const headers = {};
      if (cfg.openrouterReferer) headers["HTTP-Referer"] = cfg.openrouterReferer;
      if (cfg.openrouterTitle) headers["X-Title"] = cfg.openrouterTitle;
      return new ChatOpenAI(
        {
          model: cfg.model,
          temperature: cfg.temperature,
          maxTokens: cfg.maxTokens ?? undefined,
          apiKey: cfg.apiKey ?? undefined,
        },
        {
          baseURL: cfg.baseUrl,
          ...(Object.keys(headers).length ? { defaultHeaders: headers } : {}),
        },
      );
    },
  },
  ollama: {
    id: "ollama",
    name: "Ollama",
    defaultModel: "llama3.1",
    defaultBaseUrl: "http://127.0.0.1:11434",
    defaultApiKeyEnv: "",
    requiresApiKey: false,
    requiresGroupId: false,
    build: (cfg) =>
      new ChatOllama({
        model: cfg.model,
        temperature: cfg.temperature,
        baseUrl: cfg.baseUrl,
      }),
  },
  tongyi: {
    id: "tongyi",
    name: "Tongyi (阿里千问)",
    defaultModel: "qwen-max",
    defaultBaseUrl: "",
    defaultApiKeyEnv: "ALIBABA_API_KEY",
    requiresApiKey: true,
    requiresGroupId: false,
    build: (cfg) =>
      new ChatAlibabaTongyi({
        model: cfg.model,
        temperature: cfg.temperature,
        maxTokens: cfg.maxTokens ?? undefined,
        alibabaApiKey: cfg.apiKey ?? undefined,
      }),
  },
  deepseek: {
    id: "deepseek",
    name: "DeepSeek",
    defaultModel: "deepseek-chat",
    defaultBaseUrl: "",
    defaultApiKeyEnv: "DEEPSEEK_API_KEY",
    requiresApiKey: true,
    requiresGroupId: false,
    build: (cfg) =>
      new ChatDeepSeek({
        model: cfg.model,
        temperature: cfg.temperature,
        maxTokens: cfg.maxTokens ?? undefined,
        apiKey: cfg.apiKey ?? undefined,
      }),
  },
  kimi: {
    id: "kimi",
    name: "Kimi (Moonshot)",
    defaultModel: "moonshot-v1-8k",
    defaultBaseUrl: "",
    defaultApiKeyEnv: "MOONSHOT_API_KEY",
    requiresApiKey: true,
    requiresGroupId: false,
    build: (cfg) =>
      new ChatMoonshot({
        model: cfg.model,
        temperature: cfg.temperature,
        maxTokens: cfg.maxTokens ?? undefined,
        apiKey: cfg.apiKey ?? undefined,
      }),
  },
  minimax: {
    id: "minimax",
    name: "MiniMax",
    defaultModel: "abab6.5-chat",
    defaultBaseUrl: "",
    defaultApiKeyEnv: "MINIMAX_API_KEY",
    requiresApiKey: true,
    requiresGroupId: true,
    build: (cfg) =>
      new ChatMinimax({
        model: cfg.model,
        temperature: cfg.temperature,
        maxTokens: cfg.maxTokens ?? undefined,
        minimaxApiKey: cfg.apiKey ?? undefined,
        minimaxGroupId: cfg.minimaxGroupId,
      }),
  },
};

/**
 * @typedef {Object} LspProviderInfo
 * @property {LspProviderId} id 提供方 ID
 * @property {string} name 提供方名称
 * @property {string} defaultModel 默认模型
 * @property {string} defaultBaseUrl 默认 API Base URL
 * @property {string} defaultApiKeyEnv 默认 API Key 环境变量名
 * @property {boolean} requiresApiKey 是否必须 API Key
 * @property {boolean} requiresGroupId 是否必须 group_id
 */

/** @returns {LspProviderInfo[]} 提供方列表 */
export function listLspProviders() {
  return Object.values(PROVIDERS).map((p) => ({
    id: p.id,
    name: p.name,
    defaultModel: p.defaultModel,
    defaultBaseUrl: p.defaultBaseUrl,
    defaultApiKeyEnv: p.defaultApiKeyEnv,
    requiresApiKey: p.requiresApiKey,
    requiresGroupId: p.requiresGroupId,
  }));
}

/**
 * @param {unknown} value 待解析值
 * @param {number | null} fallback 默认值
 * @returns {number | null}
 */
function normalizeNumber(value, fallback) {
  if (value == null) return fallback;
  const num = Number(value);
  if (!Number.isFinite(num)) return fallback;
  return num;
}

/**
 * @param {string | undefined | null} value 待解析字符串
 * @returns {string}
 */
function normalizeString(value) {
  if (!value) return "";
  return String(value).trim();
}

/**
 * @param {{ lsp?: LspConfig; provider?: LspProviderId; model?: string }} config 全局配置
 * @param {{ provider?: string | null; model?: string | null; baseUrl?: string | null; apiKey?: string | null; apiKeyEnv?: string | null; temperature?: number | null; maxTokens?: number | null; minimaxGroupId?: string | null; }} args 命令行覆盖
 * @returns {LspResolvedConfig}
 */
export function resolveLspConfig(config, args) {
  const rawLsp = (config && typeof config === "object" && config.lsp && typeof config.lsp === "object") ? config.lsp : {};
  const providerId = normalizeString(args.provider ?? rawLsp.provider ?? config.provider ?? "openrouter");
  if (!providerId || !(providerId in PROVIDERS)) {
    const ids = Object.keys(PROVIDERS).join(", ");
    throw new Error(`未知 LSP provider: ${providerId || "(空)"}。可用：${ids}`);
  }
  const provider = PROVIDERS[/** @type {LspProviderId} */ (providerId)];

  const model = normalizeString(args.model ?? rawLsp.model ?? config.model ?? provider.defaultModel);
  if (!model) {
    throw new Error(`LSP provider ${provider.id} 缺少 model`);
  }

  const envBaseUrl = provider.id === "ollama" ? normalizeString(process.env.OLLAMA_BASE_URL) : "";
  const baseUrl = normalizeString(args.baseUrl ?? rawLsp.base_url ?? envBaseUrl ?? provider.defaultBaseUrl);
  const apiKeyEnv = normalizeString(args.apiKeyEnv ?? rawLsp.api_key_env ?? provider.defaultApiKeyEnv);
  const apiKey = normalizeString(args.apiKey ?? (apiKeyEnv ? process.env[apiKeyEnv] : "")) || null;
  const minimaxGroupId = normalizeString(args.minimaxGroupId ?? rawLsp.minimax_group_id ?? process.env.MINIMAX_GROUP_ID) || "";
  const temperature = normalizeNumber(args.temperature ?? rawLsp.temperature, 0) ?? 0;
  const maxTokens = normalizeNumber(args.maxTokens ?? rawLsp.max_tokens, null);
  const openrouterReferer = normalizeString(rawLsp.openrouter_referer ?? process.env.OPENROUTER_REFERER);
  const openrouterTitle = normalizeString(rawLsp.openrouter_title ?? process.env.OPENROUTER_TITLE);

  return {
    providerId: provider.id,
    providerName: provider.name,
    model,
    temperature,
    maxTokens,
    baseUrl,
    apiKey,
    apiKeyEnv,
    minimaxGroupId,
    openrouterReferer,
    openrouterTitle,
  };
}

/**
 * @param {LspResolvedConfig} cfg 已解析配置
 */
export function validateLspConfig(cfg) {
  const provider = PROVIDERS[cfg.providerId];
  if (provider.requiresApiKey && !cfg.apiKey) {
    const envHint = cfg.apiKeyEnv ? `环境变量 ${cfg.apiKeyEnv}` : "--api-key";
    throw new Error(`缺少 LSP API Key（${envHint}）。provider=${provider.id}`);
  }
  if (provider.requiresGroupId && !cfg.minimaxGroupId) {
    throw new Error("缺少 MINIMAX_GROUP_ID（MiniMax 需要 group_id）。");
  }
}

/**
 * @param {LspResolvedConfig} cfg 已解析配置
 * @returns {import("@langchain/core/language_models/chat_models").BaseChatModel}
 */
export function buildLspModel(cfg) {
  const provider = PROVIDERS[cfg.providerId];
  return provider.build(cfg);
}
