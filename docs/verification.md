# 验证方法与证据边界

本文件说明公开 Demo 的检查方法及其能证明的范围。现有材料不证明真实模型部署、租用服务器冒烟测试、准确率检验或正式投用。

## 本地验收

使用 Python 3.12，先安装 `requirements-dev.txt`。真实视频测试要求 PATH 中提供支持 `-fps_mode` 的 `ffmpeg` 和 `ffprobe`；合成变分辨率视频还需 FFmpeg 的 `libx264` 编码器。缺少所需工具或编码器时测试会失败，不会跳过。

~~~text
python -m pytest -q
python scripts/check_public_surface.py
docker compose config
~~~

## 检查范围

- 图片单测检查 RGB JPEG 转换；接口测试检查空文件、超大文件和模拟 FFmpeg 失败的结构化错误；
- 视频回归通过 HTTP 接口调用真实 FFprobe 和 FFmpeg，检查抽帧与联系表输出，详见下节；
- Mock 测试检查 JSON/SSE 响应、文本提取和输入校验；不检查视觉内容，也不证明媒体文件到达模型接口；
- Dify 测试用 YAML 解析器检查版本字段、节点和边数量、指定端点及部分环境变量，不启动 Dify；
- `docker compose config` 检查配置能否解析，不构建镜像或启动容器；
- 公开内容扫描只检查脚本内的地址、凭据和路径规则，部分目录及文件会被跳过；无命中不保证没有其他秘密、业务媒体或模型权重。

CI 配置在 Ubuntu 安装 FFmpeg 后执行上述测试、公开内容扫描和 Compose 配置校验；是否通过以对应提交的运行记录为准。Dify 的实机导入、插件兼容性、文件传递和端到端运行仍未验证；现有 DSL 没有独立 IF-ELSE 节点。

## 真实 FFmpeg 视频回归

`tests/test_media_ffmpeg.py` 在临时目录生成彩色 PNG，并生成 FFV1/MKV、MPEG-4/MP4 及变分辨率 H.264/MKV 合成视频，不使用业务媒体。可单独运行：

~~~text
python -m pytest -q tests/test_media_ffmpeg.py
~~~

- 覆盖 1 fps、0.5 fps、30 fps、单帧短视频、可变帧率（VFR）、非零起始时间戳、两个视频流、MP4 重排帧及中途改变分辨率或宽高比的视频；
- 检查 `max_frames` 默认值及 0、1、4、8、99，验证 1–8 的钳制、按真实时间选帧、去重和始终使用首个视频流；
- 检查 HTTP 200、JPEG/RGB、1920 × 660 联系表、`X-Media-Source`、实际 `X-Frame-Count`，并按每格中心颜色确认输出对应预期原始帧；宽高比变化用留白和内容像素检查是否被拉伸；
- 相对首帧的时间标签由独立单测检查，未通过 OCR 验证渲染文字。

这些回归覆盖指定合成输入的媒体服务链路，不代表所有视频编码都已验证，也不覆盖 Dify 或真实模型。

## 真实系统的额外验证

真实模型上线前还需要单独完成模型接口连通性、冒烟测试、准确率检验、端到端回归、GPU 资源评估和故障恢复验证。本 Demo 不替代这些验证。
