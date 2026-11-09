# BlueFrame Studio

BlueFrame Studio 是本地优先的 Windows 桌面视频生产应用。它在打包旧版应用旁独立实现，旧版文件只作为行为与数据证据，本仓库从不修改它们。

## 状态

完整范围（阶段 0–8）已实现并通过自动化验收：

- 旧版 `video.db` 只读预检与幂等导入
- 媒体探测、本地 ASR、短剧剧情分析
- 火山引擎方舟远程 AI 与 Seed-TTS 2.0 解说
- 高光/重组时间线、主成片渲染与交付
- 电影解说、视频变体与本地素材中心
- 直播切片（抖音授权地址）
- 隐私安全诊断、故障恢复矩阵、Windows 离线打包与安装器

验收结果见 [docs/acceptance-report.md](docs/acceptance-report.md)，已知边界见 [docs/limitations.md](docs/limitations.md)，部署与运维见 [docs/operator-guide.md](docs/operator-guide.md)。

## 开发

```powershell
.\scripts\verify.ps1
.\scripts\smoke.ps1
.\scripts\dev.ps1
```

`dev.ps1` 构建 Vue 应用并打开 Native pywebview 窗口。每次启动的 API 令牌通过内存桥接传递，不写入 URL 或浏览器存储。密钥、媒体输出、数据库和本地环境文件不得提交。

## 离线打包与安装

```powershell
$env:BLUEFRAME_PYTHON311 = "<Python 3.11 x64>\python.exe"
.\scripts\build-windows.ps1

.\scripts\install-windows.ps1 -PackageDir .\dist\BlueFrameStudio
.\scripts\verify-package.ps1 -PackageDir .\dist\BlueFrameStudio
```

- 安装版数据位于 `%LOCALAPPDATA%\BlueFrameStudio\data`，卸载不会删除用户数据。
- 本地 API 仅绑定 `127.0.0.1`，要求每次启动随机令牌，窗口关闭时停止。
- 远程 AI/TTS 仅在用户于“系统设置”配置火山引擎凭据后启用；密钥保存在 Windows 凭据管理器。
- 完整离线包包含 FFmpeg 与 FunASR 三套模型，首次启动不需要联网。

## 安全与隐私

- 诊断包默认排除视频、音频、字幕全文、绝对路径、账号资料、Cookie、Token 与 API Key。
- 文件 API 只允许访问已登记的项目根目录，拒绝路径穿越。
- FFmpeg 命令全部由结构化参数生成，不拼接 shell 字符串。
- 直播录制只接受用户确认拥有权利的播放地址，不抓取页面、不绕过付费或 DRM。
