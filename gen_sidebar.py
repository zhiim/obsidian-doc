import os
import posixpath
import urllib.parse
from datetime import datetime
import logging

IGNORE_DIRS = {
    ".git",
    ".obsidian",
    ".trash",
    ".idea",
    ".vscode",
    "assets",
    "images",
    "img",
    "draws",
    "attachments",
    "media",
    "课题",
    "reading_materials",
}
IGNORE_FILES = {  # 只用考虑 markdown 文件
    "_sidebar.md",  # 目录里面不要出现 _sidebar.md 自己
    "_navbar.md",
    "README.md",  # 目录里面不显示 README.md
}
OVERWRITE_README = True
URL_ENCODE_LINKS = True

logger = logging.getLogger()
file_handler = logging.FileHandler("info.log")
logger.addHandler(file_handler)
logger.setLevel(logging.INFO)


def get_web_path(local_path):
    """
    将文件系统路径转换为标准的 Web 绝对路径 (以 / 开头)
    例如: . -> /
         ./Notes/CPP -> /Notes/CPP
    """
    clean_path = local_path.replace("\\", "/")
    if clean_path.startswith("./"):
        clean_path = clean_path[2:]

    if clean_path == "." or clean_path == "":
        return "/"

    return "/" + clean_path.strip("/")


def write_if_changed(filepath, content):
    """
    仅当文件不存在或内容不同时才写入
    """
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            existing_content = f.read()
        if existing_content == content:
            return False

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return True


def format_url(url_path):
    """根据配置决定是否进行 URL 编码"""
    if URL_ENCODE_LINKS:
        parts = url_path.split("/")
        return "/".join(urllib.parse.quote(p) for p in parts)
    return url_path


def generate_files_for_current_dir(root, dirs, files):
    current_web_root = get_web_path(root)

    # --- 1. 准备数据 ---
    folder_links = []
    file_links = []

    for d in dirs:
        raw_link = posixpath.join(current_web_root, d, "README.md")
        link = format_url(raw_link)
        folder_links.append((d, link))

    for file in files:
        if file.endswith(".md") and file not in IGNORE_FILES:
            title = os.path.splitext(file)[0]
            raw_link = posixpath.join(current_web_root, file)
            link = format_url(raw_link)
            file_links.append((title, link))

    # --- 2. 计算“返回上一级”的绝对路径 ---
    back_link = None
    if root != ".":
        parent_dir = os.path.dirname(root)
        parent_web_path = get_web_path(parent_dir)
        raw_back_link = posixpath.join(parent_web_path, "README.md")
        back_link = format_url(raw_back_link)

    # --- 3. 生成 _sidebar.md ---
    sidebar_lines = []
    if back_link:
        sidebar_lines.append(f"* [🔙 返回上一级]({back_link})")

    for name, url in folder_links:
        sidebar_lines.append(f"* [**{name}**]({url})")

    for name, url in file_links:
        sidebar_lines.append(f"* [{name}]({url})")

    if sidebar_lines:
        sidebar_path = os.path.join(root, "_sidebar.md")
        siderbar_content = "\n".join(sidebar_lines)
        if write_if_changed(sidebar_path, siderbar_content):
            logging.info(f"更新侧边栏: {sidebar_path}")

    # --- 4. 生成 README.md ---
    readme_path = os.path.join(root, "README.md")

    if root != "." and (OVERWRITE_README or not os.path.exists(readme_path)):
        readme_lines = []
        folder_name = os.path.basename(os.path.abspath(root))

        readme_lines.append(f"# {folder_name}\n")

        if back_link:
            readme_lines.append(f"> [🔙 返回上一级]({back_link})\n")

        if folder_links:
            readme_lines.append("## 子文件夹")
            for name, url in folder_links:
                readme_lines.append(f"- 📁 [{name}]({url})")
            readme_lines.append("")

        if file_links:
            readme_lines.append("## 笔记列表")
            for name, url in file_links:
                readme_lines.append(f"- 📄 [{name}]({url})")

        if not folder_links and not file_links:
            readme_lines.append("*此目录下暂时没有公开的笔记。*")

        readme_content = "\n".join(readme_lines)
        if write_if_changed(readme_path, readme_content):
            logging.info(f"更新主页: {readme_path}")


if __name__ == "__main__":
    logging.info(f"{datetime.now().strftime('%Y-%m-%d-%H:%M:%S')} ----------")
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        dirs.sort()
        files.sort()
        generate_files_for_current_dir(root, dirs, files)
