# 流星会员树测试版（空白数据环境）

- Source baseline: formal production branch `member-tree-render`.
- All former brand wording in the application source and UI has been changed to `流星`.
- This test service uses a newly provisioned, separate PostgreSQL database.
- No production member accounts, balances, withdrawals, reports, academy documents, backups, or logs are copied.
- Demo-member seeding is disabled in this test version.
- Test records manually created here stay isolated from the formal production database.
- Free Render web services can spin down; free Render Postgres databases expire after 30 days. Do not use this environment for permanent records.
