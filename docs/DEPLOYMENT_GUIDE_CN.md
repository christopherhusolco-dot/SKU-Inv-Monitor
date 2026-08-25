# SKU Inventory Monitor：一步一步上线到 Streamlit

推荐架构：`E:\BOM` 原始 Excel → 本地压缩快照 → Private GitHub → Restricted Streamlit App。

这样原始 BOM 文件继续统一管理，GitHub 只保存网页代码和已经合并的快照；Streamlit 不需要
每次启动都解析四个 Excel，刷新和筛选速度更快。

## 第 1 步：准备电脑和账号

需要：

- Windows 电脑；
- Python 3.12；
- Git；
- GitHub 账号，或公司 GitHub Organization 的 repo 权限；
- Streamlit 账号/Workspace；
- 4 个来源位于 `E:\BOM`，或你指定的其他统一目录。

把完整 ZIP 解压到例如：

`E:\SKU Inv Monitor\sku_inventory_monitor_streamlit`

不要只复制 `app.py`。`src`、`config`、`scripts`、`data`、`docs`、`.streamlit` 和
`requirements.txt` 都必须保留。

## 第 2 步：安装本地环境

在项目目录空白处 Shift + 右键，打开 PowerShell：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

以后重新打开 PowerShell，只需要先运行：

```powershell
.\.venv\Scripts\Activate.ps1
```

## 第 3 步：确认现有快照

代码包已经包含根据你上传文件生成的当前快照。先验证：

```powershell
python scripts\validate_data.py --data-dir data
```

应看到：

- Load mode：`Fast deploy snapshot`；
- Inventory as of：`2026-08-25`；
- 4 个 Source 都是 `Loaded`；
- Product Status Mapping Master 不在 Source Manifest 中。

WARN/REVIEW 不一定是程序错误。当前文件里存在少量缺少 Product Master、COGS 或 Forecast
mapping 的行，以及可能属于仓库/状态拆分的重复 lot/status 行，需要业务 owner 审核。

## 第 4 步：从统一 BOM 目录重新生成快照

确认以下四个文件在 `E:\BOM`：

1. Current Inventory
2. Product COGS
3. Product Master
4. SCM Actual vs. Forecast

`Product Status Mapping Master` 可以继续留在 BOM 目录，但本脚本会忽略它。

关闭 Excel 文件，避免 `~$` 临时锁文件，然后运行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\refresh_from_bom.ps1
```

如果统一来源不是 `E:\BOM`：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\refresh_from_bom.ps1 -SourceDir "D:\Your\BOM"
```

脚本执行三件事：

1. 自动选择每类最新文件；
2. 生成 `data\inventory_snapshot.csv.gz` 和 `data\snapshot_metadata.json`；
3. 自动运行数据质量和 KPI 验证。

原始 Excel 不会复制到项目目录。

## 第 5 步：本地打开网页验收

```powershell
streamlit run app.py
```

浏览器打开：`http://localhost:8501`

验收清单：

- 左侧只显示 4 个 governed sources；
- Product Status Mapping Master 显示为 Not used；
- Data as of 日期正确；
- 默认 Recall view 是 `Recall excluded`；
- Enterprise Overview、CFO/Finance、SCM、Operations、Sales/Customer Service 都能切换；
- Search、Product Line、Inventory Status、Lot Status、Recall 筛选有效；
- Lot Explorer 可以下载 CSV；
- Excel package 可以生成和下载；
- Sales 页面显示的是 Commercial Review Pool，而不是最终 sale authorization。

停止本地服务：PowerShell 按 `Ctrl + C`。

## 第 6 步：创建 Private GitHub Repository

1. 登录 GitHub。
2. 点击右上角 `+` → `New repository`。
3. 名称建议：`solco-sku-inventory-monitor`。
4. Visibility 必须选 **Private**。
5. 不要勾选自动生成 README、`.gitignore` 或 License。
6. 点击 `Create repository`。

因为 deploy snapshot 仍包含内部数量、COGS 和 Forecast 信息，不能使用 Public repo。

## 第 7 步：第一次 push 到 GitHub

把 `<YOUR_GITHUB_USER_OR_ORG>` 换成你的账号或公司组织名：

```powershell
git init
git branch -M main
git add .
git commit -m "Initial SKU Inventory Monitor"
git remote add origin https://github.com/<YOUR_GITHUB_USER_OR_ORG>/solco-sku-inventory-monitor.git
git push -u origin main
```

打开 GitHub repo，确认：

- repo 显示 `Private`；
- 根目录有 `app.py` 和 `requirements.txt`；
- 有 `src`、`config`、`scripts`、`.streamlit`；
- `data` 里有 `inventory_snapshot.csv.gz`、`snapshot_metadata.json`、
  `inventory_history.csv`；
- `data` 里没有 4 个原始 BOM Excel 文件。

## 第 8 步：连接 Streamlit Community Cloud

1. 打开 https://share.streamlit.io 。
2. 用 GitHub 登录。
3. 授权 Streamlit 访问这个 private repository。
4. 如果 repo 属于公司 Organization，可能需要 Organization owner 批准第三方访问。
5. 回到 Streamlit workspace，点击 `Create app`。

## 第 9 步：Deploy

填写：

- Repository：`solco-sku-inventory-monitor`
- Branch：`main`
- Main file path：`app.py`
- Python version：`3.12`
- Secrets：本版本不需要，留空

点击 `Deploy`。首次安装 dependencies 后打开网页，重新走一次第 5 步的验收清单。

## 第 10 步：限制团队访问

在 Streamlit 的 app 设置或 Share/Manage access 中：

1. 保持 app 为公司允许的 restricted/private 状态；
2. 邀请 CFO、Finance、SCM、Operations、Sales、Customer Service 成员；
3. 用一个未受邀账号测试，确认不能访问；
4. 不要把 GitHub repo 或 app 改成 Public。

具体可用的私有访问方式和人数限制取决于公司的 Streamlit workspace/plan；正式上线前由
IT 或系统 owner 确认。

## 第 11 步：以后每次刷新

```powershell
.\.venv\Scripts\Activate.ps1
powershell -ExecutionPolicy Bypass -File scripts\refresh_from_bom.ps1
git status
git add data\inventory_snapshot.csv.gz data\snapshot_metadata.json
git commit -m "Refresh SKU inventory snapshot"
git push
```

GitHub 收到新 commit 后，Streamlit 会重新部署。由于网页读取的是压缩快照，不需要上传或
重新解析原始 Excel。

## 第 12 步：谁负责什么

| 工作 | 建议 owner |
|---|---|
| Current Inventory 文件正确性 | Operations / WMS |
| Product COGS 和估值口径 | Finance |
| Product Master / NDC mapping | Master Data / SCM |
| Forecast 月份和需求口径 | SCM |
| Restricted / Recall disposition | QA / SCM / Operations |
| Sales review pool 后续动作 | Sales / Customer Service |
| Snapshot refresh 和 GitHub push | 指定的 App/Data Owner |
| Streamlit 权限和团队成员 | App Owner / IT |

## 常见问题

### `Current Inventory was not found`

检查 `-SourceDir` 是否正确，文件名是否包含 `Current Inventory`，并确认文件不是 `~$` 开头。

### 网页启动但数据旧

检查 GitHub 上 `data/snapshot_metadata.json` 的 commit 是否更新。若 GitHub 已更新，去
Streamlit app 管理菜单 Reboot/Rerun。

### Streamlit 找不到 private repo

重新连接 GitHub private-repository 权限；如果 repo 属于公司 Organization，请让 owner
批准访问。

### Product Status Mapping 为什么没生效

这是设计决定，不是缺文件。该来源属于 Inventory Reconciliation Phase 2.5；本应用的
Product Status 来自 Product Master。

### 怎样做到完全自动刷新

Streamlit Cloud 无法直接读取你电脑的 `E:\BOM`。需要公司提供可访问该目录的 Windows
runner/server 来定时生成并 push 快照，或把统一来源迁移到 SharePoint、数据库、S3 等
云端位置，再增加安全连接和 secrets 管理。

## 官方参考

- 部署：https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy
- Dependencies：https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies
- GitHub 连接：https://docs.streamlit.io/deploy/streamlit-community-cloud/get-started/connect-your-github-account
- 分享与访问：https://docs.streamlit.io/deploy/streamlit-community-cloud/share-your-app
