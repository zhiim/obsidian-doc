# Obsidian-DOC

Publish obsidian notes using [docsify](https://docsify.js.org).

## 工作流

- Obsidian 数据使用 [Remotely Save](https://github.com/remotely-save/remotely-save) 插件同步到 Cloudflare R2 存储
- 为存有 Obsidian 数据的 Cloudflare R2 bucket 分配一个可公开访问的 url
- 使用 docsify 搭建前端网页，设定数据路径为 Cloudflare R2 bucket 对应的 url，并通过 Cloudflare Pages 部署 docsify

## 访问量优化

为了防止过多请求 Cloudflare R2 bucket，使用 [Python 脚本](./gen_sidebar.py) 为 Obsidian 笔记的每个文件目录生成 `_sidebar.md` 和 `README.md`，实现笔记数据的按需读取。

打开 docsify 页面的时候，只需要请求当前所在目录的 `_sidebar.md` 和 `README.md`。这两个文件记录了当前目录所有子目录和笔记页的 url：

- 当打开子目录时，只需要请求子目录的 `_sidebar.md` 和 `README.md`
- 当打开笔记页时，只需要情况当前笔记对于的 Markdown 文件

以此实现笔记数据在需要的时候才会发出读取请求。

```python
import os
import urllib.parse

# ---------------- 配置区域 ----------------
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
}
IGNORE_FILES = {
    "_sidebar.md",
    "_navbar.md",
    "README.md",
    "index.html",
    "gen_nested_sidebar.py",
    ".DS_Store",
    "HOME.md",
}

OVERWRITE_README = True
# ----------------------------------------


def get_web_path(path):
    """
    将文件系统路径转换为 Web 绝对路径 (以 / 开头)
    例如: ./Notes/CPP -> /Notes/CPP
    """
    # 统一将反斜杠(Windows)替换为正斜杠
    clean_path = path.replace("\\", "/")
    # 去掉开头的 ./ 或 .
    if clean_path.startswith("./"):
        clean_path = clean_path[2:]
    elif clean_path == ".":
        clean_path = ""

    # 确保以 / 开头
    if not clean_path.startswith("/"):
        clean_path = "/" + clean_path

    # URL 编码 (处理中文和特殊字符)
    # 注意：我们要分段编码，否则斜杠也会被编码
    parts = clean_path.split("/")
    encoded_parts = [urllib.parse.quote(p) for p in parts]
    return "/".join(encoded_parts)


def generate_files_for_current_dir(root, dirs, files):
    # 当前目录的 Web 绝对路径 (用于拼接子项)
    current_web_root = get_web_path(root)

    # --- 1. 准备数据 (全部生成绝对路径) ---
    folder_links = []
    file_links = []

    for d in dirs:
        # 子文件夹的绝对路径
        link = f"{current_web_root}/{urllib.parse.quote(d)}/README.md".replace(
            "//", "/"
        )
        folder_links.append((d, link))

    for file in files:
        if file.endswith(".md") and file not in IGNORE_FILES:
            title = os.path.splitext(file)[0]
            # 文件的绝对路径
            link = f"{current_web_root}/{urllib.parse.quote(file)}".replace("//", "/")
            file_links.append((title, link))

    # --- 2. 计算“返回上一级”的绝对路径 ---
    back_link = None
    if root != ".":
        # 获取父目录的物理路径
        parent_dir = os.path.dirname(root)
        # 转换为父目录的 Web 路径 + README.md
        # 比如当前是 /Notes/CPP -> 父级就是 /Notes/README.md
        # 如果父级是根目录 -> /README.md
        parent_web_path = get_web_path(parent_dir)
        back_link = f"{parent_web_path}/README.md".replace("//", "/")

    # --- 3. 生成 _sidebar.md ---
    sidebar_lines = []
    if back_link:
        # 这里直接使用计算好的绝对路径，不再用 ../
        sidebar_lines.append(f"* [🔙 返回上一级]({back_link})")
        sidebar_lines.append("")

    for name, url in folder_links:
        sidebar_lines.append(f"* [**{name}**]({url})")

    for name, url in file_links:
        sidebar_lines.append(f"* [{name}]({url})")

    if sidebar_lines:
        sidebar_path = os.path.join(root, "_sidebar.md")
        with open(sidebar_path, "w", encoding="utf-8") as f:
            f.write("\n".join(sidebar_lines))

    # --- 4. 生成 README.md ---
    readme_path = os.path.join(root, "README.md")

    # 注意：这里建议暂时开启覆盖，因为你之前生成的 README 链接是坏的
    if root != "." and (OVERWRITE_README or not os.path.exists(readme_path)):
        readme_lines = []
        folder_name = os.path.basename(os.path.abspath(root))
        title = folder_name

        readme_lines.append(f"# {title}\n")

        # 同样在 README 里添加一个显式的返回上一级
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

        with open(readme_path, "w", encoding="utf-8") as f:
            f.write("\n".join(readme_lines))
        print(f"✅ 更新: {readme_path}")


if __name__ == "__main__":
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        dirs.sort()
        files.sort()
        generate_files_for_current_dir(root, dirs, files)
```

## Deploy docsify site using Cloudflare Pages

在 Cloudflare Pages 的面板导入这个仓库，网站就会自动部署。得益于 docsify 的便捷设置，整个网站其实只是一个单文件的 [`index.html`](./index.html)，只需要在里面设定 docsify 的相关配置参数。

此外需要为静态网页分配域名，例如 `doc.example.com`。

## 转发 Cloudflare R2 读取请求

将对 Cloudflare R2 的转发到 `doc.example.com/r2/*`。

创建 Cloudflare Work，写入代码

```javascript
export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // 1. 路径检查
    if (!url.pathname.startsWith("/r2/")) {
      return new Response("Not found", { status: 404 });
    }

    // 2. 提取文件名
    const objectKey = decodeURIComponent(url.pathname.slice(4));

    // 3. 准备传给 R2 的参数 (这是关键改进点)
    // 允许 Range (视频拖拽) 和 If-None-Match (304协商缓存)
    const options = {
      range: request.headers.get("range"),
      onlyIf: request.headers,
    };

    try {
      const object = await env.MY_BUCKET.get(objectKey, options);

      if (object === null) {
        return new Response("File Not Found", { status: 404 });
      }

      const headers = new Headers();
      // 写入 R2 原有的元数据 (ContentType, ETag 等)
      object.writeHttpMetadata(headers);
      headers.set("etag", object.httpEtag);

      // 4. 显式添加缓存控制 (双重保险)
      // 这里的 public 表示允许 CDN 缓存
      // max-age=7200 表示建议缓存 2 小时 (与你的后台设置匹配)
      headers.set("Cache-Control", "public, max-age=7200");

      // 5. 返回响应
      // 如果 R2 返回的是部分内容 (Range) 或 304，这里会自动处理 status
      return new Response(object.body, {
        headers,
        status: object.body ? (request.headers.get("range") ? 206 : 200) : 304,
      });
    } catch (e) {
      return new Response("Error: " + e.message, { status: 500 });
    }
  },
};
```

然后将 Worker 绑定 R2 的 Obsidian bucket，变量名为 `MY_BUCKET`。

## 访问控制

配置 Cloudflare zero trust，限定访问用户
