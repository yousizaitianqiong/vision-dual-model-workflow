# Dify Workflow DSL 导入说明

## 导入文件

使用 `workflow/dify-vision-dual-model-demo.yml`，目标版本为 Dify 1.17.x。文件包含输入、媒体预处理、`sensenova-si-2b` 初筛 Mock、`qwen3-vl-8b` 复核 Mock、模板汇总和结束节点。两个名称是 Demo 别名，不证明真实模型型号、授权或部署状态。

当前只完成 YAML 静态契约检查，尚未验证 Dify 实机导入、供应商插件兼容性或端到端运行。以下是候选操作步骤，不是成功导入记录。DSL 有 HTTP 节点，没有独立 IF-ELSE 节点。

## 导入步骤

1. 准备独立的 Dify 实例（本仓库 Compose 不包含 Dify），选择从 DSL 文件导入；
2. 选择 workflow/dify-vision-dual-model-demo.yml；
3. 安装并启用 OpenAI API Compatible 模型供应商插件；
4. 在模型供应商中配置两个模型，名称分别保持为 qwen3-vl-8b 和 sensenova-si-2b；
5. 让 Dify 运行环境能够访问 media-preprocess:8002；
6. 上传合成图片或短视频，运行一次详细对比流程。

公开 Demo 中，`sensenova-si-2b` 指向 `mock-sensenova:8001/v1`，`qwen3-vl-8b` 指向 `mock-qwen:8003/v1`。真实模型的型号、协议、授权和端点必须另行核验，内部地址不能写回公开 DSL。

## 输入和输出

- 输入：单个图片或视频、自定义提示词、输出格式；
- 图片处理：EXIF 方向校正、RGB 转换和 JPEG 输出；
- 视频处理：按时间均匀布点选择最近的实际帧，去重后生成最多 8 帧的联系表；帧数可少于请求值，标签时间相对首帧计算；
- 预期输出：两个 Mock 的示例文本和模板化汇总。

视频联系表只包含被抽取的画面，不包含音频，也不等同于逐帧完整理解。Mock 只消费文本字段，不读取或校验图片，回答不能作为视觉输入已到达的证明。

## 待验收项

在指定 Dify 和插件版本下记录实际导入结果，确认上传文件、媒体服务返回的 JPEG 和两个模型节点之间的传递，再验证两种角色的调用及模板输出。需要检查实际请求中的视觉内容；只看到 Mock 返回成功文本不足以证明文件链路通过。
