# 验证记录模板

本文件定义公开 Demo 的可复现验收项。真实企业项目的测试集和结果不在仓库中公开。

## 本地验收

~~~text
python -m pytest -q
python scripts/check_public_surface.py
docker compose config
~~~

## 覆盖范围

- 图片能够输出 JPEG；
- 视频能够均匀抽取 1–8 帧并生成联系表；
- 空文件、未知格式、超大文件、超长视频和 FFmpeg 失败能够返回结构化错误；
- Mock 模型能够返回 JSON 和 SSE；
- Dify DSL 能够被 YAML 解析器读取，并包含预期的节点和边；
- 公开内容不包含内网地址、凭据、私有路径、业务媒体或模型权重。

## 真实系统的额外验证

真实模型上线前还需要单独完成模型接口连通性、冒烟测试、准确率检验、端到端回归、GPU 资源评估和故障恢复验证。本 Demo 不替代这些验证。
