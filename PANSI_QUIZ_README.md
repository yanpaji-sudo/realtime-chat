# 磐石九大知识闯关赛 — 云端版本

代码在 [panshi-quiz/](./panshi-quiz/) 中，包含120题、随机100题、移动端、服务器自动评分、Cloudflare D1共享排行榜、参与中名单和PNG结业证书。

本分支与已有 `realtime-chat` 服务隔离，不影响原项目。项目尚未对公网部署：需要Cloudflare账号D1数据库以及GitHub Actions Secrets（`CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN`, `D1_DATABASE_ID`）。

初始化一次D1：`npx wrangler d1 create panshi-quiz-db`，随后可从 Actions 页面手动运行“部署磐石知识闯关系统”。部署时将自动迁移数据库、测试、发布。切勿将API Token直接写入仓库。

注意：课程中的收入承诺、金融和博彩性质陈述仅供课程内容辨析，不代表事实已核查或合法性认可。
