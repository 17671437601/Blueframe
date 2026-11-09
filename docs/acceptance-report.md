# BlueFrame Studio 全范围验收报告

- 验收日期：2026-11-09
- 分支：`feature/complete-scope`
- 环境：Windows 11 x64（10.0.22631）、Python 3.11.9（离线构建）、Node.js 22.16.0
- 范围：旧版导入、诊断、离线打包、故障与性能矩阵、安装器与全量回归

## 1. 自动化回归

| 套件 | 命令 | 结果 |
| --- | --- | --- |
| 后端 | `backend\.venv\Scripts\python.exe -W error::DeprecationWarning -m pytest -q` | 140 passed，1 skipped（Windows 无 symlink 权限） |
| 前端单测 | `npm test -- --run` | 20 passed（15 个测试文件） |
| 前端构建 | `npm run build` | `vue-tsc --noEmit` 与 Vite 生产构建通过 |
| 浏览器 E2E | `npm run test:e2e -- e2e/shell.spec.ts` | 3 passed |
| 桌面 | `desktop\.venv\Scripts\python.exe -W error::DeprecationWarning -m pytest -q` | 12 passed |
| 打包自检 | `scripts\verify-package.ps1` | 通过（窗口化进程按退出码判定） |

## 2. 故障与性能矩阵

`backend/tests/hardening/` 共 8 类场景、17 项测试，全部通过：

| 场景 | 测试文件 | 验证点 |
| --- | --- | --- |
| 磁盘写满 | `test_disk_full.py` | 渲染异常时 artifact 标记 `failed`，不覆盖既有交付 |
| 进程杀死 | `test_process_kill.py` | 租约过期后任务恢复为 `interrupted` 并重新入队 |
| 网络离线 | `test_offline_provider.py` | 远程调用有界重试、错误脱敏、不泄露密钥 |
| 损坏媒体 | `test_corrupt_media.py` | 空文件/损坏文件探测失败可定位，不崩溃 |
| 长路径 | `test_long_path.py` | 超过 260 字符与深层中文目录可读写 |
| 并发 | `test_concurrency.py` | 并发创建/领取作业无 `IntegrityError`、无重复领取 |
| 大项目 | `test_large_project.py` | 大量旧项目导入与大量作业排队在可接受时间内完成 |
| 重启 | `test_restart.py` | 从持久化 checkpoint 重启后不重复计费、不重复交付 |

## 3. 安装器验收

使用 `dist\BlueFrameStudio` 全量组件安装到临时目录：

1. 安装器校验 `resource-manifest.json` 签名与全部文件 SHA-256。
2. 安装后执行 `BlueFrameStudio.exe --smoke`，通过。
3. 相同清单与组件重复安装，输出“已安装”，幂等通过。
4. `-Uninstall` 删除安装目录与快捷方式，目标目录确认不存在。
5. 卸载只处理安装目录；用户数据目录按设计保留，需手动清理。

## 4. 验收中发现并修复的缺陷

- 打包版默认数据目录原本位于 `_MEIPASS\.blueframe-data`（即安装目录 `_internal` 下），卸载会连带删除用户数据库。
- 修复：冻结运行时改用 `%LOCALAPPDATA%\BlueFrameStudio\data`；开发运行仍使用仓库 `.blueframe-data`。
- 回归：新增 `test_packaged_launcher_keeps_user_data_outside_the_install_tree`，桌面套件 12 项通过。

- 窗口化 PyInstaller 子进程中 `sys.stdout` / `sys.stderr` 为 `None`，uvicorn 日志初始化调用 `isatty()` 崩溃，本地服务无法就绪，界面显示离线。
- 修复：`desktop/blueframe_desktop/processes.py` 新增 `_ensure_std_streams()`，子进程启动前将缺失流重定向到空设备。
- 回归：新增 `test_ensure_std_streams_restores_windowed_package_children`。

- WebView2 加载 `file://` 页面时发送 `Origin: file://`，后端 CORS 仅放行 `null`，全部 API 预检被拦截。
- 修复：`backend/blueframe/app.py` 的 CORS 同时放行 `null` 与 `file://`。
- 回归：新增 `test_file_origin_preflight_allows_desktop_session_header`，覆盖两种 Origin。

## 5. 黄金媒体与 Provider 假响应

- 渲染黄金测试使用 FFmpeg `lavfi` 合成横屏/竖屏、含/不含音轨素材，校验时长、分辨率与音轨。
- 变体黄金测试校验确定性配方与可播放输出。
- 火山方舟与 TTS 使用固定假响应，验证请求结构、重试、错误分类与脱敏；未产生真实计费调用。
- 本地 ASR 运行时已打包并通过导入自检；本次未执行真实音频转写。
- 未使用真实授权剧集数据集，质量阈值校准情况见 `docs/limitations.md`。

## 6. 交付物

- `dist/BlueFrameStudio/`：PyInstaller 离线目录产物。
- `dist/BlueFrameStudio-Windows-x64.zip`：约 1.9 GB 离线分发包。
- `scripts/install-windows.ps1`：安装、组件选择、完整性校验、幂等安装、安装后冒烟与卸载。
- `docs/operator-guide.md`：部署、配置、备份、恢复与故障排查。
- `docs/limitations.md`：账号、AI 质量、直播平台、导入范围等已知边界。

## 7. 结论

完整范围的本地能力、故障恢复、隐私诊断、离线打包与安装流程均通过自动化验收。剩余边界集中在真实账号服务、真实黄金数据集质量校准、更多直播平台和代码签名/自动更新，已记录为已知限制，不阻塞本地离线版本交付。
