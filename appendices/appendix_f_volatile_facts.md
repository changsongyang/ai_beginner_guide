# 附录 F：快变事实核验表

> Last verified: 2026-06-17. 本表用于约束本书中模型、工具、价格、上下文窗口、benchmark 和规则性事实的更新。

| 类别 | 当前维护口径 | 权威入口 | 给初学者的写法 |
| --- | --- | --- | --- |
| OpenAI | GPT-5.x、ChatGPT、Responses API、Sora 等以官方模型/API/帮助中心为准。 | [OpenAI Models](https://developers.openai.com/api/docs/models/all/), [OpenAI Pricing](https://openai.com/api/pricing/) | 用“截至 YYYY-MM-DD”说明，不把某个模型写成永久最佳。 |
| Anthropic | Claude Fable 5 / Mythos 5（2026-06-09 发布；曾于 2026-06-12 暂停访问，截至 2026-07-09 官方模型页已恢复 Fable 5 为 GA、Mythos 5 为受限可用）与 Claude 4.x、Claude Code、Claude Design、thinking 支持矩阵以官方文档为准。 | [Claude Models](https://platform.claude.com/docs/en/about-claude/models/overview), [Claude Pricing](https://platform.claude.com/docs/en/about-claude/pricing), [Fable/Mythos access statement](https://www.anthropic.com/news/fable-mythos-access) | 区分正式、beta、research preview 与暂停访问；“最强/旗舰”须区分发布规格和当前可用性。 |
| Google Gemini | Gemini 3.x、Deep Think、音视频能力和 Gemini 2.x/2.5 迁移窗口以 Google AI 文档为准。 | [Gemini Models](https://ai.google.dev/gemini-api/docs/models), [Gemini Deprecations](https://ai.google.dev/gemini-api/docs/deprecations) | 不使用“Gemini Ultra”等非官方名称；写 Gemini 3.5 Flash、3.1 Pro Preview、2.5 Pro/Flash 时标明稳定/预览/迁移状态。 |
| 开源模型 | Llama、DeepSeek、Qwen、Mistral 等以项目 release / model card 为准。 | 官方 GitHub、model card、发布博客 | 本地部署成本写成条件判断，不写“免费无限制”。 |
| 量子与硬件 | 量子路线图、GPU/TPU/NPU 规格以厂商或研究机构资料为准。 | IBM Quantum、NVIDIA、Google、NIST 等官方资料 | 避免“超光速计算”等误导类比。 |
