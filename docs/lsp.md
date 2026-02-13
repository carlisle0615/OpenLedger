# LSP Providers (LangChain)

本项目的 LLM 分类阶段基于 LangChain TS，允许通过 `lsp` 配置接入不同 Provider。

## 配置入口

默认样本位于 `config/classifier.sample.json` 的 `lsp` 字段。你可以用本地覆盖：

- `config/classifier.local.json`：本机私有覆盖（已被 gitignore）

## Provider 列表

当前内置 Provider（可通过 `lsp.provider` 选择）：

- `openrouter`
- `ollama`
- `tongyi`
- `deepseek`
- `kimi`
- `minimax`

## 统一字段（lsp）

```json
{
  "provider": "openrouter",
  "model": "google/gemini-3-flash-preview",
  "api_key_env": "OPENROUTER_API_KEY",
  "base_url": "https://openrouter.ai/api/v1",
  "temperature": 0,
  "max_tokens": null
}
```

## Provider 细节

### OpenRouter

- `provider`: `openrouter`
- `api_key_env`: `OPENROUTER_API_KEY`
- `base_url`: `https://openrouter.ai/api/v1`
- 额外字段：
  - `openrouter_referer`（可选）
  - `openrouter_title`（可选）
  - 也可通过环境变量 `OPENROUTER_REFERER` / `OPENROUTER_TITLE` 提供

### Ollama

- `provider`: `ollama`
- `base_url`: `http://127.0.0.1:11434`
- 不需要 API Key
  - 也可通过环境变量 `OLLAMA_BASE_URL` 覆盖

### Tongyi (阿里千问)

- `provider`: `tongyi`
- `api_key_env`: `ALIBABA_API_KEY`

### DeepSeek

- `provider`: `deepseek`
- `api_key_env`: `DEEPSEEK_API_KEY`

### Kimi (Moonshot)

- `provider`: `kimi`
- `api_key_env`: `MOONSHOT_API_KEY`

### MiniMax

- `provider`: `minimax`
- `api_key_env`: `MINIMAX_API_KEY`
- 额外字段：`minimax_group_id` 或环境变量 `MINIMAX_GROUP_ID`

## 命令行覆盖

`stages/classify_llm.mjs` 支持命令行覆盖部分字段：

```bash
node stages/classify_llm.mjs \
  --provider openrouter \
  --model google/gemini-3-flash-preview \
  --api-key-env OPENROUTER_API_KEY \
  --base-url https://openrouter.ai/api/v1
```

## 常见问题

- LLM 分类是可选的；不开启不会联网。
- 开启后会连接你配置的 LSP Provider。
