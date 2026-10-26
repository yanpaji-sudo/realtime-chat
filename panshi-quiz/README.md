# 磐石学习学院 — 九大知识闯关赛（移动端）

**108道候选题，每次随机抽取100道。** 正确答案每份试卷严格按 A/B/C/D 各25道均衡分布，选项会随机排序。新增加的合作共赢、48小时报备、7天未回复退出、禁止多开代下注、家属入场报备等题均已纳入题库。

## 功能

- 匿名昵称参赛（2—16字符，不收集手机号），手机优先响应式排版
- 九大知识章节卡片，无人物展示
- 从108道题中随机抽取100道，并随机打乱选项顺序
- 服务器保存每名成员的独立试卷答案顺序，提交后由服务器评分
- Cloudflare D1 数据库存储全体成绩与进行中学员；20秒刷新排行榜
- 排名按昵称的最佳成绩显示，分数越高越靠前，同分用时短的靠前
- 交卷自动生成编号证书，可下载 PNG、打印为 PDF、查看错题
- 临时答卷保存在同一浏览器当前标签的 sessionStorage，刷新时可继续作答
- `磐石九大知识答题_手机离线体验版.html` 为**纯本机模拟**，不含真实共享排行榜

## 本地测试（不需登录云平台）

运行 `node --test tests/core.test.mjs`，测试题库、选题、选项均衡、评分、防重复交卷、云端接口。

直接打开 **`磐石九大知识答题_手机离线体验版.html`** 体验外观、答题、打分、证书。本机体验版排行榜只在当前浏览器保存，不是云端共享。

## 正式免费部署（Cloudflare Workers + D1）

Cloudflare Workers 提供免费额度，D1 也有免费用量；超过免费配额会受服务限制，使用前请查看官方定价条款。正式部署必须使用您自己的 Cloudflare 账号。

在解压出来的项目目录运行：

```bash
npm install
npx wrangler login
npx wrangler d1 create panshi-quiz-db
```

第三条命令会返回数据库 ID。将 `wrangler.jsonc` 里面的 `REPLACE_WITH_YOUR_D1_DATABASE_ID` 换成真实 ID，然后运行：

```bash
npx wrangler d1 migrations apply panshi-quiz-db --remote
npm test
npx wrangler deploy
```

部署完成后命令行会返回 `https://xxx.workers.dev` 的公开网址。该网址即可分享给手机端成员使用，全体成员共用真正的 D1 排行榜和答题进行中名单。

**不要只将前端页面上传到 GitHub Pages**，因为 GitHub Pages 只提供静态文件，无法独立实现安全的多人共享排行榜或服务器评分。

## GitHub 仓库持续部署

将完整项目（包括 `.github/workflows/deploy.yml`）推送到一个 **新建独立仓库**。Cloudflare 账号里创建两个 GitHub Actions Secrets：

- `CLOUDFLARE_API_TOKEN`：具有 Workers 部署和所需 D1 权限的 Cloudflare API 令牌
- `CLOUDFLARE_ACCOUNT_ID`：Cloudflare Account ID

初次仍需按上面的步骤创建 D1 并设置 `database_id`。完成后，推送到 `main` 会运行自动测试和云端部署。

## 修改题库

编辑 `data/questions.js`。每题字段：`id`（不重复）、`chapter`、`question`、`options`（四个）、`answer`（0到3）、`explanation`。新增题目只会进入**服务器**题库，所有考试均从新的总题库里随机抽100题，不用修改前端。每份试卷的A/B/C/D正确答案数量固定25道。

## 重要提示

课件中的高比例分润、推荐奖励、企业合作、股票市值、提现和社保承诺等描述，可能属于未经独立证实的项目陈述。本应用仅作为课程知识测试工具，不代表对真实性、合法性、资金安全或未来收益的认可；特别是彩票、下注、USDT与多层级奖励活动，应进行独立法律与财务审查。证书只代表完成题目，不是理财资格或业务合规证明。