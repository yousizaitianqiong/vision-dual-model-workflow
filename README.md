# 双模型视觉工作流脱敏 Demo

一个面向视觉大模型私有化部署与 AI 工作流编排的可复现最小示例。

本仓库来自一个道路监测视觉项目的脱敏技术整理，公开内容只用于展示工程方法和接口契约，不代表任何组织官方发布，也不包含业务数据、模型权重、生产配置或真实业务结果。

[![CI](https://github.com/yousizaitianqiong/vision-dual-model-workflow/actions/workflows/ci.yml/badge.svg)](https://github.com/yousizaitianqiong/vision-dual-model-workflow/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-OpenAI--compatible-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## 项目定位

真实项目面向道路监测场景，工程链路包括：

- 上线前租用服务器完成模型选型、冒烟测试和准确率检验；
- 验证通过后迁移至离线私有化环境，完成视觉模型部署并正式投用；
- 以 SenseNova-SI-2B 负责快速初筛，以 Qwen3-VL-8B 负责独立复核；
- 使用 Dify 1.17.x Workflow DSL 编排媒体输入、自定义提示词、双模型推理和结果汇总；
- 使用 FastAPI + FFmpeg 对图片和视频进行媒体预处理；
- 视频按时间均匀抽取最多 8 帧，合成为带帧序号和时间标签的 JPEG 联系表。

公开 Demo 使用 Mock 模型服务复现协议和工作流边界，不加载 Qwen3-VL 或 SenseNova 的真实权重。真实项目中的准确率、吞吐量、延迟、显存占用和业务数据均不在本仓库中公开。

## 数据流

~~~text
图片/短视频 + 自定义提示词
          |
          v
FastAPI / FFmpeg 媒体预处理
  图片：EXIF 校正、RGB 转换、JPEG 规范化
  视频：最多 8 帧均匀抽取、时间标签、联系表
          |
          v
SenseNova-SI-2B 初筛
          |
          v
Qwen3-VL-8B 复核
          |
          v
Dify 模板汇总：详细对比 / 精简结论 / 原始结果
~~~

## 快速运行

要求：Docker、Docker Compose 和可用的 FFmpeg 运行环境。

~~~bash
docker compose up --build
~~~

服务启动后可以检查：

~~~bash
curl http://localhost:8002/healthz
curl http://localhost:8001/v1/models
curl http://localhost:8003/v1/models
~~~

媒体预处理服务只接收上传文件，不接受任意 URL 或命令参数。Mock 模型服务只返回用于联调的确定性示例文本。

## Dify 工作流导入

工作流文件位于 workflow/dify-vision-dual-model-demo.yml，结构与 Dify 1.17.x Workflow DSL 对齐，包含 6 个节点和 5 条边：

1. 输入：图片或视频、自定义提示词、输出格式；
2. 媒体预处理：调用 media-preprocess 服务；
3. SenseNova-SI-2B 初筛；
4. Qwen3-VL-8B 复核；
5. 模板汇总；
6. 结果输出。

导入后，在 Dify 的 OpenAI API Compatible 供应商中配置两个模型。公开 Demo 可分别指向 mock-sensenova:8001/v1 和 mock-qwen:8003/v1；真实部署时应由部署环境绑定经过授权的模型服务端点。Dify 容器需要加入能够解析 media-preprocess 服务名的网络。

完整说明见 docs/dify-import.md。

## 公开接口

### 媒体预处理

~~~text
GET  /healthz
POST /v1/media/prepare
~~~

POST 接口使用 multipart/form-data：

- file：必填，图片或视频文件；
- max_frames：可选，范围为 1–8，默认 8。

图片返回规范化 JPEG。视频返回 JPEG 联系表，并通过响应头给出来源类型和实际帧数。默认单文件上限为 100 MB，视频时长上限为 120 秒。

### OpenAI 兼容 Mock 服务

~~~text
GET  /healthz
GET  /v1/models
POST /v1/chat/completions
~~~

chat completions 支持 stream=false 的 JSON 响应和 stream=true 的 SSE 响应，便于验证 Dify 与 OpenAI 风格服务之间的协议适配。

## 项目结构

~~~text
services/
  media_preprocess_server.py       图片和视频预处理
  mock_openai_vision_server.py     OpenAI 兼容视觉模型 Mock
workflow/
  dify-vision-dual-model-demo.yml  脱敏 Dify Workflow DSL
tests/
  test_media_preprocess.py         媒体处理测试
  test_mock_openai_vision.py       JSON/SSE 协议测试
docs/
  architecture.md                  架构与数据流
  deployment-boundaries.md         生产部署边界
  dify-import.md                   Dify 导入说明
scripts/
  check_public_surface.py          公开内容安全扫描
~~~

## 工程边界

- 视频能力是均匀抽取最多 8 帧并分析联系表，不是逐帧完整视频理解；
- Demo 不进行音频分析，不代表实时视频流处理；
- Mock 服务只验证文件链路、模型协议和异常处理，不代表真实模型准确率；
- 私有化部署、Docker/NVIDIA GPU、systemd、离线依赖和内网访问控制属于原项目工程背景，公开仓库只保留脱敏说明；
- 不上传内部地址、账号、口令、模型权重、业务媒体或未经证实的性能数字。

## 后续可验证方向

- 为更多图片格式和视频编码补充回归样本；
- 在不包含业务数据的前提下补充可复现的合成媒体夹具；
- 将真实模型端点替换为经过授权的本地 OpenAI 兼容服务；
- 对双模型链路分别记录真实的测试集、准确率、P50/P95 延迟和资源占用。

在获得真实测试记录前，不把上述内容写成已达成的性能指标。

## 许可

新增 Demo 代码和文档采用 MIT License。真实企业项目的业务代码、数据、模型权重和部署配置不属于本仓库授权范围。

安全问题请参阅 SECURITY.md，不要在公开 Issue 中提交凭据、内部地址或业务数据。
