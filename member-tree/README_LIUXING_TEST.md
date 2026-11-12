# 流星会员树测试版（空白数据环境）

- Source baseline: formal production branch `member-tree-render`.
- All former brand wording in the application source and UI has been changed to `流星`.
- This test service uses its own local SQLite file and does not connect to the formal production database or any other test database.
- No production member accounts, balances, withdrawals, reports, academy documents, backups, or logs are copied.
- The database starts with zero members and zero academy documents; demo-member seeding is disabled.
- Test records manually created here remain isolated from the formal production database.
- Render Free web services have ephemeral filesystems and can spin down; any test records entered here may be lost after spin-down, restart, or redeploy. Do not use this environment for permanent records.
