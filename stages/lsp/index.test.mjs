import assert from "node:assert/strict";
import test from "node:test";
import { buildLspModel, resolveLspConfig } from "./index.mjs";

test("openrouter: empty base_url should fallback to provider default", () => {
  const resolved = resolveLspConfig(
    {
      lsp: {
        provider: "openrouter",
        model: "google/gemini-3-flash-preview",
        base_url: "",
      },
    },
    {},
  );
  assert.equal(resolved.baseUrl, "https://openrouter.ai/api/v1");
});

test("openrouter: missing base_url should fallback to provider default", () => {
  const resolved = resolveLspConfig(
    {
      lsp: {
        provider: "openrouter",
        model: "google/gemini-3-flash-preview",
      },
    },
    {},
  );
  assert.equal(resolved.baseUrl, "https://openrouter.ai/api/v1");
});

test("ollama: should respect OLLAMA_BASE_URL env when config missing", () => {
  const old = process.env.OLLAMA_BASE_URL;
  process.env.OLLAMA_BASE_URL = "http://127.0.0.1:11435";
  try {
    const resolved = resolveLspConfig(
      {
        lsp: {
          provider: "ollama",
          model: "qwen2.5:14b",
        },
      },
      {},
    );
    assert.equal(resolved.baseUrl, "http://127.0.0.1:11435");
  } finally {
    if (old == null) delete process.env.OLLAMA_BASE_URL;
    else process.env.OLLAMA_BASE_URL = old;
  }
});

test("openrouter: ChatOpenAI client should receive baseURL via configuration", () => {
  const resolved = resolveLspConfig(
    {
      lsp: {
        provider: "openrouter",
        model: "google/gemini-3-flash-preview",
        base_url: "https://openrouter.ai/api/v1",
        openrouter_referer: "https://example.com",
        openrouter_title: "OpenLedger",
      },
    },
    {},
  );
  const model = buildLspModel(resolved);
  assert.equal(model?.clientConfig?.baseURL, "https://openrouter.ai/api/v1");
  assert.equal(model?.clientConfig?.defaultHeaders?.["HTTP-Referer"], "https://example.com");
  assert.equal(model?.clientConfig?.defaultHeaders?.["X-Title"], "OpenLedger");
});
