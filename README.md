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

    try {
      // 2. 提取文件名 (解码 URL 中的中文)
      const objectKey = decodeURIComponent(url.pathname.slice(4));

      // 3. 直接请求 R2 (不带任何条件参数，防止 R2 绑定报错)
      const object = await env.MY_BUCKET.get(objectKey);

      // 4. 文件不存在的处理
      if (object === null) {
        return new Response("File Not Found", { status: 404 });
      }

      // 5. 准备响应头
      const headers = new Headers();
      object.writeHttpMetadata(headers);
      headers.set("etag", object.httpEtag);
      // 再次强调：强制 CDN 缓存 2 小时
      headers.set("Cache-Control", "public, max-age=7200");

      // 获取浏览器发来的 ETag (通常带引号，例如 "abc")
      const clientETag = request.headers.get("If-None-Match");
      // 获取 R2 文件的 ETag (通常不带引号，例如 abc)
      const serverETag = object.httpEtag;

      // 如果浏览器发了 ETag，且内容匹配
      if (clientETag && serverETag) {
        // 简单粗暴的匹配：只要包含由于格式不同(带不带引号)，我们检查包含关系即可
        if (clientETag.includes(serverETag)) {
          // 命中缓存！不返回内容，只返回 304 状态码
          return new Response(null, {
            status: 304,
            headers,
          });
        }
      }

      // 7. 未命中缓存，返回完整文件
      return new Response(object.body, {
        headers,
      });
    } catch (e) {
      return new Response("Worker Error: " + e.message, { status: 500 });
    }
  },
};
```

然后将 Worker 绑定 R2 的 Obsidian bucket，变量名为 `MY_BUCKET`。

## 访问控制

配置 Cloudflare zero trust，限定访问用户
