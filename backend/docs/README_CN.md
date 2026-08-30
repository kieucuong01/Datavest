<div align="center">
  <a href="https://github.com/OpenByteInc/QuantDinger">
    <img src="screenshots/logo.jpg" alt="QuantDinger 标志" width="180" height="180">
  </a>

  <h1>QuantDinger</h1>
  <p><strong>开源 AI 市场研究与回测平台</strong></p>
  <p>将市场想法转化为 Python 指标、策略研究、回测、提醒和模拟组合——全部运行在一套可自托管系统中。</p>
  <p><strong>QuantDinger 是 Open Byte Inc 的产品。</strong></p>
  <p><em>AI 研究 → 策略代码 → 回测 → 提醒与模拟组合</em></p>

  <p>
    <a href="../README.md"><strong>English</strong></a>
    ·
    <a href="README_CN.md"><strong>简体中文</strong></a>
    ·
    <a href="api/README.md"><strong>API</strong></a>
    ·
    <a href="agent/README.md"><strong>AI Agent 与 MCP</strong></a>
  </p>

  <p>
    <a href="https://ai.quantdinger.com"><strong>在线应用</strong></a>
    ·
    <a href="https://www.quantdinger.com"><strong>官方网站</strong></a>
    ·
    <a href="https://www.youtube.com/watch?v=tNAZ9uMiUUw"><strong>视频演示</strong></a>
    ·
    <a href="mailto:support@quantdinger.com"><strong>官方支持邮箱</strong></a>
  </p>

  <p>
    <a href="https://t.me/quantdinger"><img src="https://img.shields.io/badge/Telegram-加入群组-26A5E4?style=flat-square&logo=telegram&logoColor=white" alt="Telegram"></a>
    <a href="https://discord.com/invite/tyx5B6TChr"><img src="https://img.shields.io/badge/Discord-服务器-5865F2?style=flat-square&logo=discord&logoColor=white" alt="Discord"></a>
    <a href="https://youtube.com/@quantdinger"><img src="https://img.shields.io/badge/YouTube-%40quantdinger-FF0000?style=flat-square&logo=youtube&logoColor=white" alt="YouTube"></a>
    <a href="https://x.com/QuantDinger_EN"><img src="badges/x-quantdinger.svg" alt="X @QuantDinger_EN"></a>
  </p>

  <p>
    <a href="../LICENSE"><img src="https://img.shields.io/badge/License-Apache%202.0-blue.svg?style=flat-square" alt="Apache 2.0"></a>
    <img src="badges/python-3.12.svg" alt="Python 3.12">
    <img src="https://img.shields.io/badge/PostgreSQL-18-4169E1?style=flat-square&logo=postgresql&logoColor=white" alt="PostgreSQL 18">
    <img src="https://img.shields.io/badge/Redis-8-DC382D?style=flat-square&logo=redis&logoColor=white" alt="Redis 8">
    <img src="badges/docker-compose.svg" alt="Docker Compose">
    <a href="https://github.com/OpenByteInc/QuantDinger/releases/latest"><img src="badges/latest-release.svg" alt="最新版本"></a>
  </p>

  <p><sub>赞助支持</sub></p>
  <p>
    <a href="https://www.atlascloud.ai/?utm_source=github&utm_medium=link&utm_campaign=quantdinger" title="Atlas Cloud — AI 推理赞助商">
      <picture>
        <source media="(prefers-color-scheme: dark)" srcset="https://www.atlascloud.ai/logo-white.svg">
        <img src="https://www.atlascloud.ai/logo.svg" alt="Atlas Cloud" width="142">
      </picture>
    </a>
    &nbsp;&nbsp;&nbsp;&nbsp;
    <a href="https://aws.amazon.com/cn/" title="Amazon Web Services — 云基础设施赞助商">
      <picture>
        <source media="(prefers-color-scheme: dark)" srcset="https://a0.awsstatic.com/libra-css/images/logos/aws_smile-header-desktop-en-white_59x35.png">
        <img src="https://upload.wikimedia.org/wikipedia/commons/9/93/Amazon_Web_Services_Logo.svg" alt="Amazon Web Services" width="70">
      </picture>
    </a>
  </p>
</div>

> QuantDinger 后端仅提供研究、回测、提醒和模拟组合能力，不连接用户账户，
> 也不向外部交易场所提交订单。本项目不提供投资建议。

## QuantDinger 是什么

QuantDinger 是一套面向独立交易者、Python 策略开发者和小型团队的
**开源 AI 市场研究与回测平台**。它采用本地优先、可自托管的方式，让行情数据、策略代码和部署环境始终由使用者自己掌控。

项目提供：

- 多 AI 提供商的市场研究和分析；
- Python 指标和 Strategy API V2 策略开发；
- 服务端回测与实验工作流；
- 公开市场行情、提醒、自选和手动/模拟组合；
- Web、移动 H5、Human API、Agent Gateway 和 MCP 接入；
- PostgreSQL 状态存储、持久任务、审计日志和可选监控。

它不是黑盒信号服务。策略代码、研究参数和运行环境都由运营者管理。

## 当前后端范围

- 只读行情数据与服务端数据提供商密钥；
- Strategy API V2 源码、校验、因子研究与回测；
- Indicator IDE、提醒、Universe、自选与手动/模拟组合；
- 有限 Celery 任务与 Scheduler 维护任务；
- 仅使用 R/W/B/N 的 Agent 与 MCP 集成。

## 系统架构

后端分为 Human API、Agent Gateway、只读行情提供商、研究/回测服务、Scheduler 和有限 Celery 任务。PostgreSQL 是事实来源；缓存 Redis 与任务 Redis 使用不同的持久化策略。

外部 AI 通过 MCP 调用 `/api/agent/v1`。它只能访问研究、回测、Indicator、提醒、自选和模拟组合，不能访问用户账户密钥或外部下单能力。

## 快速启动

### 方案 A：使用预构建镜像

前置条件：Docker 和 Compose v2。不需要本地安装 Node.js 或 Python 开发环境。

Linux 或 macOS：

```bash
curl -fsSL https://raw.githubusercontent.com/OpenByteInc/QuantDinger/main/install.sh | bash
```

Windows PowerShell：

```powershell
irm https://raw.githubusercontent.com/OpenByteInc/QuantDinger/main/install.ps1 | iex
```

安装程序会要求设置初始管理员，生成必要密钥，下载 GHCR Compose 配置并启动服务。

启动后访问：

- PC Web：<http://127.0.0.1:8888>
- 移动 H5：<http://127.0.0.1:8889>
- API 健康检查：<http://127.0.0.1:5000/api/health>

### 方案 B：从源码启动

```bash
git clone https://github.com/OpenByteInc/QuantDinger.git
cd QuantDinger
cp backend_api_python/env.example backend_api_python/.env
cp .env.example .env
```

首次启动前，必须替换两个环境文件里的示例值：

| 文件 | 生产环境必须设置的变量 |
| --- | --- |
| `backend_api_python/.env` | `SECRET_KEY`、`ADMIN_USER`、`ADMIN_PASSWORD` |
| `.env` | `POSTGRES_PASSWORD`、`REDIS_PASSWORD`、`CELERY_REDIS_PASSWORD`、`GRAFANA_ADMIN_PASSWORD` |

每个密钥应独立生成：

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

从本地后端源码启动核心服务：

```bash
docker compose up -d --build
docker compose ps
```

基础服务不会启动 Prometheus、Grafana 和 Alertmanager，从而避免普通开源安装
默认承担完整监控栈的资源开销。

Windows、国内镜像、数据库迁移等问题见
[安装故障排查](deployment/INSTALL_TROUBLESHOOTING.md)和[云部署指南](deployment/CLOUD_DEPLOYMENT_CN.md)。

## 生产部署

启动前校验全部生产密钥：

```bash
python backend_api_python/scripts/check_production_config.py \
  --env-file .env \
  --env-file backend_api_python/.env
```

启用生产加固和可选监控：

```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.production.yml \
  -f docker-compose.observability.yml \
  up -d --build
```

资源有限或已经接入外部监控时，可以去掉 `docker-compose.observability.yml`。

生产规则：

- 只通过 TLS 反向代理对外开放 80/443；
- PostgreSQL、两套 Redis、Prometheus、Grafana、Alertmanager 不直接暴露公网；
- 不使用示例密码，不允许核心加密密钥为空；
- 备份 PostgreSQL 和持久化的 `redis-jobs` 数据卷；
- 缓存 Redis 可以淘汰数据，但不能作为 Celery broker；
- 每次部署后检查 API 就绪状态和 Worker 心跳。

完整清单见[生产加固](deployment/PRODUCTION_HARDENING.md)。

## 本机服务地址

所有宿主机端口默认只绑定 `127.0.0.1`。

| 服务 | 默认地址 | 用途 |
| --- | --- | --- |
| PC Web | <http://127.0.0.1:8888> | PC 客户端和同源 API 代理。 |
| 移动 H5 | <http://127.0.0.1:8889> | 移动客户端和同源 API 代理。 |
| 后端 API | <http://127.0.0.1:5000> | API 与健康检查。 |
| Grafana | <http://127.0.0.1:3000> | 监控仪表盘，需要可观测性覆盖层。 |
| Prometheus | <http://127.0.0.1:9090> | 指标采集、存储和查询，可选。 |
| Alertmanager | <http://127.0.0.1:9093> | 告警分组、静默和通知，可选。 |

任务 Redis 和 exporter 等仅开放容器内部端口，不映射到宿主机。

## 可观测性

监控栈默认可选：

- **Prometheus** 采集 API、Worker、PostgreSQL 和 Redis 指标；
- **Grafana** 把指标展示为运维仪表盘；
- **Alertmanager** 对告警分组、去重、静默，并在配置接收器后发送通知。

本地诊断时可以不启用生产覆盖层：

```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.observability.yml \
  up -d
```

监控端口仍只绑定本机。远程管理应使用 VPN、SSH 隧道或带认证的反向代理。
仪表盘、规则、数据保留和通知配置见[可观测性说明](deployment/OBSERVABILITY.md)。

## 安全模型

- MFA 密钥使用稳定的服务端加密密钥，并且设置后不再返回；
- Agent Token 经过哈希、权限范围、限流和审计控制；
- Agent 仅支持 R/W/B/N 研究、回测、提醒和模拟组合能力；
- 生产容器使用非 root 用户并移除 Linux capabilities；
- 默认端口只监听本机，公网入口应由 TLS 反向代理统一承接。

安全问题请按照 [SECURITY.md](../SECURITY.md) 私下报告。不要在公开 Issue 中提供
凭据、账户信息或可以直接利用的漏洞细节。

## 策略与集成能力

| 领域 | 当前能力 |
| --- | --- |
| 指标 | Python 图表覆盖、标记、区间和信号。 |
| 策略 | Strategy API V2 源码、校验、因子研究和回测。 |
| 加密货币 | Binance、OKX、Bitget、Bybit、Gate、HTX 公开行情。 |
| AI 提供商 | OpenRouter、OpenAI 兼容接口、Google、DeepSeek、Grok、MiniMax 和自定义端点。 |
| 自动化 | Human API、Agent Gateway、MCP、Celery、计划任务和通知。 |

开发前建议阅读[指标开发指南](trading/INDICATOR_DEV_GUIDE_CN.md)、
[策略开发指南](trading/STRATEGY_DEV_GUIDE_CN.md)和[扩展指南](architecture/EXTENSION_GUIDE.md)。

## AI Agent 与 MCP

Agent Gateway 位于 `/api/agent/v1`。仓库内的 MCP Server 可以让 Cursor、
Claude Code、Codex 等客户端调用经过授权的研究工具，而不需要获得数据提供商密钥或管理员 JWT。

Agent 仅支持 R/W/B/N 范围内的研究、回测、Indicator、提醒、自选和模拟组合能力。

详细步骤见 [MCP 配置](agent/MCP_SETUP.md)、
[Agent 快速入门](agent/AGENT_QUICKSTART.md)和
[Agent OpenAPI](agent/agent-openapi.json)。

## 开发与验证

后端使用 Python 3.12：

```bash
cd backend_api_python
python -m venv .venv
python -m pip install -r requirements-dev.txt
python -m pytest -m "not integration and not stress" --ignore=tests/release_gate -q
ruff check app scripts tests
```

仓库级检查：

```bash
python scripts/check_version.py
python scripts/check_mojibake.py
docker compose -f docker-compose.yml config -q
docker compose -f docker-compose.yml -f docker-compose.production.yml -f docker-compose.observability.yml config -q
```

修改 API 时应遵守 [API 契约规范](architecture/API_CONVENTIONS.md)，按需重新生成 OpenAPI，
并通过兼容性检查。

## 仓库结构

这个仓库包含后端应用、独立 Worker、部署编排、运维配置、工程文档和 MCP Server。
PC Web 与移动端源码位于各自独立的仓库；本仓库通过 Compose 使用它们发布的镜像。

```text
QuantDinger/
|-- .github/workflows/                 CI、安全、兼容性与发布检查
|-- backend_api_python/                后端应用及全部后端进程
|   |-- app/
|   |   |-- __init__.py                Flask 应用工厂与基础装配
|   |   |-- startup.py                 按进程职责执行启动钩子并管理进程内单例
|   |   |-- celery_app.py              Celery 应用与任务注册
|   |   |-- commands/                  迁移、调度与健康检查入口
|   |   |-- config/                    数据库、Redis 和供应商的环境配置
|   |   |-- routes/                    面向 Web 和移动端的 HTTP API 路由外壳
|   |   |   `-- agent_v1/              /api/agent/v1 下的受限 Agent Gateway API
|   |   |-- openapi/                   OpenAPI Schema、标签、注册与导出
|   |   |-- services/                  领域流程与第三方集成
|   |   |   `-- strategy_v2/           带版本的策略研究与回测服务
|   |   |-- data_sources/              原始行情数据源适配器
|   |   |-- data_providers/            行情、宏观、新闻和情绪聚合服务
|   |   |-- markets/                   市场与标的代码标准化
|   |   |-- tasks/                     有限、可重试的 Celery 任务
|   |   |-- workers/                   长期运行的 Worker 进程外壳
|   |   |-- runtime/                   进程角色与任务归属辅助模块
|   |   |-- observability/             请求上下文、指标和 HTTP 监控
|   |   `-- utils/                     数据库、缓存、认证和日志等底层工具
|   |-- migrations/                    PostgreSQL 结构与种子数据迁移
|   |-- scripts/                       后端维护和校验脚本
|   |-- tests/                         单元、契约、集成与发布门禁测试
|   |-- run.py                         本地 Flask 与 Gunicorn 应用入口
|   |-- Dockerfile                     API 和 Worker 共用的后端镜像
|   `-- docker-entrypoint.sh           容器命令分发入口
|-- docs/
|   |-- architecture/                  模块边界、并发、API 与扩展设计
|   |-- deployment/                    安装、生产部署与可观测性运维
|   |-- trading/                       策略和指标开发指南
|   |-- api/                           Human API 文档
|   `-- agent/                         Agent Gateway 与 MCP 文档
|-- mcp_server/                        独立的 QuantDinger MCP Server 包
|   |-- src/quantdinger_mcp/           MCP Server 与安全实现
|   `-- tests/                         MCP 契约与安全测试
|-- ops/                               运行与监控配置
|   |-- prometheus/                    采集配置和告警规则
|   |-- grafana/                       数据源和仪表盘自动配置
|   `-- alertmanager/                  告警路由配置
|-- scripts/                           仓库级版本、编码和安装检查
|-- docker-compose.yml                 本地源码核心服务
|-- docker-compose.ghcr.yml            预构建镜像安装服务
|-- docker-compose.production.yml      生产加固覆盖层
|-- docker-compose.observability.yml   可选监控覆盖层
|-- install.sh / install.ps1           Linux、macOS 与 Windows 安装脚本
`-- VERSION                            唯一的源码版本声明
```

### 主要请求链路

| 请求 | 链路 |
| --- | --- |
| Human API | `app/routes` → `app/services` → PostgreSQL、缓存或公开行情 |
| 有限后台任务 | API/Celery beat → Job Redis → `app/tasks` → PostgreSQL |
| 定时任务 | `app/commands/scheduler.py` → 维护或通知服务 |
| Agent/MCP | MCP 客户端 → `mcp_server` → `/api/agent/v1` → 研究服务 |

HTTP 路由负责校验与委派。有限且可重试的工作属于 Celery；定时单例工作属于 Scheduler。

### 修改功能时应该去哪里

| 修改类型 | 主要位置 | 通常还要同步更新 |
| --- | --- | --- |
| 新增或修改 HTTP 接口 | `backend_api_python/app/routes/` | `app/openapi/`、路由或契约测试、API 文档 |
| 新增业务流程 | `backend_api_python/app/services/` | 对应的服务测试 |
| 新增行情数据源 | `app/data_sources/` | 聚合服务、缓存键、数据源测试 |
| 新增看板、新闻或宏观数据聚合 | `app/data_providers/` | 路由外壳与缓存策略 |
| 新增有限异步任务 | `app/tasks/` | `celery_app.py`、队列路由、任务测试 |
| 新增长期运行进程行为 | `app/workers/`、`app/commands/` 或 `app/runtime/` | Compose 命令、健康检查、归属测试 |
| 修改数据库结构 | `backend_api_python/migrations/` | 迁移测试、发布门禁与相关文档 |
| 新增指标或告警 | `app/observability/` 与 `ops/` | 仪表盘、告警规则、可观测性文档 |
| 新增 MCP 工具 | `mcp_server/src/quantdinger_mcp/` | Agent Gateway Scope、安全测试、Agent 文档 |

Web 和移动端源码仓库独立发布 GHCR 镜像，只有从源码构建客户端时才需要 Node.js。
更详细的归属规则见[架构说明](architecture/ARCHITECTURE.md)、
[模块边界](architecture/MODULE_BOUNDARIES.md)和
[进程职责](architecture/PROCESS_ROLES_AND_TASKS.md)。

## 文档导航

全部维护中文档见 [`docs/README.md`](README.md)。

| 主题 | 文档 |
| --- | --- |
| 贡献者架构 | [架构说明](architecture/ARCHITECTURE.md) |
| 模块职责 | [模块边界](architecture/MODULE_BOUNDARIES.md) |
| 进程与任务职责 | [进程职责](architecture/PROCESS_ROLES_AND_TASKS.md) |
| 生产运行 | [生产加固](deployment/PRODUCTION_HARDENING.md) |
| 指标与告警 | [可观测性](deployment/OBSERVABILITY.md) |
| Human API 契约 | [API 规范](architecture/API_CONVENTIONS.md) |
| OpenAPI | [API 文档](api/README.md) |
| 策略开发 | [策略指南](trading/STRATEGY_DEV_GUIDE_CN.md) |
| 指标开发 | [指标指南](trading/INDICATOR_DEV_GUIDE_CN.md) |
| MCP 与 Agent | [Agent 文档](agent/README.md) |
| 云部署 | [云部署指南](deployment/CLOUD_DEPLOYMENT_CN.md) |
| 安装问题 | [故障排查](deployment/INSTALL_TROUBLESHOOTING.md) |

## 参与贡献

提交 Pull Request 前请阅读 [CONTRIBUTING.md](../CONTRIBUTING.md) 和
[DEVELOPMENT.md](../DEVELOPMENT.md)。保持路由轻量，维护 API 兼容性，把长期任务放到
正确的进程，并为高风险修改补充针对性测试。



## 许可与商业说明

- 后端源代码采用 [Apache License 2.0](../LICENSE)。
- QuantDinger 是 **Open Byte Inc** 的产品，名称、Logo、产品身份和商业授权与代码许可分开管理。
- Web 前端源码发布在
  [QuantDinger Frontend](https://github.com/OpenByteInc/QuantDinger-Vue)，适用其独立的源码可用许可证。
- 移动端 H5 和原生客户端源码发布在
  [QuantDinger Mobile](https://github.com/OpenByteInc/QuantDinger-Mobile)，适用其独立的源码可用许可证。
- 商标、品牌、署名和水印的使用规则见 [TRADEMARKS.md](../TRADEMARKS.md)。
  Apache 2.0 不授予 QuantDinger 商标使用权。

如需商业授权、前端源码、品牌授权或部署支持，可通过以下方式联系：

- 官网：[quantdinger.com](https://www.quantdinger.com)
- Telegram：[t.me/worldinbroker](https://t.me/worldinbroker)
- 邮箱：[support@quantdinger.com](mailto:support@quantdinger.com)

## 法律声明与合规提示

QuantDinger 仅用于**合法的研究、教育和合规交易场景**，不得用于欺诈、市场操纵、
逃避制裁、洗钱或其他违法活动。部署者和使用者有责任遵守所在司法辖区适用的法律法规、
许可要求、税务规则、数据提供商条款以及数据合规要求。

**本项目不提供法律、税务、投资、金融或监管建议。** 历史行情、回测结果、模拟结果、AI 输出、
指标和策略示例均不代表或保证未来表现。使用者必须独立审查研究假设、数据质量和风险限制。

本软件依照适用许可证提供，使用风险由部署者和使用者自行承担。在法律允许的最大范围内，
项目维护者和贡献者不对因使用或误用本软件产生的交易亏损、数据丢失、服务中断、第三方服务故障、
安全事件或监管后果承担责任。

## 社区与支持

<p>
  <a href="https://t.me/quantdinger"><img src="badges/telegram-group.svg" alt="Telegram"></a>
  <a href="https://discord.com/invite/tyx5B6TChr"><img src="https://img.shields.io/badge/Discord-服务器-5865F2?style=for-the-badge&logo=discord" alt="Discord"></a>
  <a href="https://youtube.com/@quantdinger"><img src="https://img.shields.io/badge/YouTube-频道-FF0000?style=for-the-badge&logo=youtube" alt="YouTube"></a>
  <a href="https://x.com/QuantDinger_EN"><img src="https://img.shields.io/badge/X-关注-000000?style=for-the-badge&logo=x" alt="X"></a>
</p>

- [官方网站](https://www.quantdinger.com)
- [贡献指南](../CONTRIBUTING.md)
- [贡献者名单](../CONTRIBUTORS.md)
- [问题反馈或功能建议](https://github.com/OpenByteInc/QuantDinger/issues)
- 邮箱：[support@quantdinger.com](mailto:support@quantdinger.com)

## 赞助商

QuantDinger 的持续开发和开源社区由以下赞助商共同支持：

<table>
  <tr>
    <td align="center" width="50%">
      <a href="https://www.atlascloud.ai/?utm_source=github&utm_medium=link&utm_campaign=quantdinger">
        <picture>
          <source media="(prefers-color-scheme: dark)" srcset="https://www.atlascloud.ai/logo-white.svg">
          <img src="https://www.atlascloud.ai/logo.svg" alt="Atlas Cloud" width="190">
        </picture>
      </a>
      <br><br>
      <strong>Atlas Cloud</strong>
      <br>
      <sub>AI 推理赞助商</sub>
    </td>
    <td align="center" width="50%">
      <a href="https://aws.amazon.com/cn/">
        <picture>
          <source media="(prefers-color-scheme: dark)" srcset="https://a0.awsstatic.com/libra-css/images/logos/aws_smile-header-desktop-en-white_59x35.png">
          <img src="https://upload.wikimedia.org/wikipedia/commons/9/93/Amazon_Web_Services_Logo.svg" alt="Amazon Web Services" width="100">
        </picture>
      </a>
      <br><br>
      <strong>Amazon Web Services</strong>
      <br>
      <sub>云基础设施赞助商</sub>
    </td>
  </tr>
</table>

衷心感谢 [Atlas Cloud](https://www.atlascloud.ai/?utm_source=github&utm_medium=link&utm_campaign=quantdinger) 为 AI 模型推理提供赞助支持，
以及 [Amazon Web Services](https://aws.amazon.com/cn/) 为 QuantDinger 社区服务所需的云基础设施提供赞助支持。

## 支持项目

如果 QuantDinger 对你有帮助，欢迎点一个 GitHub Star、参与贡献或通过打赏支持持续开发与基础设施费用。

加密货币打赏地址：

```text
0x96fa4962181bea077f8c7240efe46afbe73641a7
```

链上转账不可撤销。发送前请与项目维护者确认地址和目标网络。

## 鸣谢

QuantDinger 建立在优秀的开源生态之上，特别感谢以下项目的维护者和贡献者：

- [Flask](https://flask.palletsprojects.com/)
- [Gunicorn](https://gunicorn.org/)
- [Celery](https://docs.celeryq.dev/)
- [PostgreSQL](https://www.postgresql.org/)
- [Redis](https://redis.io/)
- [Pandas](https://pandas.pydata.org/)
- [NumPy](https://numpy.org/)
- [CCXT](https://github.com/ccxt/ccxt)
- [yfinance](https://github.com/ranaroussi/yfinance)
- [AkShare](https://github.com/akfamily/akshare)
- [Vue.js](https://vuejs.org/)
- [Ant Design Vue](https://antdv.com/)
- [KLineCharts](https://github.com/klinecharts/KLineChart)
- [ECharts](https://echarts.apache.org/)
- [Capacitor](https://capacitorjs.com/)
- [bip-utils](https://github.com/ebellocchia/bip_utils)
- [Prometheus](https://prometheus.io/)
- [Grafana](https://grafana.com/)

## P.S.——关于名字

**QuantDinger** 是向物理学家
**[薛定谔（Erwin Schrödinger）](https://zh.wikipedia.org/wiki/%E5%9F%83%E5%B0%94%E6%B8%A9%C2%B7%E8%96%9B%E5%AE%9A%E8%B0%94)**
的一份小小致敬——名字里的“-dinger”，正是“Schrödinger”的尾巴。盒子里的猫是一个思想实验；
每一个尚未验证的策略假设，都是它的小型版本。回测打开盒子，结果仍需谨慎解释。

<p align="center"><sub>如果 QuantDinger 对你有帮助，欢迎点一个 GitHub Star。</sub></p>
