# 孙导带你夜夜笙歌

个人彩票观测站：开奖爬取 / 分析 / 娱乐预测 / 购彩记录 / 奖金估算 / 邮件推送。

> **合规声明**：号码预测与策略推荐**仅供娱乐**，不保证中奖，不构成任何投注建议。请理性购彩，量力而行。开奖请以官方公布为准。

## 技术栈

- 前端：Vue 3 + Vite + Vue Router（视觉对齐 lottery-ui v3 素净冷静）
- 后端：FastAPI + SQLAlchemy + SQLite
- 定时：APScheduler（启动时按设置间隔爬取）

## 目录

```
ye-ye-sheng-ge/
  backend/          FastAPI
  frontend/         Vue3 SPA
  .env.example      SMTP 等环境变量示例
  README.md
```

## 启动

### 1. 后端

```bash
cd /workspace/ye-ye-sheng-ge
python3 -m venv backend/.venv
source backend/.venv/bin/activate
pip install -r backend/requirements.txt
# 可选：cp .env.example .env 并填写 SMTP
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

健康检查：`http://127.0.0.1:8000/api/health`  
文档：`http://127.0.0.1:8000/docs`

### 2. 前端

```bash
cd /workspace/ye-ye-sheng-ge/frontend
npm install
npm run dev
```

浏览器打开 Vite 提示的地址（默认 `http://127.0.0.1:5173`）。`/api` 已代理到后端 `8000`。

## 功能清单

| 功能 | 状态 | 说明 |
|------|------|------|
| 开奖列表 / 最新 | ✅ | SQLite 存储；首次自动种子数据 |
| 手动 / 定时爬取 | ✅ | 福彩部分公开接口尽力而为；失败保留种子并返回错误列表 |
| 号码分析 | ✅ | 冷热频次、遗漏、热力 |
| 开奖回声 | ✅ | 对照近期开奖，找出与一注号码重合最多的期次；数字彩按位比较。仅供娱乐，不代表下期结果 |
| 号码结伴 | ✅ | 主号共现：哪些号码经常一起出现；数字彩看不同位置。仅供娱乐，不构成投注建议 |
| 号码撞车 | ✅ | 同一彩种多注对照：撞号浪费与没覆盖到的号；数字彩按位比较。可一键用购彩记录。预测/分析仅供娱乐，不构成投注建议 |
| 重号脉搏 | ✅ | 相邻两期主号有多少留下来，再把一注对照最新开奖。乐透按集合，数字彩按位；特别号单独计。仅供娱乐，不构成投注建议 |
| 预测推荐 | ✅ | hot/cold/hybrid/random；API 与页面均有娱乐免责 |
| 购买记录 CRUD | ✅ | 盈亏汇总 |
| 奖金计算 | ✅ | 各彩种简化固定规则 |
| 邮件测试 / 摘要 | ✅ | 依赖 `.env` SMTP；未配置返回友好提示 |
| 设置 | ✅ | 爬取间隔、订阅彩种、邮箱开关 |

## 彩种

双色球 `ssq`、大乐透 `dlt`、福彩3D `fc3d`、排列三 `pl3`、排列五 `pl5`、七星彩 `qxc`、快乐八 `kl8`

## 已知限制

1. **爬虫**：仅对福利彩票官网部分 JSON 接口做尝试；大乐透/排三/排五/七星彩等无稳定公开源时**只用种子数据**，并在爬取结果里提示。接口变更或网络拦截会导致爬取失败，属预期。
2. **邮件**：必须自行配置 SMTP；本环境默认不发送真实邮件。
3. **奖金**：一等奖等浮动奖为示意金额；快乐八按「选十」简化表。
4. **定时间隔**：修改设置中的分钟数后，需重启 uvicorn 才能让 APScheduler 重读间隔。
5. **数据标签**：顶栏「示例 / 混合 / 爬取」反映本地 `source` 字段，非实时官方状态。

## 视觉（v3）

近黑底 `#0c0c0f`、强调蓝灰 `#7d8fa8`、金色仅 Logo/主 CTA、扁平号码球、低饱和图表。样式来自 `/workspace/lottery-ui/shared.css`。
