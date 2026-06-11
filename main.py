"""
ZombieBot - 《向僵尸开炮》微信小游戏 桌面自动化挂机脚本
适用平台: macOS / Windows
依赖安装（通用）:
    pip install pyautogui easyocr pillow opencv-python-headless numpy
Windows 额外依赖:
    pip install pygetwindow
"""

import sys
import subprocess
import platform

# ──────────────────────────────────────────────
# 【自动安装依赖】— 必须在所有第三方 import 之前运行
# ──────────────────────────────────────────────

def _auto_install():
    """检测并自动安装所有依赖，用户无需手动 pip install。"""

    # 通用依赖（Mac + Windows 都需要）
    packages = [
        ("pyautogui",                 "pyautogui"),
        ("easyocr",                   "easyocr"),
        ("PIL",                       "pillow"),
        ("cv2",                       "opencv-python-headless"),
        ("numpy",                     "numpy"),
    ]

    # Windows 额外依赖
    if platform.system() == "Windows":
        packages.append(("pygetwindow", "pygetwindow"))

    missing = []
    for import_name, pip_name in packages:
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pip_name)

    if not missing:
        return  # 全部已安装，直接返回

    print("=" * 50)
    print(f"  [依赖] 检测到 {len(missing)} 个缺失的库，自动安装中...")
    print(f"  {missing}")
    print("=" * 50)

    for pkg in missing:
        print(f"  → 安装 {pkg} ...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", pkg, "--quiet"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            print(f"  ✅ {pkg} 安装成功")
        else:
            print(f"  ❌ {pkg} 安装失败，错误信息：")
            print(result.stderr.strip())
            print(f"  请手动运行: pip install {pkg}")

    print("[依赖] 所有依赖处理完毕，继续启动...\n")


_auto_install()  # 在任何第三方 import 之前执行

# ── 依赖安装完成后再导入第三方库 ──────────────────
import time
import random
import os
import json
from PIL import ImageDraw
import pyautogui
import numpy as np
import easyocr

# ──────────────────────────────────────────────
# 【全局配置】
# ──────────────────────────────────────────────

# pyautogui 安全设置
pyautogui.FAILSAFE = True          # 鼠标移至左上角可紧急中断
pyautogui.PAUSE = 0.1              # 每步操作后微停顿

# 等待时间（秒）
WAIT_AFTER_START   = 1             # 步骤 A: 点击开始后等待
WAIT_BEFORE_REOPEN = 2             # 步骤 C: 关闭窗口后等待
WAIT_GAME_LOADING  = 10            # 重新进入后等待游戏加载

# 随机偏移参数
OFFSET_RANGE       = 3             # 点击坐标 ± 像素
MOVE_TIME_MIN      = 0.2           # 鼠标移动最短时间
MOVE_TIME_MAX      = 0.5           # 鼠标移动最长时间

# 当前操作系统（启动时由用户确认，见入口处）
IS_MAC = platform.system() == "Darwin"   # 默认自动检测，可被用户选择覆盖

# ──────────────────────────────────────────────
# 【EasyOCR 初始化】
# ──────────────────────────────────────────────

print("[初始化] 加载 EasyOCR 模型（首次可能需要下载）...")
reader = easyocr.Reader(["ch_sim", "en"], gpu=False)
print("[初始化] EasyOCR 模型加载完毕。")


# ──────────────────────────────────────────────
# 【屏幕缩放倍数】
# ──────────────────────────────────────────────

def get_screen_scale() -> float:
    """
    动态计算屏幕的 HiDPI 缩放倍数。
    - macOS Retina: 截图物理宽 / 逻辑宽 ≈ 2.0
    - Windows 高 DPI: pyautogui 在 Windows 下截图与逻辑坐标一致，通常返回 1.0
                      若 Windows 开启了缩放，通过 ctypes 修正。
    """
    logical_w, _ = pyautogui.size()
    screenshot = pyautogui.screenshot()
    physical_w = screenshot.width
    scale = physical_w / logical_w

    # Windows 下 pyautogui.screenshot() 已经按逻辑像素返回，scale 通常为 1.0
    # 但若用户开启了系统显示缩放（125%/150%），需通过 ctypes 获取真实 DPI 比
    if not IS_MAC and platform.system() == "Windows":
        try:
            import ctypes
            # 获取系统 DPI（96 = 100%，120 = 125%，144 = 150%）
            dpi = ctypes.windll.user32.GetDpiForSystem()
            scale = dpi / 96.0
            print(f"[缩放] Windows DPI={dpi}，缩放倍数={scale:.2f}x")
            return scale
        except Exception:
            pass

    print(f"[缩放] 逻辑宽={logical_w}px  截图宽={physical_w}px  缩放倍数={scale:.2f}x")
    return scale

# 启动时计算一次，全局复用（分辨率不变就不需要反复算）
SCREEN_SCALE: float = get_screen_scale()


# ──────────────────────────────────────────────
# 【核心函数】
# ──────────────────────────────────────────────

def click_text(keyword: str, confidence_threshold: float = 0.3,
               debug: bool = True,
               region: tuple | None = None) -> bool:
    """
    全屏（或指定区域）截图 → EasyOCR 识别 → 找到包含 keyword 的文字框 → 点击其中心。

    Args:
        keyword:              要查找的关键词（支持部分匹配）。
        confidence_threshold: OCR 置信度阈值。
        debug:                True 时保存标注截图到 debug_click.png。
        region:               限定扫描区域 (left, top, width, height)，单位为逻辑像素。
                              None 表示全屏。缩小范围可显著提升速度和准确率。

    Returns:
        True 如果成功找到并点击，False 如果未找到。
    """
    # 截图（全屏或指定区域）
    screenshot = pyautogui.screenshot(region=region)
    img_array = np.array(screenshot)

    # 保存区域截图，方便核查 OCR 扫的是不是正确位置
    if debug:
        try:
            dbg_region_path = os.path.join(os.path.dirname(__file__), "debug_region.png")
            screenshot.save(dbg_region_path)
        except Exception:
            pass

    # EasyOCR 识别
    results = reader.readtext(img_array)

    # 打印所有识别结果，方便调试
    if results:
        print(f"  [OCR全部结果] 共{len(results)}条: " +
              " | ".join(f"「{t}」({c:.2f})" for _, t, c in results))
    else:
        print("  [OCR全部结果] 未识别到任何文字")

    for (bbox, text, confidence) in results:
        if keyword in text and confidence >= confidence_threshold:
            # 文字框中心（相对于截图左上角，物理像素）
            xs = [point[0] for point in bbox]
            ys = [point[1] for point in bbox]
            phys_cx = int((min(xs) + max(xs)) / 2)
            phys_cy = int((min(ys) + max(ys)) / 2)

            # 转换为逻辑像素，并加上区域偏移
            region_offset_x = region[0] if region else 0
            region_offset_y = region[1] if region else 0
            cx = int(phys_cx / SCREEN_SCALE) + region_offset_x
            cy = int(phys_cy / SCREEN_SCALE) + region_offset_y

            # 随机偏移 + 移动时间
            target_x = cx + random.randint(-OFFSET_RANGE, OFFSET_RANGE)
            target_y = cy + random.randint(-OFFSET_RANGE, OFFSET_RANGE)
            move_duration = random.uniform(MOVE_TIME_MIN, MOVE_TIME_MAX)

            print(f"  [OCR] 找到「{text}」(置信度 {confidence:.2f})，"
                  f"逻辑点击=({target_x}, {target_y})"
                  + (f" [区域 {region}]" if region else " [全屏]"))

            # 调试截图
            if debug:
                try:
                    dbg_img = screenshot.copy()
                    draw = ImageDraw.Draw(dbg_img)
                    r = 20
                    draw.ellipse([phys_cx-r, phys_cy-r, phys_cx+r, phys_cy+r],
                                 outline="red", width=4)
                    draw.rectangle([int(min(xs)), int(min(ys)),
                                    int(max(xs)), int(max(ys))],
                                   outline="blue", width=2)
                    dbg_path = os.path.join(os.path.dirname(__file__), "debug_click.png")
                    dbg_img.save(dbg_path)
                    print(f"  [调试] 截图已保存 → {dbg_path}")
                except Exception as dbg_e:
                    print(f"  [调试] 截图保存失败: {dbg_e}")

            # 移动 + 点击
            pyautogui.moveTo(target_x, target_y, duration=move_duration)
            time.sleep(0.15)
            pyautogui.click(target_x, target_y)
            time.sleep(0.05)
            pyautogui.click(target_x, target_y)
            return True

    print(f"  [OCR] 未找到关键词「{keyword}」。")
    return False


def close_window():
    """
    关闭当前最前端窗口。
    macOS: Command+W | Windows: Alt+F4
    """
    if IS_MAC:
        pyautogui.hotkey("command", "w")
        print("  [关闭窗口] 已发送 Mac 关闭快捷键 (Cmd+W)。")
    else:
        # 🌟 Windows 增强版关闭逻辑：
        # 有时快捷键按得太快系统检测不到，这里改用分步按下，并增加微小延迟
        try:
            print("  [关闭窗口] 正在向 Windows 游戏窗口发送 Alt+F4...")
            pyautogui.keyDown('alt')
            time.sleep(0.1)
            pyautogui.press('f4')
            time.sleep(0.1)
            pyautogui.keyUp('alt')
            print("  [关闭窗口] Alt+F4 发送完毕。")
        except Exception as e:
            print(f"  [关闭窗口] 发送快捷键失败: {e}")
            
    time.sleep(1.0)  # 留出 1 秒给窗口完全销毁，防止下一轮循环重叠

def bring_game_to_front():
    """
    将微信小游戏窗口置于前台。
    macOS : osascript 找到标题不含"微信"的浮动窗口并 AXRaise。
    Windows: pygetwindow 遍历所有窗口，找标题不含"微信"但属于 WeChat 进程的窗口并激活。
    """
    if IS_MAC:
        script = """
tell application "System Events"
    tell process "WeChat"
        set frontmost to true
        repeat with w in windows
            if name of w does not contain "微信" then
                perform action "AXRaise" of w
                exit repeat
            end if
        end repeat
    end tell
end tell
"""
        try:
            import subprocess
            subprocess.run(["osascript", "-e", script], check=True,
                           capture_output=True, timeout=5)
            print("  [前台] 已将小游戏窗口提至前台。")
        except Exception as e:
            print(f"  [前台] osascript 失败，点击屏幕中央降级激活: {e}")
            sw, sh = pyautogui.size()
            pyautogui.click(sw // 2, sh // 2)

    else:
        # Windows：用 pygetwindow 查找微信小游戏窗口
        try:
            import pygetwindow as gw
            all_wins = gw.getAllWindows()
            # 微信主窗口标题通常是"微信"，小游戏窗口标题是游戏名
            game_wins = [w for w in all_wins
                         if w.title and "微信" not in w.title
                         and w.title not in ("", "Program Manager")
                         and w.visible]
            if game_wins:
                win = game_wins[0]
                win.activate()
                print(f"  [前台] Windows：已激活窗口「{win.title}」。")
            else:
                print("  [前台] Windows：未找到小游戏窗口，点击屏幕中央降级激活。")
                sw, sh = pyautogui.size()
                pyautogui.click(sw // 2, sh // 2)
        except ImportError:
            print("  [前台] pygetwindow 未安装，请运行: pip install pygetwindow")
            sw, sh = pyautogui.size()
            pyautogui.click(sw // 2, sh // 2)
        except Exception as e:
            print(f"  [前台] Windows 激活失败: {e}")

    time.sleep(0.5)


# ──────────────────────────────────────────────
# 【各步骤】
# ──────────────────────────────────────────────

# 搜索结果列表区域（逻辑像素），从 config.json 自动读取，首次运行时引导标定后自动保存。
# 格式: (left, top, width, height)，无需手动修改代码。
GAME_LIST_REGION: tuple | None = None

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")


def load_config():
    """从 config.json 读取已保存的配置。"""
    global GAME_LIST_REGION
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            if "game_list_region" in cfg:
                GAME_LIST_REGION = tuple(cfg["game_list_region"])
                print(f"[配置] 已加载游戏列表区域: {GAME_LIST_REGION}")
        except Exception as e:
            print(f"[配置] 读取 config.json 失败: {e}")


def save_config():
    """将当前配置写入 config.json。"""
    try:
        cfg = {}
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        cfg["game_list_region"] = list(GAME_LIST_REGION)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        print(f"[配置] 区域已保存到 {CONFIG_PATH}")
    except Exception as e:
        print(f"[配置] 保存失败: {e}")


def calibrate_game_region():
    """
    交互式标定游戏列表区域，标定结果自动保存到 config.json，下次无需重新标定。
    """
    global GAME_LIST_REGION
    while True:
        print("\n[标定] 请将鼠标移到游戏列表区域的【左上角】，3秒后自动记录...")
        time.sleep(3)
        x1, y1 = pyautogui.position()
        print(f"[标定] 左上角记录: ({x1}, {y1})")

        print("[标定] 请将鼠标移到游戏列表区域的【右下角】，3秒后自动记录...")
        time.sleep(3)
        x2, y2 = pyautogui.position()
        print(f"[标定] 右下角记录: ({x2}, {y2})")

        w = x2 - x1
        h = y2 - y1

        if w <= 10 or h <= 10:
            print(f"[标定] ❌ 无效区域 (宽={w}, 高={h})，两个点太近或顺序错误，请重新标定。")
            print("       提示：左上角要在右下角的【左边且上面】，两点之间要有足够距离。")
            continue

        GAME_LIST_REGION = (x1, y1, w, h)
        print(f"[标定] ✅ 完成！区域已设为: {GAME_LIST_REGION}")
        save_config()
        return GAME_LIST_REGION


def step_reopen_game():
    """重新进入游戏：在微信搜索结果中精准点击第一条「向僵尸开炮」，等待加载。"""
    print(f"\n[重新进入] 等待 {WAIT_BEFORE_REOPEN} 秒后寻找游戏入口...")
    time.sleep(WAIT_BEFORE_REOPEN)

    # 依次尝试多个关键词，「僵尸开」最短最稳，可避免「炮/跑」被 OCR 误认
    found = False
    for kw in ["僵尸开炮", "僵尸开跑", "僵尸开", "向僵尸"]:
        print(f"  [重新进入] 尝试关键词「{kw}」...")
        found = click_text(kw, region=GAME_LIST_REGION)
        if found:
            break

    if not found:
        print("[重新进入] 所有关键词均未找到，跳过本轮。")
        print("  → 请查看 debug_region.png 确认截图区域是否正确")
        return False

    print(f"[重新进入] 已点击，等待游戏加载 {WAIT_GAME_LOADING} 秒...")
    time.sleep(WAIT_GAME_LOADING)
    bring_game_to_front()
    print("[重新进入] 加载完毕。")
    return True

def step_click_start():
    """点击「开始游戏」或「前往战场」，等待 5 秒。"""
    print("\n[] 尝试点击「」或「前往战场」...")
    found = click_text("开始游戏")
    if not found:
        found = click_text("前往战场")
    if not found:
        print("[] 均未找到，返回失败。")
        return False
    print(f"[] 点击成功，等待 {WAIT_AFTER_START} 秒...")
    time.sleep(WAIT_AFTER_START)
    return True


def step_close_game():
    """大退游戏窗口（Cmd+W / Alt+F4）。"""
    print("\n[大退] 关闭游戏窗口...")
    close_window()
    print("[大退] 完成。")


# ──────────────────────────────────────────────
# 【主循环】
# 第 1 轮：
#   点击「向僵尸开炮」→ 等待 10s → 点击「开始游戏」→ 等待 5s → 大退
# 第 2 轮起（每轮相同）：
#   点击「向僵尸开炮」→ 等待 10s → 点击「开始游戏」→ 等待 10s
#   → 点击「放弃挑战」→ 点击「开始游戏」→ 等待 5s → 大退
# ──────────────────────────────────────────────

def main_loop():
    round_num = 0
    while True:
        round_num += 1
        print(f"\n{'='*50}")
        print(f"  第 {round_num} 轮循环开始")
        print(f"{'='*50}")

        # ── 进入游戏 ─────────────────────────────
        try:
            ok = step_reopen_game()      # 点击「向僵尸开炮」+ 等待 10s
            if not ok:
                time.sleep(5)
                continue
        except Exception as e:
            print(f"[错误][进入游戏] {e}")
            continue
        
        try:
            ok = step_click_start()      # 再次点击「开始游戏」+ 等待 5s
            if not ok:
                step_close_game()
                continue
        except Exception as e:
            print(f"[错误][第{round_num}次开始游戏] {e}")
            step_close_game()
            continue
       
        try:
            step_close_game()            # 大退
        except Exception as e:
            print(f"[错误][大退] {e}")

        print(f"\n[循环] 第 {round_num} 轮结束，进入下一轮。")


# ──────────────────────────────────────────────
# 【入口】
# ──────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("  ZombieBot (Desktop) 启动")
    print("=" * 50)
    print()

    # ── 平台选择 ─────────────────────────────────
    auto_detected = "Mac" if IS_MAC else "Windows"
    print(f"[平台] 自动检测到: {auto_detected}")
    print("  直接按【回车】使用自动检测结果")
    print("  或输入 m = Mac  /  w = Windows  后按回车")
    choice = input("  你的选择: ").strip().lower()
    if choice == "m":
        IS_MAC = True
    elif choice == "w":
        IS_MAC = False
    # 空输入保持自动检测结果
    print(f"[平台] 已确认使用: {'macOS' if IS_MAC else 'Windows'} 模式")
    print()
    print("  按 Ctrl+C 终止 | 鼠标移至左上角紧急中断")
    print()

    # ── 读取已保存的配置（区域等）────────────────────
    load_config()

    # ── 首次使用：引导标定，完成后直接继续，不需要重新运行 ──
    if GAME_LIST_REGION is None:
        print("┌─────────────────────────────────────────────────┐")
        print("│  【首次使用】需要标定游戏列表的点击区域            │")
        print("│  标定结果自动保存，以后启动直接使用，无需重复操作  │")
        print("└─────────────────────────────────────────────────┘")
        print()
        print("请切换到微信，打开「向僵尸开炮」的搜索结果页面，")
        print("然后回到此窗口，按【回车】开始标定...")
        input()
        calibrate_game_region()
        print("\n[标定完成] 3 秒后自动开始运行...")
        time.sleep(3)
    else:
        print("[提示] 3 秒后开始运行，请确保微信搜索结果页面可见...")
        time.sleep(3)

    try:
        main_loop()
    except KeyboardInterrupt:
        print("\n[退出] 用户手动中断，脚本结束。")
