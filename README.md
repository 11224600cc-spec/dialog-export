# Dialog Export — DeepSeek 聊天导出工具

> 基于 **PySide6 + Playwright** 的 DeepSeek 对话导出桌面应用，支持全量消息提取与数据完整性验证。

![Python](https://img.shields.io/badge/Python-3.12-blue)
![PySide6](https://img.shields.io/badge/UI-PySide6-41cd52)
![License](https://img.shields.io/badge/License-MIT-green)

## ✨ 功能

- 🚀 **一键启动** — 自动打开 Chromium 浏览器并加载 DeepSeek 页面
- 🔍 **全量提取** — 通过 CSS Hack 方案绕过虚拟列表限制，完整获取所有消息
- ✅ **自动验证** — 导出后自动对比页面原始条数，确保零丢失
- 📁 **文件管理** — 内置预览、删除功能，支持 JSON / TXT 格式
- 🎨 **毛玻璃 UI** — Catppuccin Mocha 暗色主题，自定义壁纸系统
- 🌊 **流畅动画** — 壁纸淡入淡出、粒子庆祝、弹入提示框、底部波形装饰
- 💫 **透玻璃按钮** — 现代化玻璃质感控件，卡片间渐变分隔线

## 📦 下载

前往 [Releases](../../releases) 页面下载 `Dialog Export.exe`（~84MB）。

## ⚙️ 使用说明

1. 运行 `Dialog Export.exe`
2. 点击 **🚀 启动浏览器** — 自动启动 Chromium 并加载 DeepSeek
3. 在浏览器中登录并进入目标对话
4. 点击 **▶ 开始抓取** — 自动提取全部消息
5. 导出完成后查看 `output/` 目录下的 JSON/TXT 文件

### 技术原理

DeepSeek 使用 React 虚拟列表（`ds-virtual-list`），DOM 只渲染可见区域的消息。本工具通过修改滚动容器 CSS 样式（`height = scrollHeight` + `overflowY: visible`）欺骗虚拟列表渲染全部 DOM 节点，从而完整提取所有消息。

## 🔧 开发环境

```bash
# 创建虚拟环境
python -m venv venv
venv\Scripts\activate

# 安装依赖
pip install playwright pyinstaller PySide6
playwright install chromium

# 运行
python deepseek_exporter_gui.py

# 打包
pyinstaller --onefile --windowed --noconfirm --name "Dialog Export" --icon "tujue.ico" --add-data "default_wallpaper.png;." deepseek_exporter_gui.py
```

## 🛠️ 技术栈

| 技术 | 用途 |
|---|---|
| Python 3.12 | 主逻辑 |
| PySide6 (Qt6) | 毛玻璃 GUI 框架 |
| Playwright | 浏览器自动化控制 |
| PyInstaller | 单文件 exe 打包 |

## 📄 License

[MIT License](LICENSE)
