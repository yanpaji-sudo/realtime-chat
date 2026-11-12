# V11 正式版本发布说明

新增：完整账号精准搜索（只在 Enter/精准定位点击执行），自动展开祖先，居中放大至可读大小，唯一目标黄色高亮；右下角固定悬浮「＋ 新增会员」。

沿用正式版 `ADMIN_USERS_JSON` 中8位管理员的独立密码、登录与CSRF保护；管理员日志/撤回和分支图；V10智能粘贴新增；按入会时间的红色等级/当日绿色；服务端共享数据。

加密备份：管理员经登录后取得后端记录，由浏览器AES-256-GCM加密成.mtbackup。恢复须输入密码并二次确认、输入“确认覆盖”，服务端原子恢复完整会员及审计日志，带权限与校验。

数据库注意事项：本次没有清空数据的自动调用。但若Render环境没有DATABASE_URL，仍使用临时本地SQLite，发布及重启可能使历史数据丢失。必须单独配置持久化数据库并定期另存备份。

构建：`base64 -d member-tree-deploy/payload.b64 | tar xz && pip install -r member-tree/requirements.txt`
启动：`cd member-tree && uvicorn app:app --host 0.0.0.0 --port $PORT`
