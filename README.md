# 双模型视觉工作流脱敏 Demo

一个面向视觉媒体预处理、Mock 接口和 AI 工作流编排的最小示例。

本仓库面向道路监测等视觉输入场景，公开内容只用于展示工程方法和接口契约，不代表任何组织官方发布，不提供业务数据、模型权重、生产配置或真实业务结果。

[![CI](https://github.com/yousizaitianqiong/vision-dual-model-workflow/actions/workflows/ci.yml/badge.svg)](https://github.com/yousizaitianqiong/vision-dual-model-workflow/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-OpenAI--compatible-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## 项目定位

公开代码包含 FastAPI + Pillow + FFmpeg 媒体预处理服务、两个 OpenAI 风格 Mock 服务，以及目标为 Dify 1.17.x 的 Workflow DSL 示例。视频预处理生成最多 8 帧、带帧序号和时间标签的 JPEG 联系表。

当前 Compose 和 DSL 使用 `sensenova-si-2b` 作为初筛 Mock 别名，使用 `qwen3-vl-8b` 作为复核 Mock 别名。它们不加载真实权重，别名不证明真实模型型号、接口兼容性、授权或部署状态。“Qwen 初筛 + 第二模型复核”仍是待验证方案，与当前 Demo 的角色安排不同，不能写成已经实现。

现有材料不足以确认租用服务器冒烟测试、准确率检验、真实模型部署或正式投用。Dify 目前仅做 YAML 静态契约检查，尚未验证实机导入和端到端运行。验证方法与边界见 [验证说明](docs/verification.md)。

## 数据流

以下为 DSL 描述的预期路径，尚未完成 Dify 端到端验证：

~~~text
图片/短视频 + 自定义提示词
          |
          v
FastAPI / FFmpeg 媒体预处理
  图片：EXIF 校正、RGB 转换、JPEG 规范化
  视频：按时间采样最多 8 个实际帧、时间标签、联系表
          |
          v
sensenova-si-2b 初筛 Mock
          |
          v
qwen3-vl-8b 复核 Mock
          |
          v
Dify 模板汇总：详细对比 / 精简结论 / 原始结果
~~~

## 快速运行

要求：Docker 和 Docker Compose；镜像构建会安装 FFmpeg。以下命令用于尝试启动 Demo，CI 的 `docker compose config` 只校验配置，不证明镜像已构建或容器已成功启动。

~~~bash
docker compose up --build
~~~

服务启动后可以检查：

~~~bash
curl http://localhost:8002/healthz
curl http://localhost:8001/v1/models
curl http://localhost:8003/v1/models
~~~

媒体预处理服务只接收上传文件，不接受任意 URL 或命令参数。Mock 模型服务只从请求中提取文本字段并返回示例文本，不解析或校验图片；Mock 回答不能证明视觉输入已到达。

## Dify 工作流导入

工作流文件位于 `workflow/dify-vision-dual-model-demo.yml`，以 Dify 1.17.x 为目标，包含 6 个节点和 5 条边；目标版本兼容性尚未经实机导入验证：

1. 输入：图片或视频、自定义提示词、输出格式；
2. 媒体预处理：调用 media-preprocess 服务；
3. `sensenova-si-2b` 初筛 Mock；
4. `qwen3-vl-8b` 复核 Mock；
5. 模板汇总；
6. 结果输出。

Compose 只包含媒体服务和两个 Mock，不启动 Dify。尝试导入时，在独立 Dify 实例的 OpenAI API Compatible 供应商中配置两个模型别名。公开 Demo 可分别指向 `mock-sensenova:8001/v1` 和 `mock-qwen:8003/v1`。Dify 容器需要加入能够解析这些服务名的网络。当前 DSL 有 HTTP 节点，没有独立的 IF-ELSE 节点；模板内部的条件格式化不等同于工作流分支验证。

候选导入步骤和待验收项见 [Dify 导入说明](docs/dify-import.md)。

## 公开接口

### 媒体预处理

~~~text
GET  /healthz
POST /v1/media/prepare
~~~

POST 接口使用 multipart/form-data：

- file：必填，图片或视频文件；
- max_frames：可选整数，默认 8；小于 1 按 1 处理，大于 8 按 8 处理。

图片返回规范化 JPEG。视频在首帧到末帧的时间范围内均匀布点，选择最近的实际可解码帧并去重，返回 JPEG 联系表。实际帧数还受视频时长和可用帧数限制，可能少于 `max_frames`；标签时间相对首帧计算。响应头给出来源类型和实际帧数。默认单文件上限为 100 MB，视频时长上限为 120 秒。

### OpenAI 兼容 Mock 服务

~~~text
GET  /healthz
GET  /v1/models
POST /v1/chat/completions
~~~

chat completions 支持 `stream=false` 的 JSON 响应和 `stream=true` 的 SSE 响应，测试覆盖这些接口响应及输入错误。Dify 与供应商插件之间的实际协议适配仍需端到端验证。

## 项目结构

~~~text
services/
  media_preprocess_server.py       图片和视频预处理
  mock_openai_vision_server.py     OpenAI 兼容视觉模型 Mock
workflow/
  dify-vision-dual-model-demo.yml  脱敏 Dify Workflow DSL
tests/
  test_media_preprocess.py         媒体处理测试
  test_media_ffmpeg.py              合成视频与真实 FFmpeg 接口回归
  test_mock_openai_vision.py       JSON/SSE 协议测试
docs/
  architecture.md                  架构与数据流
  deployment-boundaries.md         生产部署边界
  dify-import.md                   Dify 导入说明
  verification.md                  验证方法与证据边界
scripts/
  check_public_surface.py          公开内容规则扫描
~~~

## 工程边界

- 视频预处理只生成最多 8 帧的联系表；Mock 不分析联系表，也不提供逐帧完整视频理解；
- Demo 不进行音频分析，不代表实时视频流处理；
- Mock 测试验证请求结构、文本处理、JSON/SSE 响应和部分异常处理，不证明视觉文件链路、真实模型准确率或生产稳定性；
- 私有化部署、GPU 推理、离线依赖和内网访问控制需要独立验证，仓库中的部署建议不是完成记录；
- 公开内容扫描仅检查脚本列出的规则，并跳过部分文件；扫描通过不保证不存在任何秘密或业务内容；
- 不上传内部地址、账号、口令、模型权重、业务媒体或未经证实的性能数字。

## 后续可验证方向

- 为更多图片格式和视频编码补充回归样本；
- 扩展不含业务数据的合成媒体回归场景；
- 完成 Dify 实机导入、媒体文件传递和双 Mock 调用的端到端验收；
- 核对真实模型的型号、协议和授权后，将 Mock 端点替换为授权服务，验证模型角色方案；
- 对双模型链路分别记录真实的测试集、准确率、P50/P95 延迟和资源占用。

在获得真实测试记录前，不把上述内容写成已达成的性能指标。

## 许可

新增 Demo 代码和文档采用 MIT License。真实企业项目的业务代码、数据、模型权重和部署配置不属于本仓库授权范围。

安全问题请参阅 SECURITY.md，不要在公开 Issue 中提交凭据、内部地址或业务数据。
