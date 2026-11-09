# BlueFrame Studio 运维与操作指南

本指南面向离线部署、日常使用和故障排查人员。应用为本地优先的 Windows 桌面程序：业务数据、任务队列、ASR 模型与 FFmpeg 均在本机运行；只有配置了火山引擎凭据后才会发起远程 AI/TTS 请求。

## 1. 系统要求

- Windows 10/11 x64。
- 四核 CPU、16 GB 内存、20 GB 可用磁盘空间（离线包解压后约 1.9 GB）。
- NVIDIA GPU 为可选加速，不是运行前提；硬件编码不可用时自动回退软件编码。
- 安装与首次启动不需要联网；远程 AI、TTS 和直播拉流需要网络。

## 2. 安装

离线包为 `BlueFrameStudio-Windows-x64.zip`，解压后使用 `scripts/install-windows.ps1` 安装：

```powershell
# 全量安装（应用 + ASR 模型 + FFmpeg），默认安装到 %LOCALAPPDATA%\Programs\BlueFrameStudio
.\install-windows.ps1 -PackageDir .\BlueFrameStudio

# 自定义目录并跳过开始菜单快捷方式
.\install-windows.ps1 -PackageDir .\BlueFrameStudio -InstallDir D:\Apps\BlueFrameStudio -NoShortcut

# 仅安装应用（需要另行提供 models 与 third-party，否则启动自检会失败）
.\install-windows.ps1 -PackageDir .\BlueFrameStudio -Components app
```

安装器行为：

- 校验 `resource-manifest.json` 的签名与每个文件的 SHA-256，任一不匹配立即终止。
- 相同清单与组件重复安装时直接返回“已安装”，不会重复复制。
- 安装完成后执行 `BlueFrameStudio.exe --smoke`，失败则抛出错误。
- 组件选择：`app`、`models`、`third-party`、`full`（默认）。`app` 为必选。

## 3. 启动与界面

- 通过开始菜单快捷方式或安装目录下的 `BlueFrameStudio.exe` 启动。
- 首次窗口 1366×768，最小 1024×700，窄窗口会自动降级布局。
- 启动时桌面壳会：执行数据库迁移、选择空闲回环端口、启动本地 FastAPI 服务、生成每次启动随机会话令牌，并打开 Native 窗口。
- 本地 API 只监听 `127.0.0.1`，未携带会话令牌的请求返回 401。

导航包括：工作台、短剧生产、电影解说、视频变体、直播切片、素材中心、任务中心、系统设置。

## 4. 数据目录与备份

| 场景 | 数据目录 |
| --- | --- |
| 开发运行 | 仓库根目录 `.blueframe-data` |
| 安装版 | `%LOCALAPPDATA%\BlueFrameStudio\data` |

目录内容：

- `blueframe.db`：SQLite 主数据库（项目、任务、分析、时间线、渲染记录等）。
- `providers.json` / `tts-provider.json`：火山方舟与 TTS 的非敏感配置（只保存凭据引用，不保存密钥）。
- `tts-cache/`：TTS 音频缓存。
- `diagnostics/`：导出的安全诊断包。

备份：退出应用后整体复制上述数据目录即可。迁移到新机器时，先安装同版本应用，再用备份目录替换默认数据目录。

## 5. 配置远程 AI（火山引擎 Ark）

入口：系统设置 → 智能服务设置。

1. 填写模型或推理接入点 ID（例如 `ep-2026...`）。
2. 填写 API Key；已配置时留空可保留原密钥。
3. 保存后显示“已配置”。

说明：

- 使用官方 Responses API（`https://ark.cn-beijing.volces.com/api/v3/responses`），要求 JSON Schema 严格输出。
- 密钥写入 Windows 凭据管理器（目标名 `BlueFrame/provider:volcengine-ark`），不会写入项目文件、日志或前端缓存。
- 默认仅发送转写文本；原始视频与关键帧不会随分析请求上传。
- 未配置凭据时，分析类作业会明确失败，不会静默降级为本地伪分析。

## 6. 配置语音合成（火山引擎 Seed-TTS 2.0）

入口：系统设置 → 火山引擎 Seed-TTS 2.0。

- 填写 API Key；默认音色为 `zh_female_vv_uranus_bigtts`，资源 ID 为 `seed-tts-2.0`。
- 合成结果按文本、音色、语速、模型与版本做内容寻址缓存，命中缓存不重复计费。
- 密钥目标名为 `BlueFrame/provider:volcengine-tts`。

## 7. 旧版数据导入

入口：系统设置 → 旧版项目迁移 → “选择并预览旧版数据库”。

1. 选择旧版 `video.db`，程序以只读 URI（`mode=ro&immutable=1`）打开，绝不写回。
2. 预览报告列出可导入项目、源文件是否存在、被排除的表和警告。
3. 勾选确认后执行导入；导入按源文件哈希 + 旧表 + 旧 ID 幂等，重复导入会跳过而不是覆盖。
4. 每次导入记录 `legacy-v1` 迁移版本与来源哈希。

被排除的表：`account`、`admin`、`key`、`notice`。账号、会员、密钥、Cookie 和无法验证归属的数据永不导入。

## 8. 任务、恢复与并发

- 本地 worker 单线程顺序领取任务，任务租约 60 秒。
- 进程异常退出或租约过期后，恢复逻辑会把任务标记为 `interrupted`，未超过最大尝试次数则重新入队，超过则标记 `failed`。
- 渲染先写入任务级临时文件，FFprobe 校验通过后再原子替换交付文件；失败不会破坏上一版交付。
- 取消在安全边界生效；变体批量任务允许部分成功，并可仅重试失败项。
- 磁盘写满、FFmpeg 失败、媒体损坏等异常会把任务置为 `failed` 并保留明确阶段与错误码。

## 9. 诊断与故障排查

入口：系统设置 → 隐私诊断 → “导出安全诊断包”。

- 诊断包写入数据目录 `diagnostics/`，文件名形如 `blueframe-diagnostics-YYYYMMDD-HHMMSS.zip`。
- 内容仅含 `system.json`、`metrics.json`、`jobs.json` 和清单，包含阶段、耗时、状态、错误码、Token 用量等指标。
- 默认排除视频、音频、字幕全文、任务参数、绝对路径、账号资料、Cookie、Token 与 API Key。
- 导出采用临时文件 + 原子替换，失败不会留下半成品。

常见问题：

| 现象 | 排查 |
| --- | --- |
| 启动即退出 | 运行安装目录下 `BlueFrameStudio.exe --smoke` 查看缺失资源或运行时错误 |
| 提示资源清单无效 | 重新解压离线包；不要手动修改 `_internal` 下文件 |
| 分析任务失败且提示未配置 | 在系统设置中配置 Ark 模型与 API Key |
| TTS 失败 | 检查 TTS API Key、音色与网络；查看任务错误码与诊断包 |
| 端口被占用 | 应用每次选择空闲回环端口；若持续失败，检查本机安全软件是否拦截回环监听 |
| 长路径失败 | 应用层已覆盖长路径测试；系统仍需启用 Windows 长路径策略（`LongPathsEnabled=1`） |
| 磁盘写满 | 清理项目工作目录与 `tts-cache/`；失败任务不会覆盖既有交付 |
| 旧库无项目 | 旧表必须包含预期列；部分或未知 schema 会跳过并在预览中给出警告 |

## 10. 升级与卸载

升级：解压新离线包后再次运行安装器。安装器按清单哈希判断是否需要更新，覆盖应用与资源；用户数据位于 `%LOCALAPPDATA%\BlueFrameStudio\data`，不会被覆盖。

卸载：

```powershell
.\install-windows.ps1 -PackageDir .\BlueFrameStudio -InstallDir <原安装目录> -Uninstall
```

- 卸载只删除安装目录与开始菜单快捷方式；缺少 `.blueframe-install.json` 标记时拒绝删除，避免误删其他目录。
- 用户数据目录会保留，需要时手动删除 `%LOCALAPPDATA%\BlueFrameStudio`。

## 11. 安全说明

- 本地 API 仅绑定 `127.0.0.1`，使用每次启动随机令牌；桌面桥接密钥不会进入 URL 或浏览器存储。
- 文件 API 只允许访问已登记的项目根目录，拒绝路径穿越。
- 所有 FFmpeg 命令由结构化参数生成，不拼接 shell 字符串。
- 远程调用日志不记录 AK/SK、Token、完整字幕或账号凭据。
- 直播录制只接受用户主动提供且确认拥有权利的播放地址，不抓取页面、不提取私有签名、不绕过付费或 DRM。
