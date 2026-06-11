# 🧟‍♂️ ZombieBot - 《向僵尸开炮》桌面自动化挂机助手

![Platform: macOS | Windows](https://img.shields.io/badge/Platform-macOS%20%7C%20Windows-blue)
![Python: 3.9+](https://img.shields.io/badge/Python-3.9%2B-green)
![Tech: EasyOCR + PyAutoGUI](https://img.shields.io/badge/Tech-EasyOCR%20%7C%20PyAutoGUI-orange)

ZombieBot 是一款基于 Python 开发的电脑端微信小游戏自动化挂机辅助脚本。
它告别了传统“找图定位”的死板逻辑，采用 **AI 光学字符识别 (OCR)** 技术，自动寻找并点击游戏内的文字按钮。主打一个“抗干扰、强兼容、解放双手”。

---

## ✨ 核心特性

- 👀 **AI 视觉识别：** 接入 `EasyOCR` 大模型，直接“看懂”屏幕文字。无论游戏界面更新、按钮换色还是分辨率改变，只要文字还在就能精准点击。
- 💻 **双平台原生支持：** 完美兼容 **macOS** 与 **Windows**。内置智能算法自动处理 Mac Retina 屏幕缩放与 Windows HiDPI 偏移问题。
- 📦 **全自动环境搭建：** 告别繁琐的 `pip install`。脚本内置依赖自检守护程序，首次运行会自动拉取并安装所有缺失的第三方库。
- 🎯 **智能标定与容错：** 首次使用只需按提示指认一次游戏区域，即可永久保存配置。自带强杀微信小游戏窗口、焦点抢占、异常自动重开等防卡死机制。

---

## 🚀 快速开始

### 方式一：源码运行（面向开发者）

1. 确保你的电脑已安装 Python 3.9 或以上版本。
2. 下载本项目源码到本地。
3. 打开终端（Terminal / CMD），进入项目目录，直接运行：
   ```bash
   python main.py
   ```
4. maybe need:
   管理员权限运行（最重要）： Windows 版微信的安全级别较高。如果你的脚本是用普通权限运行的，系统可能会阻止 pyautogui 向微信小游戏发送 Alt 和 F4 这种系统级组合键。
   解决办法： 用户在运行打包好的 ZombieBot.exe 时，必须右键点击它 -> 选择“以管理员身份运行”。
   输入法中英文状态： 如果用户的电脑当前处于中文输入法状态，按下 Alt 键可能会误触发输入法的菜单栏快捷键，导致 F4 失效。
   解决办法： 挂机前，确保把系统的输入法切回 纯英文（ENG） 状态。
