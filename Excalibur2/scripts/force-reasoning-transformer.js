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
// This transformer forces `reasoning: { enabled: <bool> }` unconditionally,
// overriding whatever the built-in "openrouter" transformer set (or left
// unset). Register it AFTER "openrouter" (and after "tooluse") in a
// provider's transformer.use list so it runs after that translation has
// already happened, not before.
//
// Config (in config.json's top-level "transformers" array):
//   {
//     "path": "...",
//     "options": {
//       "enabled": false,                 // true forces reasoning ON for
//                                          // every request; false forces
//                                          // it OFF. Required.
//       "models": ["qwen/qwen3.5-9b"]     // optional; omit to apply to
//                                          // every request that reaches
//                                          // this transformer regardless
//                                          // of model.
//     }
//   }
//
// Note: forcing `enabled: true` for every request -- including simple
// background/tool-use steps that don't need it -- means every single call
// pays reasoning-token cost and latency, not just the requests Claude Code
// itself would have flagged as think-worthy. That's the whole point if
// you're deliberately testing "always thinking," but worth knowing before
// running a full 50-CVE batch this way.
class ForceReasoningTransformer {
  name = "force-reasoning";

  constructor(options = {}) {
    this.enabled = options.enabled === true;
    this.models = Array.isArray(options.models) ? options.models : null;
  }

  async transformRequestIn(request) {
    if (this.models && !this.models.includes(request.model)) {
      return request;
    }
    request.reasoning = { enabled: this.enabled };
    return request;
  }
}

module.exports = ForceReasoningTransformer;
