// force-reasoning-transformer.js
//
// ccr's built-in "openrouter" transformer only sets `reasoning` based on
// Claude Code's own per-request thinking classification (roughly: enabled
// for "think"-routed requests, omitted for "background" etc.) -- there's
// no static per-model toggle in config.json. Since Excalibur's
// OPENROUTER_ROUTER maps every role to the same model, that per-request
// variability means you can't reliably guarantee ALL requests go one way
// or the other just from the router config.
//
// This transformer forces `reasoning` to a specific value per model,
// overriding whatever the built-in "openrouter" transformer set (or left
// unset). Register it AFTER "openrouter" (and after "tooluse") in a
// provider's transformer.use list so it runs after that translation has
// already happened, not before.
//
// IMPORTANT: not all reasoning-capable models accept the same values here.
// "Hybrid" models (e.g. Qwen3.5's family) have a genuine on/off switch --
// `{ enabled: false }` cleanly disables reasoning. "Mandatory reasoning"
// models (e.g. OpenAI's GPT-OSS family) do NOT -- OpenRouter's own docs
// say these reject `effort: "none"` / an explicit disable outright rather
// than silently ignoring it. For those, the closest you can get is turning
// effort down to "low", not off. Sending the wrong shape to a mandatory
// model will likely fail every request with an HTTP 400, not just no-op --
// hence per-model rules below rather than one blanket setting for
// everything.
//
// Config (in config.json's top-level "transformers" array):
//   {
//     "path": "...",
//     "options": {
//       "rules": [
//         { "models": ["qwen/qwen3.5-9b"], "reasoning": { "enabled": false } },
//         { "models": ["openai/gpt-oss-20b", "openai/gpt-oss-120b"],
//           "reasoning": { "effort": "low" } }
//       ]
//     }
//   }
// The first rule whose "models" list includes the request's model wins.
// Requests for a model not listed in any rule pass through unmodified.
class ForceReasoningTransformer {
  name = "force-reasoning";

  constructor(options = {}) {
    this.rules = Array.isArray(options.rules) ? options.rules : [];
  }

  async transformRequestIn(request) {
    for (const rule of this.rules) {
      if (Array.isArray(rule.models) && rule.models.includes(request.model)) {
        if (rule.reasoning) {
          request.reasoning = rule.reasoning;
        }
        break;
      }
    }
    return request;
  }
}

module.exports = ForceReasoningTransformer;
