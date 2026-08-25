# 从这里开始：SKU Inventory Monitor

这份代码包已经按确认的 UI 做成 Streamlit，并已用你上传的 4 个 BOM 文件生成当前数据快照。

## 这版使用哪些数据

| 来源 | 本应用是否使用 | 主要用途 |
|---|---:|---|
| Current Inventory | 是 | Lot、状态、数量、有效期 |
| Product COGS | 是 | 最新有效单位 COGS |
| Product Master | 是 | Material、NDC、Product Line、Supplier、Product Status |
| SCM Actual vs. Forecast | 是 | 月度 Forecast、6M Average、12M Coverage |
| Product Status Mapping Master | **否** | 留给 Inventory Reconciliation Phase 2.5 |

原始 Excel 继续统一放在 `E:\BOM`，不会复制进 GitHub。刷新脚本会在本地把四个来源合并成一个
压缩快照，Streamlit 网页直接读取快照，所以启动和筛选更快。

## 先在本地打开

解压后，在项目文件夹打开 PowerShell：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python scripts\validate_data.py --data-dir data
streamlit run app.py
```

浏览器打开 `http://localhost:8501`。

## 推到网上的最短步骤

1. 在 GitHub 建一个 **Private** repository。
2. 在项目 PowerShell 运行：

```powershell
git init
git branch -M main
git add .
git commit -m "Initial SKU Inventory Monitor"
git remote add origin https://github.com/<你的账号或组织>/solco-sku-inventory-monitor.git
git push -u origin main
```

3. 登录 https://share.streamlit.io ，连接 GitHub。
4. 选择刚才的 private repository、`main` branch、`app.py`。
5. Python 选 `3.12`，然后 Deploy。
6. 在 Streamlit 的访问/分享设置中保持 restricted/private，并邀请 CFO、Finance、SCM、
   Operations、Sales、Customer Service 团队成员。

完整截图式步骤、以后刷新命令和常见问题见
[`docs/DEPLOYMENT_GUIDE_CN.md`](docs/DEPLOYMENT_GUIDE_CN.md)。

## 以后刷新数据

关闭正在打开的 BOM Excel 文件，然后：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\refresh_from_bom.ps1
git add data\inventory_snapshot.csv.gz data\snapshot_metadata.json
git commit -m "Refresh SKU inventory snapshot"
git push
```

Streamlit 会从新的 GitHub commit 重新部署。原始 BOM Excel 仍留在 `E:\BOM`。

## 上线前还缺什么

- 一个可用的 GitHub 账号或公司 Organization，并建立 **Private** repo；
- 一个 Streamlit 账号/Workspace，并确认公司允许的访问隐私设置；
- 需要邀请的团队邮箱名单；
- 确认谁负责每次运行刷新脚本及 push；如果希望完全自动刷新，还需要公司可访问
  `E:\BOM` 的 Windows runner/server 或改用 SharePoint、数据库等云端数据源。
