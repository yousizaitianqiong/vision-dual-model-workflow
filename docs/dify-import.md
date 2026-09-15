# Dify Workflow DSL 导入说明

## 导入文件

使用 workflow/dify-vision-dual-model-demo.yml，目标版本为 Dify 1.17.x。文件包含输入、媒体预处理、SenseNova 初筛、Qwen 复核、模板汇总和结束节点。

## 导入步骤

1. 在 Dify 中选择从 DSL 文件导入；
2. 选择 workflow/dify-vision-dual-model-demo.yml；
3. 安装并启用 OpenAI API Compatible 模型供应商插件；
4. 在模型供应商中配置两个模型，名称分别保持为 qwen3-vl-8b 和 sensenova-si-2b；
5. 让 Dify 运行环境能够访问 media-preprocess:8002；
6. 上传合成图片或短视频，运行一次详细对比流程。

公开 Demo 的两个模型端点可以指向 Compose 中的 mock-sensenova:8001/v1 和 mock-qwen:8003/v1。真实部署时，模型地址必须由授权环境配置，不能写回公开 DSL。

## 输入和输出

- 输入：单个图片或视频、自定义提示词、输出格式；
- 图片处理：EXIF 方向校正、RGB 转换和 JPEG 输出；
- 视频处理：均匀抽取最多 8 帧并生成带时间标签的联系表；
- 输出：SenseNova 初筛、Qwen 复核和模板化最终建议。

视频输出只代表被抽取帧中的可见内容，不包含音频分析，也不等同于逐帧完整理解。
