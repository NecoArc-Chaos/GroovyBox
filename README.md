# GroovyBox 🎵

> A modern, cross-platform music player built with [Flet](https://flet.dev/) and Python.

> 🇬🇧 [English Version](README_EN.md)

GroovyBox 是一个用 Python 和 Flet 打造的现代音乐播放器，支持 Windows、macOS、Linux 和 Android 平台。它拥有精美的 Material 3 界面、智能元数据解析、播放列表管理和多语言支持等特性。

<p align="center">
  <img src="assets/images/icon.png" alt="GroovyBox Logo" width="128" height="128">
</p>

---

## ✨ 特性

- 🎶 **本地音乐播放** — 支持多种音频格式，流畅播放体验
- 📚 **音乐库管理** — 自动扫描并整理你的音乐收藏
- 🎨 **Material 3 设计** — 现代化 UI，支持亮/暗/跟随系统三种主题
- 🎤 **艺术家/专辑浏览** — 按艺术家和专辑维度浏览音乐
- 📋 **播放列表** — 创建和管理自定义播放列表
- 📝 **歌词支持** — 内建歌词解析器，支持 LRC 格式
- 🎨 **自适应配色** — 根据当前播放专辑封面自动提取主题色
- 🌐 **多语言** — 支持中/英文切换
- 🔍 **元数据解析** — 自动读取音频文件的标签信息
- 📦 **跨平台** — 一套代码，多端运行

## 🖥️ 截图


<img width="1584" height="893" alt="fe31cdc6-a4ea-403f-a1c0-87647484b823" src="https://github.com/user-attachments/assets/4622f17b-eb15-4c40-80e2-95f98d44bafe" />
<img width="1583" height="892" alt="b0c02b50-7a05-4399-bf6b-e0a11d0c8707" src="https://github.com/user-attachments/assets/fb44c63c-1b05-484f-89f3-b71092d250a3" />
<img width="1584" height="893" alt="02f0166e-2fec-4b6c-82e3-8428fdea4cb8" src="https://github.com/user-attachments/assets/9c4e29fc-e99b-43d9-97dd-91c39ec26557" />
<img width="1584" height="893" alt="4fcd4768-b0c5-46d6-bb17-5406fb771a43" src="https://github.com/user-attachments/assets/76ef20d7-28d8-4b6c-b8d6-73c607daa194" />
<img width="1584" height="893" alt="7226cf1f-7e3d-47fb-a5fb-1a3acb30391b" src="https://github.com/user-attachments/assets/4ee2a964-d878-4824-8b2f-7ca4b9b78b79" />


## 🚀 快速开始

### 前提条件

- Python 3.12+
- pip（Python 包管理器）

### 安装与运行

```bash
# 1. 克隆仓库
git clone https://github.com/liang-work/groovybox.git
cd groovybox

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动应用
python main.py
```

### 使用 uv（推荐，更快）

```bash
# 安装 uv
pip install uv

# 运行
uv run main.py
```

## 📦 构建

项目使用 Flet 打包工具进行跨平台构建。

```bash
# 安装 flet
export PATH="$HOME/.local/bin:$PATH"  # Linux/macOS
pip install flet

# 构建（输出到 dist 目录）
flet pack main.py --name GroovyBox
```

详细的构建配置请参考 `build-config.json` 和 `build-config-reference.md`。

## 🧩 项目结构

```
GroovyBox/
├── main.py                    # 应用入口
├── app.py                     # 应用主控制器 (GroovyBoxApp)
├── requirements.txt           # Python 依赖
├── build-config.json          # 构建配置文件
├── build-config-reference.md  # 构建配置参考文档
├── LICENSE                    # GPL-3.0 许可证
│
├── logic/                     # 逻辑层
│   ├── audio_handler.py       # 音频播放处理
│   ├── lyrics_parser.py       # LRC 歌词解析
│   ├── metadata_service.py    # 音频元数据服务
│   ├── playlist_parser.py     # 播放列表解析
│   ├── playlist_exporter.py   # 播放列表导出
│   ├── file_dialog.py         # 文件对话框
│   ├── file_drop.py           # 文件拖放处理
│   ├── encoding_helper.py     # 编码辅助
│   ├── localize.py            # 多语言本地化
│   ├── logger.py              # 日志系统
│   └── zip_importer.py        # ZIP 导入器
│
├── ui/                        # 用户界面
│   ├── shell.py               # 主界面壳（导航框架）
│   ├── screens/               # 页面屏幕
│   │   ├── library_screen.py         # 音乐库主页
│   │   ├── player_screen.py          # 全屏播放器
│   │   ├── artist_detail_screen.py   # 艺术家详情
│   │   ├── album_detail_screen.py    # 专辑详情
│   │   ├── albums_by_artist_screen.py# 按艺术家专辑列表
│   │   ├── playlist_detail_screen.py # 播放列表详情
│   │   ├── playlists_screen.py       # 播放列表管理
│   │   └── settings_screen.py        # 设置页
│   ├── tabs/                  # 标签页
│   │   ├── albums_tab.py      # 专辑标签页
│   │   └── playlists_tab.py   # 播放列表标签页
│   └── widgets/               # 可复用组件
│       ├── mini_player.py     # 迷你播放器控件
│       ├── track_tile.py      # 曲目条目组件
│       └── universal_image.py # 通用图片组件
│
├── data/                      # 数据层
│   ├── db.py                  # 数据库初始化与管理
│   ├── models.py              # 数据模型
│   ├── track_repository.py    # 曲目数据仓库
│   └── playlist_repository.py # 播放列表数据仓库
│
├── assets/                    # 资源文件
│   ├── images/
│   │   └── icon.jpg           # 应用图标
│   └── locales/
│       ├── zh.json            # 中文翻译
│       └── en.json            # 英文翻译
│
└── scripts/                   # 构建脚本
    ├── do_build.py            # 自动化构建脚本
    └── package_windows.nsi    # Windows 安装包 NSIS 脚本
```

## ⚙️ 配置

应用启动后会自动创建 SQLite 数据库用于存储音乐库和设置。你可以通过设置界面调整：

- **语言**：中文 / English
- **主题模式**：亮色 / 暗色 / 跟随系统
- **日志级别**：控制日志输出详细程度

## 🧪 技术栈

| 技术 | 用途 |
|------|------|
| [Flet](https://flet.dev/) | 跨平台 UI 框架 |
| [flet-audio](https://github.com/flet-dev/flet-audio) | 音频播放支持 |
| [mutagen](https://mutagen.readthedocs.io/) | 音频元数据解析 |
| [Pillow](https://python-pillow.org/) | 图像处理 |
| [colorthief](https://github.com/fengsp/color-thief-py) | 专辑封面颜色提取 |
| [httpx](https://www.python-httpx.org/) | HTTP 客户端 |
| SQLite | 本地数据存储 |

## 📄 许可证

本项目基于 [GNU General Public License v3.0](LICENSE) 开源。

## 🚨 注意事项

 本项目为[ Flutter 版 GroovyBox](https://github.com/Solsynth/GroovyBox) 的重构版，本项目的品质、存在的问题，与原开发者 NightSystem 和 [LittleSheep2Code](https://github.com/LittleSheep2Code) 无关，特此声明。
 

## 📖 项目历史

  在 2025 年 8 月 11 日，NightSystem 在 sn(一个社区)发帖求助，希望有人能帮助 TA 完成初版 GroovyBox(即Swift版) 并上架。后面，LittleSheep2Code表示愿意看看，此后，该应用成功在 TestFlight 可用，但没过多久，就因为开发者繁忙而废弃。到 25 年底，LittleSheep2Code 重新制作了 Flutter 版的 GroovyBox，但是没过多久，就再次停更。在几个月后，就有了这个项目。
  

## 👥 贡献者
  
  - [luolingy](https://github.com/luolingy)
  - [ZhiH](https://github.com/ZhiH2333)
  - [符跃 万界](https://qm.qq.com/q/vMovFQlrj2)(图标设计)
---

<p align="center">
  Made liang-work with ❤️ and Python
</p>
